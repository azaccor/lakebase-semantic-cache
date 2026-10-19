"""Configuration for a Lakebase-backed semantic cache."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")


def ident(name: str) -> str:
    """Validate a Postgres identifier we interpolate into DDL (schema/table/column names
    come from config, never from user input, but we still refuse anything unexpected)."""
    if not _IDENT.match(name):
        raise ValueError(f"Invalid identifier {name!r}: use lowercase letters, digits and _")
    return name


@dataclass
class CacheConfig:
    # --- Lakebase connection ---------------------------------------------------------
    lakebase_instance: str                    # Lakebase instance (== project id)
    database: str = "databricks_postgres"
    branch: str = "production"
    host: str | None = None                   # resolved from the instance when omitted
    # Service principal client id for Lakebase OAuth (secret from $DATABRICKS_CLIENT_SECRET). Needed
    # outside notebooks, e.g. in a Databricks App: pass $DATABRICKS_CLIENT_ID. None = notebook identity.
    client_id: str | None = None
    pool_max_size: int = 10                   # max pooled connections (raise for concurrent callers)

    # --- Storage ---------------------------------------------------------------------
    backend: str = "pgvector"                 # "pgvector" (HNSW) | "lakebase_search" (lakebase_ann)
    pg_schema: str = "semantic_cache"
    # Defaults to cache_entries_<backend>. Keep one table per backend: both indexes serve the
    # same `<=>` operator, so on a shared table the planner would pick either one.
    table: str | None = None

    # --- Embeddings ------------------------------------------------------------------
    embedding_endpoint: str = "databricks-qwen3-embedding-0-6b"
    dimensions: int = 1024

    # --- Matching --------------------------------------------------------------------
    similarity_threshold: float = 0.75        # cosine similarity required for a hit
    # A lookup only matches entries whose scope values are equal to the request's, so a
    # model or prompt change never serves another configuration's answer.
    scope_columns: tuple[str, ...] = ("model", "prompt_version", "tenant")
    default_ttl_seconds: int | None = None    # None = entries never expire
    track_hits: bool = True                   # bump hit_count / last_hit_at on every hit
    # A btree index on the scope columns speeds up invalidate(), but gives the planner an exact-but-slow
    # alternative (scan the scope, then sort) to the vector index for lookups. Off by default.
    scope_index: bool = False

    # --- Index builds / pgvector query tuning -----------------------------------------
    index_build_mem: str | None = None        # maintenance_work_mem for index builds, e.g. "4GB"
    # Postgres' cost model underprices 1024-d distance math, so for pgvector it picks a sequential
    # scan over HNSW well past 10K rows (41 ms vs 1 ms measured). When True, the cache's own
    # connections discourage sequential scans so lookups use the HNSW index.
    pgvector_prefer_index: bool = True
    hnsw_ef_search: int | None = None         # HNSW candidate list size (pgvector default 40)
    hnsw_m: int | None = None                 # HNSW build: links per node (pgvector default 16)
    hnsw_ef_construction: int | None = None   # HNSW build: candidate list size (pgvector default 64)

    extra: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.backend not in ("pgvector", "lakebase_search"):
            raise ValueError(f"Unknown backend {self.backend!r}")
        self.table = self.table or f"cache_entries_{self.backend}"
        for name in (self.pg_schema, self.table, *self.scope_columns):
            ident(name)

    @property
    def qualified_table(self) -> str:
        return f"{self.pg_schema}.{self.table}"
