# Databricks notebook source
# MAGIC %md
# MAGIC # 03a · Scale data
# MAGIC
# MAGIC Builds a large set of real, embedded questions for the load test (`03b_load_test`). They act as
# MAGIC *distractor* cache entries: the 50 FAQs from `01_build_cache` have to be found among them.
# MAGIC
# MAGIC | Source | Rows | Role | License |
# MAGIC |---|---|---|---|
# MAGIC | [Bitext retail banking](https://huggingface.co/datasets/bitext/Bitext-retail-banking-llm-chatbot-training-dataset) | ~25K | In-domain banking questions: realistic near-misses | CDLA-Sharing-1.0 |
# MAGIC | [GooAQ](https://github.com/allenai/gooaq) ([HF mirror](https://huggingface.co/datasets/sentence-transformers/gooaq)) | ~3M | Real search questions, filler up to 1M | Apache-2.0 |
# MAGIC
# MAGIC Every row gets a deterministic `rank`, and all Bitext rows rank ahead of GooAQ rows, so a cache
# MAGIC of size N is always "the first N rows" and the banking near-misses are present at every size.
# MAGIC Embedding is **incremental**: raising `target_rows` only embeds the new rows. Embeddings are
# MAGIC computed in bulk with `ai_query()`, the same way you would seed a cache from an existing
# MAGIC inference or FAQ table.
# MAGIC
# MAGIC A held-out set of GooAQ questions (never loaded) is kept as realistic "miss" traffic for the load test.

# COMMAND ----------

dbutils.widgets.text("catalog", "main")
dbutils.widgets.text("schema", "semantic_cache")
dbutils.widgets.text("embedding_endpoint", "databricks-qwen3-embedding-0-6b")
dbutils.widgets.text("target_rows", "10000")
dbutils.widgets.text("holdout_rows", "2000")

catalog, schema = dbutils.widgets.get("catalog"), dbutils.widgets.get("schema")
endpoint = dbutils.widgets.get("embedding_endpoint")
target_rows, holdout_rows = int(dbutils.widgets.get("target_rows")), int(dbutils.widgets.get("holdout_rows"))
questions_table = f"{catalog}.{schema}.scale_questions"
embedded_table = f"{catalog}.{schema}.scale_embeddings"
raw_dir = f"/Volumes/{catalog}/{schema}/raw"

# COMMAND ----------

# MAGIC %md ## Download

# COMMAND ----------

import os, requests

spark.sql(f"CREATE VOLUME IF NOT EXISTS {catalog}.{schema}.raw")
FILES = {
    "bitext.parquet": "https://huggingface.co/api/datasets/bitext/Bitext-retail-banking-llm-chatbot-training-dataset/parquet/default/train/0.parquet",
    "gooaq_0.parquet": "https://huggingface.co/api/datasets/sentence-transformers/gooaq/parquet/pair/train/0.parquet",
    "gooaq_1.parquet": "https://huggingface.co/api/datasets/sentence-transformers/gooaq/parquet/pair/train/1.parquet",
}
for name, url in FILES.items():
    path = f"{raw_dir}/{name}"
    if os.path.exists(path):
        continue
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    print(f"downloaded {name}: {os.path.getsize(path) / 1e6:.0f} MB")

# COMMAND ----------

# MAGIC %md ## Rank questions (once)

# COMMAND ----------

if not spark.catalog.tableExists(questions_table):
    spark.sql(f"""
      CREATE TABLE {questions_table} AS
      WITH src AS (
        SELECT 'bitext' AS source, 0 AS source_order, trim(instruction) AS question,
               left(response, 500) AS answer, intent AS source_label
        FROM parquet.`{raw_dir}/bitext.parquet`
        UNION ALL
        SELECT 'gooaq', 1, trim(question), left(answer, 500), NULL
        FROM parquet.`{raw_dir}/gooaq_*.parquet`
      ),
      dedup AS (
        SELECT *, row_number() OVER (PARTITION BY lower(question) ORDER BY source_order) AS dup
        FROM src WHERE length(question) BETWEEN 5 AND 300
      )
      SELECT row_number() OVER (ORDER BY source_order, xxhash64(question)) - 1 AS rank,
             source, question, answer, source_label
      FROM dedup WHERE dup = 1
    """)
display(spark.sql(f"SELECT source, count(*) AS rows, min(rank), max(rank) FROM {questions_table} GROUP BY source"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Embed incrementally
# MAGIC Rows `0 … target_rows-1` become cache entries; the **last** `holdout_rows` GooAQ rows are the
# MAGIC held-out query pool (far from any loaded rank, so they stay held out as `target_rows` grows).

# COMMAND ----------

import time

total = spark.table(questions_table).count()
holdout_start = total - holdout_rows
assert target_rows <= holdout_start, "target_rows overlaps the held-out rows"

spark.sql(f"""CREATE TABLE IF NOT EXISTS {embedded_table}
              (rank BIGINT, source STRING, question STRING, answer STRING, source_label STRING,
               holdout BOOLEAN, embedding ARRAY<FLOAT>)""")
done = {r["holdout"]: r["n"] for r in spark.sql(
    f"SELECT holdout, count(*) AS n FROM {embedded_table} GROUP BY holdout").collect()}
print(f"already embedded: {done}")

t0 = time.time()
spark.sql(f"""
  INSERT INTO {embedded_table}
  SELECT q.rank, q.source, q.question, q.answer, q.source_label, q.rank >= {holdout_start} AS holdout,
         ai_query('{endpoint}', q.question) AS embedding
  FROM {questions_table} q
  LEFT ANTI JOIN {embedded_table} e ON q.rank = e.rank
  WHERE q.rank < {target_rows} OR q.rank >= {holdout_start}
""")
elapsed = time.time() - t0
n = spark.table(embedded_table).count()
new = n - sum(done.values())
print(f"embedded {new:,} new rows in {elapsed:.0f}s ({new / max(elapsed, 1):.0f} rows/s); table now {n:,} rows")

# COMMAND ----------

display(spark.sql(f"""
  SELECT holdout, source, count(*) AS rows, min(size(embedding)) AS dim, count_if(embedding IS NULL) AS failed
  FROM {embedded_table} GROUP BY ALL ORDER BY ALL
"""))
