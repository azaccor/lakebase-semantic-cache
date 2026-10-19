# Databricks notebook source
# MAGIC %md
# MAGIC # 01 · Build the cache
# MAGIC
# MAGIC Seeds the cache with answers to known FAQs by running them through the LLM endpoint
# MAGIC **via the cache itself** (`get_or_generate`), so seeding exercises the same code path as
# MAGIC live traffic and every request is logged to the `cache_events` Delta table.
# MAGIC
# MAGIC - **Dataset:** `data/question_bank.json`: 50 support FAQs for Lux Pay, a fictional consumer P2P money app,
# MAGIC   each with a canonical question, held-out paraphrases (used in `02_evaluate`) and a reference answer.
# MAGIC   Two account-specific intents are marked `cacheable: false` and are *not* seeded.
# MAGIC - **Scope:** every entry is tagged with the model and a `prompt_version` derived from a hash of
# MAGIC   the system prompt, so editing the prompt automatically starts a fresh cache partition.
# MAGIC - **Idempotent:** seeding uses a 0.99 threshold, so only an (almost) identical question counts as
# MAGIC   already cached. Re-running costs nothing; similar-but-different FAQs don't block each other.

# COMMAND ----------

dbutils.widgets.text("catalog", "main")
dbutils.widgets.text("schema", "semantic_cache")
dbutils.widgets.text("sdk_wheel", "/Volumes/main/semantic_cache/libs/databricks_lakebase_adapters-<version>-py3-none-any.whl")
dbutils.widgets.text("lakebase_instance", "semantic-cache")
dbutils.widgets.dropdown("backend", "pgvector", ["pgvector", "lakebase_search"])
dbutils.widgets.text("pg_schema", "semantic_cache")   # Postgres schema for the cache tables
dbutils.widgets.text("embedding_endpoint", "databricks-qwen3-embedding-0-6b")
dbutils.widgets.text("llm_endpoint", "databricks-claude-opus-4-8")
# USD per 1M tokens: list-price assumptions for cost estimates; adjust to your contract.
dbutils.widgets.text("price_in_per_m", "5")
dbutils.widgets.text("price_out_per_m", "25")

# COMMAND ----------

sdk_wheel = dbutils.widgets.get("sdk_wheel")
%pip install -q "{sdk_wheel}[pgvector,lakebase-search]" "databricks-sdk>=0.86"
dbutils.library.restartPython()

# COMMAND ----------

import hashlib, json, os, sys, uuid

sys.path.insert(0, os.path.abspath(".."))
from semantic_cache import CacheConfig, SemanticCache, chat_generator, log_events

catalog, schema = dbutils.widgets.get("catalog"), dbutils.widgets.get("schema")
events_table = f"{catalog}.{schema}.cache_events"
llm_endpoint = dbutils.widgets.get("llm_endpoint")
price_in, price_out = float(dbutils.widgets.get("price_in_per_m")), float(dbutils.widgets.get("price_out_per_m"))

cfg = CacheConfig(
    lakebase_instance=dbutils.widgets.get("lakebase_instance"),
    backend=dbutils.widgets.get("backend"),
    pg_schema=dbutils.widgets.get("pg_schema"),
    embedding_endpoint=dbutils.widgets.get("embedding_endpoint"),
)
cache = SemanticCache(cfg)

# COMMAND ----------

# Shared with 02_evaluate and the app: the prompt's hash is part of the cache scope.
with open("../data/system_prompt.txt") as f:
    SYSTEM_PROMPT = f.read().strip()
scope = {
    "model": llm_endpoint,
    "prompt_version": hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()[:8],
    "tenant": "",
}
generate = chat_generator(llm_endpoint, system_prompt=SYSTEM_PROMPT, max_tokens=400)
scope

# COMMAND ----------

with open("../data/question_bank.json") as f:
    bank = json.load(f)
seed = [i for i in bank["intents"] if i["cacheable"]]
print(f"{bank['persona']}: {len(seed)} cacheable intents to seed")

# COMMAND ----------

# MAGIC %md ## Seed

# COMMAND ----------

run_id = str(uuid.uuid4())
results = []
for intent in seed:
    r = cache.get_or_generate(
        intent["canonical_question"], generate, scope, threshold=0.99,
        metadata={"intent_id": intent["intent_id"], "category": intent["category"], "source": "seed"},
    )
    results.append(r)
    print(f"{'cached ' if r.hit else 'seeded '} {r.total_ms:7.0f} ms  {intent['canonical_question']}")

log_events(spark, events_table, results, run_id=run_id, source="01_build_cache", backend=cfg.backend,
           price_in_per_m=price_in, price_out_per_m=price_out,
           attributes=[{"intent_id": i["intent_id"]} for i in seed])

# `lakebase_ann` is an IVF index: it learns its clusters from the rows present when it is built,
# and 00_setup built it on an empty table. Rebuilding after the initial seed is cheap at this size.
# (In production, rebuild periodically as the cache grows; HNSW doesn't need this.)
if cache.backend.rebuild_after_bulk_load and cache.backend.row_count() < 100_000:
    cache.backend.rebuild_index()

# COMMAND ----------

# MAGIC %md ## Summary

# COMMAND ----------

display(spark.sql(f"""
  SELECT count(*)                                   AS requests,
         count_if(NOT hit)                          AS llm_calls,
         round(avg(IF(NOT hit, generate_ms, NULL))) AS avg_llm_ms,
         round(avg(embed_ms))                       AS avg_embed_ms,
         round(avg(lookup_ms), 1)                   AS avg_lookup_ms,
         sum(input_tokens)                          AS input_tokens,
         sum(output_tokens)                         AS output_tokens,
         round(sum(cost_usd), 3)                    AS llm_cost_usd,
         round(avg(IF(NOT hit, cost_usd, NULL)), 4) AS cost_per_llm_call_usd
  FROM {events_table} WHERE run_id = '{run_id}'
"""))
cache.stats()

# COMMAND ----------

display(cache.backend.execute(
    f"SELECT metadata->>'intent_id' AS intent_id, question, left(answer, 160) AS answer "
    f"FROM {cfg.qualified_table} WHERE model = %s AND prompt_version = %s ORDER BY 1",
    [scope["model"], scope["prompt_version"]],
))

# COMMAND ----------

cache.close()
