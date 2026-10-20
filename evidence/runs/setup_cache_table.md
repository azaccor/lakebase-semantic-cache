# Task `setup_cache_table` (job run 32232528631469)

Result: **SUCCESS**, 2026-10-20 00:59:13 UTC – 2026-10-20 01:00:08 UTC.

# 00 · Setup

Creates everything the semantic cache needs and runs a smoke test:

1. Installs `databricks-lakebase-adapters` (from a UC Volume while the SDK is pre-PyPI).
2. Checks the embedding and chat endpoints exist.
3. Creates the UC schema (for evaluation / logging tables later).
4. Creates the Lakebase cache table + vector index for the chosen backend.
5. Puts one entry, looks it up with a paraphrase, then removes it.

**Backends:** `pgvector` (default; HNSW, which indexes each new entry as it is written and works on
any Lakebase instance) or `lakebase_search` (native `lakebase_ann`, IVF + RaBitQ: for large, bulk-loaded
caches whose index is rebuilt periodically; requires Lakebase Search to be enabled for your
workspace and Lakebase project). Use the same `backend` in every notebook.

```python
dbutils.widgets.text("catalog", "main")
dbutils.widgets.text("schema", "semantic_cache")
dbutils.widgets.text("sdk_wheel", "/Volumes/main/semantic_cache/libs/databricks_lakebase_adapters-<version>-py3-none-any.whl")
dbutils.widgets.text("lakebase_instance", "semantic-cache")
dbutils.widgets.dropdown("backend", "pgvector", ["pgvector", "lakebase_search"])
dbutils.widgets.text("pg_schema", "semantic_cache")   # Postgres schema for the cache tables
dbutils.widgets.text("embedding_endpoint", "databricks-qwen3-embedding-0-6b")
dbutils.widgets.text("llm_endpoint", "databricks-claude-opus-4-8")
```

```python
sdk_wheel = dbutils.widgets.get("sdk_wheel")
%pip install -q "{sdk_wheel}[pgvector,lakebase-search]" "databricks-sdk>=0.86"
dbutils.library.restartPython()
```

```python
import os, sys

# Make the repo root importable (this notebook lives in <repo>/notebooks).
sys.path.insert(0, os.path.abspath(".."))

from semantic_cache import CacheConfig, SemanticCache

catalog, schema = dbutils.widgets.get("catalog"), dbutils.widgets.get("schema")
cfg = CacheConfig(
    lakebase_instance=dbutils.widgets.get("lakebase_instance"),
    backend=dbutils.widgets.get("backend"),
    pg_schema=dbutils.widgets.get("pg_schema"),
    embedding_endpoint=dbutils.widgets.get("embedding_endpoint"),
)
llm_endpoint = dbutils.widgets.get("llm_endpoint")
cfg
```

Output:

```text
CacheConfig(lakebase_instance='<redacted>', database='databricks_postgres', branch='production', host=None, client_id=None, pool_max_size=10, backend='pgvector', pg_schema='semantic_cache', table='cache_entries_pgvector', embedding_endpoint='databricks-qwen3-embedding-0-6b', dimensions=1024, similarity_threshold=0.75, scope_columns=('model', 'prompt_version', 'tenant'), default_ttl_seconds=None, track_hits=True, scope_index=False, index_build_mem=None, pgvector_prefer_index=True, hnsw_ef_search=None, hnsw_m=None, hnsw_ef_construction=None, extra={})
```

## Check endpoints and the Lakebase instance

```python
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
for name in (cfg.embedding_endpoint, llm_endpoint):
    ep = w.serving_endpoints.get(name)
    print(f"{name}: {ep.state.ready}")

inst = w.database.get_database_instance(name=cfg.lakebase_instance)
print(f"Lakebase {inst.name}: {inst.state} · {inst.capacity} · {inst.read_write_dns}")

dim = len(w.serving_endpoints.query(name=cfg.embedding_endpoint, input=["dimension check"]).data[0].embedding)
assert dim == cfg.dimensions, f"{cfg.embedding_endpoint} returns {dim}-d vectors; set CacheConfig(dimensions={dim})"
```

Output:

```text
databricks-qwen3-embedding-0-6b: EndpointStateReady.READY
databricks-claude-opus-4-8: EndpointStateReady.READY
Lakebase <redacted>: DatabaseInstanceState.AVAILABLE · CU_1 · <lakebase-endpoint>.database.us-east-1.cloud.databricks.com
```

```python
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")
```

Output:

```text
DataFrame[]
```

## Create the cache table and index

```python
cache = SemanticCache(cfg)
cache.backend.setup()

display(cache.backend.execute(
    "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = %s AND tablename = %s",
    [cfg.pg_schema, cfg.table],
))
cache.stats()
```

Output:

| indexdef | indexname |
|---|---|
| CREATE UNIQUE INDEX cache_entries_pgvector_pkey ON semantic_cache.cache_entries_pgvector USING btree (cache_id) | cache_entries_pgvector_pkey |
| CREATE INDEX cache_entries_pgvector_last_hit_idx ON semantic_cache.cache_entries_pgvector USING btree (last_hit_at) | cache_entries_pgvector_last_hit_idx |
| CREATE INDEX cache_entries_pgvector_ann_idx ON semantic_cache.cache_entries_pgvector USING hnsw (embedding vector_cosine_ops) | cache_entries_pgvector_ann_idx |

Output:

```text
{'entries': 51, 'total_hits': Decimal('53'), 'expired': 0}
```

## Smoke test
Uses a throwaway scope so it can't collide with real entries.

```python
scope = {"model": "smoke-test", "prompt_version": "v0", "tenant": "setup"}
cid = cache.put("How do I reset my password?",
                "Go to Settings → Security → Reset password and follow the emailed link.", scope)

hit = cache.lookup("I forgot my password, how can I change it?", scope)
miss_other_scope = cache.lookup("I forgot my password, how can I change it?", {**scope, "model": "other-model"})
unrelated = cache.lookup("What are your branch opening hours?", scope)

for label, r in [("paraphrase", hit), ("other scope", miss_other_scope), ("unrelated", unrelated)]:
    print(f"{label:12} hit={r.hit!s:5} sim={r.similarity} embed={r.embed_ms:.0f}ms lookup={r.lookup_ms:.0f}ms")

assert hit.hit and hit.cache_id == cid
assert not miss_other_scope.hit and miss_other_scope.similarity is None  # scope isolates entries
assert not unrelated.hit

print("removed", cache.invalidate(scope), "smoke-test entries")
cache.close()
```

Output:

```text
paraphrase   hit=True  sim=0.7879262205340335 embed=289ms lookup=11ms
other scope  hit=False sim=None embed=721ms lookup=9ms
unrelated    hit=False sim=0.3935864685054562 embed=180ms lookup=7ms
removed 1 smoke-test entries
```
