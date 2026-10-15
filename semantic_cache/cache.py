"""SemanticCache: embed -> nearest cached question (within scope) -> threshold gate ->
return the cached answer, or generate one, return it and write it back."""
from __future__ import annotations

import hashlib
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Union

from lakebase.core.search.filters import F

from .backends import CacheBackend, make_backend
from .config import CacheConfig


@dataclass
class Generation:
    """What a ``generate`` callable may return instead of a plain string, so token usage
    of cache misses can be logged and costed."""
    text: str
    input_tokens: int = 0
    output_tokens: int = 0


Generator = Callable[[str], Union[str, Generation]]


@dataclass
class CacheResult:
    question: str
    answer: str | None
    hit: bool
    similarity: float | None = None          # similarity of the nearest in-scope entry
    cache_id: str | None = None              # entry served (hit) or written (miss)
    matched_question: str | None = None
    matched_metadata: dict | None = None     # metadata stored with the nearest entry
    scope: dict = field(default_factory=dict)
    threshold: float | None = None
    embed_ms: float = 0.0
    lookup_ms: float = 0.0
    generate_ms: float = 0.0
    write_ms: float = 0.0
    total_ms: float = 0.0
    input_tokens: int = 0                    # LLM usage on a miss (0 on a hit)
    output_tokens: int = 0
    embedding: list[float] | None = field(default=None, repr=False)  # query embedding

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("embedding")
        return d


def cache_id_for(question: str, scope: dict, scope_columns) -> str:
    """Deterministic id, so re-caching the same question in the same scope replaces it."""
    key = "\x1f".join([*(str(scope.get(c, "")) for c in scope_columns), " ".join(question.lower().split())])
    return hashlib.sha256(key.encode()).hexdigest()[:32]


class SemanticCache:
    def __init__(self, cfg: CacheConfig, backend: CacheBackend | None = None, workspace_client=None):
        from databricks.sdk import WorkspaceClient

        self.cfg = cfg
        self.backend = backend or make_backend(cfg)
        self.w = workspace_client or WorkspaceClient()

    # --- embeddings --------------------------------------------------------------------
    def embed(self, texts: list[str], batch_size: int = 150) -> list[list[float]]:
        # Foundation Model API embedding endpoints cap inputs per request (150 for Qwen3).
        out = []
        for i in range(0, len(texts), batch_size):
            resp = self.w.serving_endpoints.query(name=self.cfg.embedding_endpoint, input=texts[i:i + batch_size])
            out += [d.embedding for d in sorted(resp.data, key=lambda d: d.index)]
        return out

    # --- core operations ---------------------------------------------------------------
    def _scope_filter(self, scope: dict):
        """A scope value may be a list, to match entries in any of several scopes."""
        def match(c):
            v = scope.get(c, "")
            return F.in_(c, [str(x) for x in v]) if isinstance(v, (list, tuple, set)) else F.eq(c, str(v))
        now = datetime.now(timezone.utc)
        return F.and_(
            *(match(c) for c in self.cfg.scope_columns),
            F.or_(F.is_null("expires_at"), F.gt("expires_at", now)),
        )

    def lookup(self, question: str, scope: dict | None = None, *, threshold: float | None = None,
               embedding: list[float] | None = None) -> CacheResult:
        """Find the nearest in-scope, unexpired entry; a hit if similarity >= threshold."""
        scope = scope or {}
        threshold = self.cfg.similarity_threshold if threshold is None else threshold
        t0 = time.perf_counter()
        if embedding is None:
            embedding = self.embed([question])[0]
        t1 = time.perf_counter()
        rows = self.backend.search(embedding, filters=self._scope_filter(scope), top_k=1)
        t2 = time.perf_counter()

        res = CacheResult(question=question, answer=None, hit=False, scope=scope, threshold=threshold,
                          embed_ms=(t1 - t0) * 1e3, lookup_ms=(t2 - t1) * 1e3, embedding=embedding)
        if rows:
            best = rows[0]
            res.similarity = best["similarity"]
            res.matched_question = best["question"]
            res.matched_metadata = best.get("metadata")
            if best["similarity"] >= threshold:
                res.hit, res.answer, res.cache_id = True, best["answer"], best["cache_id"]
                if self.cfg.track_hits:
                    self.backend.record_hit(best["cache_id"])
        res.total_ms = (time.perf_counter() - t0) * 1e3
        return res

    def put(self, question: str, answer: str, scope: dict | None = None, *, embedding: list[float] | None = None,
            metadata: dict | None = None, ttl_seconds: int | None = None) -> str:
        scope = scope or {}
        embedding = embedding if embedding is not None else self.embed([question])[0]
        ttl = ttl_seconds if ttl_seconds is not None else self.cfg.default_ttl_seconds
        cid = cache_id_for(question, scope, self.cfg.scope_columns)
        self.backend.upsert([{
            "cache_id": cid, "question": question, "answer": answer, "embedding": embedding,
            "scope": scope, "metadata": metadata,
            "expires_at": datetime.now(timezone.utc) + timedelta(seconds=ttl) if ttl else None,
        }])
        return cid

    def get_or_generate(self, question: str, generate: Generator, scope: dict | None = None, *,
                        threshold: float | None = None, write_back: bool = True,
                        metadata: dict | None = None, write_scope: dict | None = None) -> CacheResult:
        """Serve from cache on a hit; otherwise call ``generate(question)`` and cache the answer.
        ``write_scope`` (default ``scope``) is where a miss is cached, e.g. one scope of a multi-scope lookup."""
        t0 = time.perf_counter()
        res = self.lookup(question, scope, threshold=threshold)
        if not res.hit:
            t1 = time.perf_counter()
            out = generate(question)
            if isinstance(out, Generation):
                res.answer, res.input_tokens, res.output_tokens = out.text, out.input_tokens, out.output_tokens
            else:
                res.answer = out
            t2 = time.perf_counter()
            res.generate_ms = (t2 - t1) * 1e3
            if write_back:
                res.cache_id = self.put(question, res.answer, write_scope or scope, embedding=res.embedding,
                                        metadata=metadata)
                res.write_ms = (time.perf_counter() - t2) * 1e3
        res.total_ms = (time.perf_counter() - t0) * 1e3
        return res

    # --- maintenance -------------------------------------------------------------------
    def invalidate(self, scope: dict | None = None) -> int:
        """Delete every entry matching the given scope values (all entries if scope is empty)."""
        scope = {k: v for k, v in (scope or {}).items() if k in self.cfg.scope_columns}
        where = " AND ".join(f"{c} = %s" for c in scope) or "TRUE"
        rows = self.backend.execute(
            f"WITH d AS (DELETE FROM {self.cfg.qualified_table} WHERE {where} RETURNING 1) SELECT count(*) AS n FROM d",
            list(scope.values()),
        )
        return int(rows[0]["n"])

    def purge_expired(self) -> int:
        rows = self.backend.execute(
            f"WITH d AS (DELETE FROM {self.cfg.qualified_table} WHERE expires_at <= now() RETURNING 1) "
            "SELECT count(*) AS n FROM d"
        )
        return int(rows[0]["n"])

    def stats(self) -> dict:
        return self.backend.execute(
            f"SELECT count(*) AS entries, coalesce(sum(hit_count), 0) AS total_hits, "
            f"count(*) FILTER (WHERE expires_at <= now()) AS expired FROM {self.cfg.qualified_table}"
        )[0]

    def close(self) -> None:
        self.backend.close()


def chat_generator(endpoint: str, system_prompt: str | None = None, workspace_client=None,
                   **query_kwargs) -> Generator:
    """A ``generate`` callable that answers with a Databricks chat serving endpoint and
    reports token usage."""
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.serving import ChatMessage, ChatMessageRole

    w = workspace_client or WorkspaceClient()

    def generate(question: str) -> Generation:
        messages = [ChatMessage(role=ChatMessageRole.SYSTEM, content=system_prompt)] if system_prompt else []
        messages.append(ChatMessage(role=ChatMessageRole.USER, content=question))
        resp = w.serving_endpoints.query(name=endpoint, messages=messages, **query_kwargs)
        usage = resp.usage
        return Generation(
            text=resp.choices[0].message.content,
            input_tokens=(usage.prompt_tokens or 0) if usage else 0,
            output_tokens=(usage.completion_tokens or 0) if usage else 0,
        )

    return generate
