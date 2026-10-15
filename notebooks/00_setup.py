# Databricks notebook source
# MAGIC %md
# MAGIC # 00 · Setup
# MAGIC
# MAGIC Creates everything the semantic cache needs and runs a smoke test:
# MAGIC
# MAGIC 1. Installs `databricks-lakebase-adapters` (from a UC Volume while the SDK is pre-PyPI).
# MAGIC 2. Checks the embedding and chat endpoints exist.
# MAGIC 3. Creates the UC schema (for evaluation / logging tables later).
# MAGIC 4. Creates the Lakebase cache table + vector index for the chosen backend.
# MAGIC 5. Puts one entry, looks it up with a paraphrase, then removes it.
# MAGIC
# MAGIC **Backends:** `pgvector` (default; HNSW, which indexes each new entry as it is written and works on
# MAGIC any Lakebase instance) or `lakebase_search` (native `lakebase_ann`, IVF + RaBitQ: for large, bulk-loaded
# MAGIC caches whose index is rebuilt periodically; requires Lakebase Search to be enabled for your
# MAGIC workspace and Lakebase project). Use the same `backend` in every notebook.

# COMMAND ----------

dbutils.widgets.text("catalog", "main")
dbutils.widgets.text("schema", "semantic_cache")
dbutils.widgets.text("sdk_wheel", "/Volumes/main/semantic_cache/libs/databricks_lakebase_adapters-<version>-py3-none-any.whl")
dbutils.widgets.text("lakebase_instance", "semantic-cache")
dbutils.widgets.dropdown("backend", "pgvector", ["pgvector", "lakebase_search"])
dbutils.widgets.text("pg_schema", "semantic_cache")   # Postgres schema for the cache tables
dbutils.widgets.text("embedding_endpoint", "databricks-qwen3-embedding-0-6b")
dbutils.widgets.text("llm_endpoint", "databricks-claude-opus-4-8")

# COMMAND ----------

sdk_wheel = dbutils.widgets.get("sdk_wheel")
%pip install -q "{sdk_wheel}[pgvector,lakebase-search]" "databricks-sdk>=0.86"
dbutils.library.restartPython()

# COMMAND ----------

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

# COMMAND ----------

# MAGIC %md ## Check endpoints and the Lakebase instance

# COMMAND ----------

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
for name in (cfg.embedding_endpoint, llm_endpoint):
    ep = w.serving_endpoints.get(name)
    print(f"{name}: {ep.state.ready}")

inst = w.database.get_database_instance(name=cfg.lakebase_instance)
print(f"Lakebase {inst.name}: {inst.state} · {inst.capacity} · {inst.read_write_dns}")

dim = len(w.serving_endpoints.query(name=cfg.embedding_endpoint, input=["dimension check"]).data[0].embedding)
assert dim == cfg.dimensions, f"{cfg.embedding_endpoint} returns {dim}-d vectors; set CacheConfig(dimensions={dim})"

# COMMAND ----------

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")

# COMMAND ----------

# MAGIC %md ## Create the cache table and index

# COMMAND ----------

cache = SemanticCache(cfg)
cache.backend.setup()

display(cache.backend.execute(
    "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = %s AND tablename = %s",
    [cfg.pg_schema, cfg.table],
))
cache.stats()

# COMMAND ----------

# MAGIC %md ## Smoke test
# MAGIC Uses a throwaway scope so it can't collide with real entries.

# COMMAND ----------

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
