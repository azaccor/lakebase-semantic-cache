"""Storage backends for the semantic cache, both built on databricks-lakebase-adapters.

- ``PgVectorBackend``       : pgvector + HNSW. The default: works on any Lakebase instance, and
                              HNSW indexes each new row as it is written, which suits a cache that
                              grows by one entry per miss.
- ``LakebaseSearchBackend`` : native Lakebase Search (``lakebase_ann``, IVF + RaBitQ). Faster and
                              more accurate than HNSW at every size in 03b_load_test (1K-1M), but
                              that was with the index rebuilt after each bulk load: IVF clusters
                              are learned at build time, so it needs periodic rebuilds as the cache
                              grows. Best for large, bulk-loaded caches. Requires Lakebase Search to
                              be enabled for the workspace and the Lakebase project.

Both use the same table layout, so an existing cache can be pointed at either backend.
The rest of the package only talks to the ``CacheBackend`` interface.
"""
from __future__ import annotations

import io
import json
import struct
import time
from abc import ABC, abstractmethod
from typing import Any

import numpy as np
from psycopg2.extras import Json

from .config import CacheConfig, ident

COLLECTION = "semantic_cache"


def connection_config(cfg: CacheConfig):
    """Build an SDK ConnectionConfig. On Databricks this uses the ambient identity to mint
    Lakebase OAuth credentials; off-platform set DATABRICKS_CONFIG_PROFILE first."""
    from lakebase.core import ConnectionConfig

    host = cfg.host
    if not host:
        from databricks.sdk import WorkspaceClient

        host = WorkspaceClient().database.get_database_instance(name=cfg.lakebase_instance).read_write_dns
    return ConnectionConfig.from_databricks(
        host=host, database=cfg.database, project_id=cfg.lakebase_instance, branch_id=cfg.branch,
        client_id=cfg.client_id or "", pool_max_size=cfg.pool_max_size,
    )


class CacheBackend(ABC):
    # True if the vector index must be rebuilt after a bulk load to stay accurate (IVF).
    rebuild_after_bulk_load = False

    def __init__(self, cfg: CacheConfig):
        self.cfg = cfg
        self.adapter = self._make_adapter(connection_config(cfg))
        self.adapter.initialize()

    # --- backend-specific ------------------------------------------------------------
    @abstractmethod
    def _make_adapter(self, conn_cfg): ...

    @abstractmethod
    def _ensure_extensions(self) -> None: ...

    @abstractmethod
    def _index_ddl(self, index_name: str):
        """CREATE INDEX statement (non-concurrent) for the vector index."""

    @abstractmethod
    def _search(self, query_vector: np.ndarray, filters, top_k: int) -> list[dict]:
        """Return rows (dicts) ordered by ascending cosine ``distance``."""

    # --- shared ----------------------------------------------------------------------
    @property
    def return_columns(self) -> list[str]:
        return ["question", "answer", *self.cfg.scope_columns, "metadata", "created_at", "expires_at"]

    def execute(self, sql: str, params: list | tuple | None = None) -> list[dict]:
        # PgVectorAdapter.execute_sql returns a DataFrame; SearchAdapter's returns list[dict].
        out = self.adapter.execute_sql(sql, params)
        return out.to_dict("records") if hasattr(out, "to_dict") else out

    def setup(self) -> None:
        """Idempotently create the extension(s), schema, cache table and indexes."""
        cfg, t = self.cfg, self.cfg.qualified_table
        self._ensure_extensions()
        self.execute(f"CREATE SCHEMA IF NOT EXISTS {cfg.pg_schema}")
        scope_ddl = "".join(f"  {c} text NOT NULL DEFAULT '',\n" for c in cfg.scope_columns)
        self.execute(
            f"""CREATE TABLE IF NOT EXISTS {t} (
  cache_id     text PRIMARY KEY,
  question     text NOT NULL,
  answer       text NOT NULL,
  embedding    vector({int(cfg.dimensions)}) NOT NULL,
{scope_ddl}  metadata     jsonb NOT NULL DEFAULT '{{}}'::jsonb,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now(),
  expires_at   timestamptz,
  hit_count    bigint NOT NULL DEFAULT 0,
  last_hit_at  timestamptz
)"""
        )
        if cfg.scope_index:
            self.execute(f"CREATE INDEX IF NOT EXISTS {cfg.table}_scope_idx ON {t} ({', '.join(cfg.scope_columns)})")
        else:
            self.execute(f"DROP INDEX IF EXISTS {cfg.pg_schema}.{cfg.table}_scope_idx")
        # Future LRU eviction.
        self.execute(f"CREATE INDEX IF NOT EXISTS {cfg.table}_last_hit_idx ON {t} (last_hit_at)")

        exists = self.execute(
            "SELECT 1 FROM pg_indexes WHERE schemaname = %s AND indexname = %s", [cfg.pg_schema, self.index_name]
        )
        if not exists:
            self.create_vector_index()

    @property
    def index_name(self) -> str:
        return ident(f"{self.cfg.table}_ann_idx")

    def _with_connection(self, fn):
        """Run ``fn(cursor)`` on one pooled connection, so session settings apply to it."""
        pool = self.adapter.pool
        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                return fn(cur)
        except Exception:
            pool.putconn(conn, discard=True)
            conn = None
            raise
        finally:
            if conn is not None:
                pool.putconn(conn)

    def create_vector_index(self) -> float:
        """Build the vector index; returns build seconds. Building after a bulk load is much
        faster than loading into an indexed table (and required for a good IVF index)."""
        def build(cur):
            if self.cfg.index_build_mem:
                cur.execute("SET maintenance_work_mem = %s", [self.cfg.index_build_mem])
            t0 = time.perf_counter()
            cur.execute(self._index_ddl(self.index_name))
            elapsed = time.perf_counter() - t0
            cur.execute("RESET maintenance_work_mem")
            return elapsed
        return self._with_connection(build)

    def drop_vector_index(self) -> None:
        self.execute(f"DROP INDEX IF EXISTS {self.cfg.pg_schema}.{self.index_name}")

    def index_size_bytes(self) -> int:
        rows = self.execute("SELECT pg_relation_size(to_regclass(%s)) AS b", [f"{self.cfg.pg_schema}.{self.index_name}"])
        return int(rows[0]["b"] or 0)

    def bulk_load(self, rows: list[dict]) -> int:
        """Fast insert of new entries (no upsert) via binary COPY. Same row shape as ``upsert``."""
        cfg = self.cfg
        cols = ["cache_id", "question", "answer", "embedding", *cfg.scope_columns, "metadata"]
        buf = io.BytesIO()
        buf.write(b"PGCOPY\n\xff\r\n\x00" + struct.pack("!ii", 0, 0))
        for r in rows:
            buf.write(struct.pack("!h", len(cols)))
            texts = [r["cache_id"], r["question"], r["answer"]]
            for t in texts:
                b = t.encode()
                buf.write(struct.pack("!i", len(b)) + b)
            vec = np.asarray(r["embedding"], dtype=">f4")
            # pgvector binary format: int16 dim, int16 unused, float4[dim]
            buf.write(struct.pack("!ihh", 4 + 4 * len(vec), len(vec), 0) + vec.tobytes())
            for c in cfg.scope_columns:
                b = str(r.get("scope", {}).get(c, "")).encode()
                buf.write(struct.pack("!i", len(b)) + b)
            b = b"\x01" + json.dumps(r.get("metadata") or {}).encode()   # jsonb binary: version 1 + text
            buf.write(struct.pack("!i", len(b)) + b)
        buf.write(struct.pack("!h", -1))
        buf.seek(0)
        self._with_connection(lambda cur: cur.copy_expert(
            f"COPY {cfg.qualified_table} ({', '.join(cols)}) FROM STDIN WITH (FORMAT binary)", buf))
        return len(rows)

    @abstractmethod
    def _search_sql(self, filters):
        """(sql, filter_params) of the top-1 lookup this backend runs."""

    def explain_lookup(self, query_vector, filters) -> list[str]:
        """EXPLAIN (COSTS OFF) of the real lookup query, on a cache connection (session settings apply)."""
        sql, fparams = self._search_sql(filters)
        v = np.asarray(query_vector, dtype=np.float32)
        def run(cur):
            cur.execute("EXPLAIN (COSTS OFF) " + (sql.as_string(cur) if hasattr(sql, "as_string") else sql),
                        [v, *fparams, v, 1])
            return [r[0] for r in cur.fetchall()]
        return self._with_connection(run)

    def row_count(self) -> int:
        return int(self.execute(f"SELECT count(*) AS n FROM {self.cfg.qualified_table}")[0]["n"])

    def sync_scope_from(self, source: "CacheBackend", scope: dict) -> int:
        """Replace this table's entries in ``scope`` with ``source``'s (tables in the same database).
        Lets several backends serve identical entries without re-calling the LLM."""
        cols = ["cache_id", "question", "answer", "embedding", *self.cfg.scope_columns, "metadata",
                "created_at", "updated_at", "expires_at", "hit_count", "last_hit_at"]
        where = " AND ".join(f"{c} = %s" for c in self.cfg.scope_columns)
        params = [str(scope.get(c, "")) for c in self.cfg.scope_columns]
        self.execute(f"DELETE FROM {self.cfg.qualified_table} WHERE {where}", params)
        self.execute(
            f"INSERT INTO {self.cfg.qualified_table} ({', '.join(cols)}) "
            f"SELECT {', '.join(cols)} FROM {source.cfg.qualified_table} WHERE {where}", params)
        return int(self.execute(f"SELECT count(*) AS n FROM {self.cfg.qualified_table} WHERE {where}", params)[0]["n"])

    def rebuild_index(self) -> None:
        """Rebuild the vector index. Needed for lakebase_ann (IVF) after a bulk load, since
        its clusters are learned from the rows present at build time; harmless for HNSW."""
        # Not adapter.reindex(): PgVectorAdapter quotes "schema.index" as a single identifier.
        self.execute(f"REINDEX INDEX {self.cfg.pg_schema}.{self.index_name}")

    def upsert(self, rows: list[dict]) -> int:
        """Insert or replace entries by ``cache_id``. Replacing an entry keeps its hit stats."""
        cfg = self.cfg
        cols = ["cache_id", "question", "answer", "embedding", *cfg.scope_columns, "metadata", "expires_at"]
        updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c != "cache_id")
        sql = (
            f"INSERT INTO {cfg.qualified_table} ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))}) "
            f"ON CONFLICT (cache_id) DO UPDATE SET {updates}, updated_at = now()"
        )
        params = [
            (
                r["cache_id"], r["question"], r["answer"], np.asarray(r["embedding"], dtype=np.float32),
                *(r.get("scope", {}).get(c, "") for c in cfg.scope_columns),
                Json(r.get("metadata") or {}), r.get("expires_at"),
            )
            for r in rows
        ]
        # Neither adapter exposes a batch upsert with custom conflict handling (and
        # SearchAdapter has no upsert at all), so use the shared batch executor.
        self.adapter._execute_batch(sql, params, page_size=200)
        return len(params)

    def search(self, query_vector, filters=None, top_k: int = 1) -> list[dict]:
        rows = self._search(np.asarray(query_vector, dtype=np.float32), filters, top_k)
        for r in rows:
            r["similarity"] = 1.0 - float(r["distance"])
        return rows

    def record_hit(self, cache_id: str) -> None:
        self.execute(
            f"UPDATE {self.cfg.qualified_table} SET hit_count = hit_count + 1, last_hit_at = now() "
            "WHERE cache_id = %s",
            [cache_id],
        )

    def close(self) -> None:
        self.adapter.close()


class PgVectorBackend(CacheBackend):
    def _make_adapter(self, conn_cfg):
        from lakebase.pgvector import PgVectorAdapter, VectorCollection

        settings = []
        if self.cfg.pgvector_prefer_index:
            settings.append("SET enable_seqscan = off")
        if self.cfg.hnsw_ef_search:
            settings.append(f"SET hnsw.ef_search = {int(self.cfg.hnsw_ef_search)}")

        class _Adapter(PgVectorAdapter):
            def on_pool_connect(self, conn) -> None:
                super().on_pool_connect(conn)
                if settings:
                    with conn.cursor() as cur:
                        for s in settings:
                            cur.execute(s)
                    if not conn.autocommit:
                        conn.commit()

        self._collection = VectorCollection(
            name=COLLECTION,
            table=self.cfg.qualified_table,
            vector_column="embedding",
            dimensions=self.cfg.dimensions,
            distance_metric="cosine",
            return_columns=self.return_columns,
            id_column="cache_id",
        )
        return _Adapter(conn_cfg, collections=[self._collection])

    def _ensure_extensions(self) -> None:
        self.adapter.ensure_extension()

    def _index_ddl(self, index_name: str):
        from lakebase.pgvector import IndexType
        from lakebase.pgvector.sql import build_create_index_sql

        return build_create_index_sql(self._collection, index_name=index_name, index_type=IndexType.HNSW,
                                      concurrent=False, m=self.cfg.hnsw_m,
                                      ef_construction=self.cfg.hnsw_ef_construction)

    def _search_sql(self, filters):
        from lakebase.pgvector.sql import build_search_sql

        return build_search_sql(self._collection, filters=filters, include_distance=True, include_vector=False)

    def _search(self, query_vector, filters, top_k) -> list[dict]:
        df = self.adapter.search(COLLECTION, query_vector, top_k=top_k, filters=filters, include_distance=True)
        return df.to_dict("records")


class LakebaseSearchBackend(CacheBackend):
    rebuild_after_bulk_load = True

    def _make_adapter(self, conn_cfg):
        from lakebase.lakebase_search import SearchAdapter, SearchCollection

        self._collection = SearchCollection(
            name=COLLECTION,
            table=self.cfg.qualified_table,
            vector_column="embedding",
            dimensions=self.cfg.dimensions,
            distance_metric="cosine",
            return_columns=self.return_columns,
            id_column="cache_id",
        )
        return SearchAdapter(conn_cfg, collections=[self._collection])

    def _ensure_extensions(self) -> None:
        # Installs lakebase_vector (CASCADE pulls in pgvector's `vector` type) and
        # lakebase_text; raises LakebaseSearchNotEnabledError with enablement steps if
        # the preview is off.
        self.adapter.ensure_extensions()

    def _index_ddl(self, index_name: str):
        from lakebase.lakebase_search.native.vector import build_create_ann_index_sql

        return build_create_ann_index_sql(self._collection, name=index_name, concurrent=False)

    def _search_sql(self, filters):
        from lakebase.lakebase_search.native.vector import build_vector_search_sql

        return build_vector_search_sql(self._collection, filters=filters, include_distance=True, include_vector=False)

    def _search(self, query_vector, filters, top_k) -> list[dict]:
        return self.adapter.vector_search(COLLECTION, query_vector, top_k=top_k, filters=filters)


def make_backend(cfg: CacheConfig) -> CacheBackend:
    return {"pgvector": PgVectorBackend, "lakebase_search": LakebaseSearchBackend}[cfg.backend](cfg)
