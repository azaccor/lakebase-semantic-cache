# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "6"
# ///
# MAGIC %md
# MAGIC # 02 · Evaluate
# MAGIC
# MAGIC How much would the cache save, and how often would it serve a wrong answer?
# MAGIC
# MAGIC 1. **Queries** (`silver_eval_questions`): the 167 held-out paraphrases of the seeded FAQs, plus the
# MAGIC    account-specific questions (`cacheable: false`), which should *never* hit.
# MAGIC 2. **Lookup:** each query is embedded once and looked up on every backend, recording the
# MAGIC    nearest in-scope entry and its similarity (no threshold applied yet; nothing is written).
# MAGIC 3. **Threshold sweep:** at each threshold, a lookup is a hit if similarity ≥ threshold, and a
# MAGIC    hit is *correct* if the matched entry answers the same FAQ (intent) as the query.
# MAGIC 4. **Savings:** cost and latency are projected from the Opus latency and token cost measured
# MAGIC    in `01_build_cache` (so this notebook makes no LLM calls), plus the measured embed + lookup
# MAGIC    overhead that every request pays.
# MAGIC
# MAGIC Run `01_build_cache` first. List one backend or both in `backends`: if several are listed, the
# MAGIC entries `01_build_cache` seeded (in whichever backend it used) are copied to the others, so every
# MAGIC backend is scored on identical data without calling the LLM again.

# COMMAND ----------

dbutils.widgets.text("catalog", "main")
dbutils.widgets.text("schema", "semantic_cache")
dbutils.widgets.text("sdk_wheel", "/Volumes/main/semantic_cache/libs/databricks_lakebase_adapters-<version>-py3-none-any.whl")
dbutils.widgets.text("lakebase_instance", "semantic-cache")
dbutils.widgets.text("backends", "pgvector")   # e.g. "pgvector,lakebase_search" to compare
dbutils.widgets.text("pg_schema", "semantic_cache")
dbutils.widgets.text("embedding_endpoint", "databricks-qwen3-embedding-0-6b")
dbutils.widgets.text("llm_endpoint", "databricks-claude-opus-4-8")
dbutils.widgets.text("threshold", "0.75")
dbutils.widgets.text("price_in_per_m", "5")     # $ per 1M tokens, list price of the llm_endpoint
dbutils.widgets.text("price_out_per_m", "25")

# COMMAND ----------

sdk_wheel = dbutils.widgets.get("sdk_wheel")
%pip install -q "{sdk_wheel}[pgvector,lakebase-search]" "databricks-sdk>=0.86" plotly
dbutils.library.restartPython()

# COMMAND ----------

import hashlib, json, os, re, sys, uuid
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(".."))
from semantic_cache import CacheConfig, SemanticCache

catalog, schema = dbutils.widgets.get("catalog"), dbutils.widgets.get("schema")
backends = [b.strip() for b in dbutils.widgets.get("backends").split(",") if b.strip()]
llm_endpoint = dbutils.widgets.get("llm_endpoint")
default_threshold = float(dbutils.widgets.get("threshold"))
run_id = str(uuid.uuid4())
run_ts = pd.Timestamp.now(tz="UTC")   # lets readers (e.g. the app) pick the latest run

# Same system prompt, so the same scope, as 01_build_cache.
with open("../data/system_prompt.txt") as f:
    SYSTEM_PROMPT = f.read().strip()
scope = {"model": llm_endpoint, "prompt_version": hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()[:8], "tenant": ""}

def make_cache(backend):
    # track_hits=False: evaluation lookups must not count as real cache hits.
    return SemanticCache(CacheConfig(
        lakebase_instance=dbutils.widgets.get("lakebase_instance"), backend=backend,
        pg_schema=dbutils.widgets.get("pg_schema"),
        embedding_endpoint=dbutils.widgets.get("embedding_endpoint"), track_hits=False,
    ))

caches = {b: make_cache(b) for b in backends}

# COMMAND ----------

# MAGIC %md ## Prepare backends
# MAGIC The backend with the most entries in this scope is the one `01_build_cache` seeded; its entries are
# MAGIC copied to any other listed backend. Small `lakebase_search` tables then get their vector index rebuilt:
# MAGIC `lakebase_ann` (IVF) learns its clusters from the rows present when the index is built.

# COMMAND ----------

def in_scope(c):
    where = " AND ".join(f"{col} = %s" for col in c.cfg.scope_columns)
    return c.backend.execute(f"SELECT count(*) AS n FROM {c.cfg.qualified_table} WHERE {where}",
                             [scope[col] for col in c.cfg.scope_columns])[0]["n"]

for c in caches.values():
    c.backend.setup()
counts = {b: in_scope(c) for b, c in caches.items()}
seeded = max(counts, key=counts.get)
assert counts[seeded] > 0, f"No seeded entries in this scope for {backends}: run 01_build_cache first"
source = caches[seeded]
for b, c in caches.items():
    if b != seeded and counts[b] != counts[seeded]:
        c.backend.sync_scope_from(source.backend, scope)
        if c.backend.rebuild_after_bulk_load and c.backend.row_count() < 100_000:
            c.backend.rebuild_index()
for b, c in caches.items():
    print(f"{b:16} {in_scope(c)} entries in scope" + ("  (seeded by 01_build_cache)" if b == seeded else ""))

# COMMAND ----------

# MAGIC %md ## Build the query set

# COMMAND ----------

# Built by the semantic_cache_ingest pipeline: paraphrases labeled with their FAQ, and account-specific
# probes (expected_intent NULL), where any hit would serve a generic (wrong) answer.
queries = [r.asDict() for r in spark.table(f"{catalog}.{schema}.silver_eval_questions")
           .select("question", "expected_intent", "cacheable").orderBy("question").collect()]
qdf = pd.DataFrame(queries)
qdf.groupby("cacheable").size()

# COMMAND ----------

# MAGIC %md ## Look up every query on every backend
# MAGIC Each query also gets its **leave-one-FAQ-out** similarity: the nearest seeded entry excluding its own
# MAGIC FAQ (exact search over the seeded entries). That simulates an in-domain question whose answer is *not*
# MAGIC cached, which is what most non-repeat traffic looks like: any hit on it serves a wrong answer.
# MAGIC Account-specific probes have no FAQ, so theirs is their ordinary nearest entry.

# COMMAND ----------

import time

where = " AND ".join(f"{c} = %s" for c in source.cfg.scope_columns)
entries = source.backend.execute(
    f"SELECT embedding::text AS emb, metadata->>'intent_id' AS intent_id FROM {source.cfg.qualified_table} WHERE {where}",
    [scope[c] for c in source.cfg.scope_columns])
seeded_vecs = np.asarray([json.loads(r["emb"]) for r in entries], dtype=np.float32)
seeded_vecs /= np.linalg.norm(seeded_vecs, axis=1, keepdims=True)
seeded_intents = np.asarray([r["intent_id"] for r in entries], dtype=object)

def novel_similarity(emb, expected_intent):
    v = np.asarray(emb, dtype=np.float32)
    sims = seeded_vecs @ (v / np.linalg.norm(v))
    return float(sims[seeded_intents != expected_intent].max())

rows = []
for q in queries:
    t0 = time.perf_counter()
    emb = source.embed([q["question"]])[0]          # one real single-query embedding call
    embed_ms = (time.perf_counter() - t0) * 1e3
    novel_sim = novel_similarity(emb, q["expected_intent"])
    for b, c in caches.items():
        r = c.lookup(q["question"], scope, threshold=0.0, embedding=emb)
        rows.append({
            **q, "backend": b, "similarity": r.similarity,
            "matched_intent": (r.matched_metadata or {}).get("intent_id"),
            "matched_question": r.matched_question,
            "embed_ms": embed_ms, "lookup_ms": r.lookup_ms, "novel_similarity": novel_sim,
        })
res = pd.DataFrame(rows)
res["match_correct"] = res["matched_intent"] == res["expected_intent"]
spark.createDataFrame(res.assign(run_id=run_id, run_ts=run_ts)).write.mode("append").option("mergeSchema", "true") \
    .saveAsTable(f"{catalog}.{schema}.eval_lookups")
res.head()

# COMMAND ----------

# MAGIC %md ## Backend comparison
# MAGIC Do both backends return the same nearest entry, and how fast is the lookup?

# COMMAND ----------

wide = res.pivot_table(index="question", columns="backend", values="matched_intent", aggfunc="first")
if len(backends) > 1:
    agree = (wide[backends].nunique(axis=1) == 1).mean()
    print(f"Backends return the same nearest entry for {agree:.1%} of queries")

display(res.groupby("backend").agg(
    queries=("question", "count"),
    lookup_p50_ms=("lookup_ms", "median"),
    lookup_p95_ms=("lookup_ms", lambda s: s.quantile(0.95)),
    embed_p50_ms=("embed_ms", "median"),
    embed_p95_ms=("embed_ms", lambda s: s.quantile(0.95)),
    nearest_correct=("match_correct", "mean"),
).round(3).reset_index())

# COMMAND ----------

# Which plan does Postgres pick? On a small cache a sequential scan is cheaper than any index,
# so both backends may show a Seq Scan here; the ANN index starts to matter at larger sizes.
probe = np.asarray(source.embed(["plan check"])[0], dtype=np.float32)
for b, c in caches.items():
    plan = c.backend.execute(
        f"EXPLAIN (COSTS OFF) SELECT cache_id FROM {c.cfg.qualified_table} ORDER BY embedding <=> %s LIMIT 1",
        [probe])
    print(b, "\n  " + "\n  ".join(re.sub(r"'\[[^']*\]'", "'[...]'", r["QUERY PLAN"]) for r in plan))

# COMMAND ----------

# MAGIC %md ## Threshold sweep

# COMMAND ----------

def sweep(df, thresholds):
    out = []
    for t in thresholds:
        hit = df["similarity"] >= t
        correct = hit & df["match_correct"]
        out.append({
            "threshold": round(t, 2),
            "hit_rate": hit.mean(),
            "precision": correct.sum() / hit.sum() if hit.sum() else np.nan,
            "false_hit_rate": (hit & ~df["match_correct"]).mean(),
            "cacheable_hit_rate": hit[df["cacheable"]].mean(),
            # Wrong answers per repeat question, and per question whose answer isn't cached (leave-one-FAQ-out
            # + account-specific probes). Fixed denominators, so both only fall as the threshold rises.
            "cacheable_false_hit_rate": (hit & ~df["match_correct"])[df["cacheable"]].mean(),
            "novel_hit_rate": (df["novel_similarity"] >= t).mean(),
            "account_specific_hits": int(hit[~df["cacheable"]].sum()),
        })
    return pd.DataFrame(out)

thresholds = np.arange(0.50, 0.96, 0.05)
sweeps = pd.concat([sweep(res[res.backend == b], thresholds).assign(backend=b) for b in backends])
spark.createDataFrame(sweeps.assign(run_id=run_id, run_ts=run_ts)).write.mode("append").option("mergeSchema", "true") \
    .saveAsTable(f"{catalog}.{schema}.eval_threshold_sweep")
display(sweeps.round(3))

# COMMAND ----------

import plotly.graph_objects as go

base = sweeps[sweeps.backend == backends[0]]
INK, MUTED, GRID = "#1f1f1e", "#6b6a64", "#e8e7e2"
fig = go.Figure()
for col, name, color in [("precision", "Precision", "#2a78d6"), ("hit_rate", "Hit rate", "#eb6834")]:
    fig.add_trace(go.Scatter(
        x=base["threshold"], y=base[col] * 100, name=name, mode="lines+markers",
        line=dict(color=color, width=2), marker=dict(size=8, color=color, line=dict(color="#fcfcfb", width=2)),
        hovertemplate=f"{name}: %{{y:.1f}}%<br>threshold %{{x:.2f}}<extra></extra>",
    ))
    last = base.dropna(subset=[col]).iloc[-1]
    fig.add_annotation(x=last["threshold"], y=last[col] * 100, text=name, showarrow=False,
                       xanchor="left", xshift=10, font=dict(color=INK, size=12))
fig.add_shape(type="line", x0=default_threshold, x1=default_threshold, y0=0, y1=106, line=dict(color=MUTED, width=1, dash="dot"))
fig.add_annotation(x=default_threshold, y=110, text=f"default {default_threshold:.2f}", showarrow=False,
                   yanchor="bottom", font=dict(color=MUTED, size=11))
fig.update_layout(
    title=dict(text=f"Hit rate vs precision by similarity threshold ({backends[0]})", font=dict(color=INK)),
    plot_bgcolor="#fcfcfb", paper_bgcolor="#fcfcfb", font=dict(color=MUTED), hovermode="x unified",
    xaxis=dict(title="Similarity threshold", gridcolor=GRID, zeroline=False),
    yaxis=dict(title="%", range=[0, 116], gridcolor=GRID, zeroline=False),
    legend=dict(orientation="h", y=-0.2), margin=dict(r=90), height=420,
)
fig.show()

# COMMAND ----------

# MAGIC %md ## Savings at the chosen threshold
# MAGIC Baseline = every request calls the LLM. With the cache, every request pays embed + lookup, and
# MAGIC misses additionally pay the LLM call and a cache write. LLM latency/cost come from the
# MAGIC `01_build_cache` misses in this scope (model + system prompt version, since the prompt sets the input
# MAGIC tokens); embedding cost is not included.

# COMMAND ----------

events = (spark.table(f"{catalog}.{schema}.cache_events")
          .where("NOT hit AND input_tokens > 0")
          .where(f"scope['model'] = '{scope['model']}' AND scope['prompt_version'] = '{scope['prompt_version']}'")
          .toPandas())
price_in, price_out = float(dbutils.widgets.get("price_in_per_m")), float(dbutils.widgets.get("price_out_per_m"))
llm_ms, write_ms = events["generate_ms"].mean(), events["write_ms"].mean()
llm_cost = (events["input_tokens"].mean() * price_in + events["output_tokens"].mean() * price_out) / 1e6

summary = []
for b in backends:
    r = res[res.backend == b]
    s = sweep(r, [default_threshold]).iloc[0]
    overhead = r["embed_ms"].mean() + r["lookup_ms"].mean()
    summary.append({
        "backend": b, "threshold": default_threshold,
        "hit_rate": s.hit_rate, "precision": s.precision, "false_hit_rate": s.false_hit_rate,
        "account_specific_hits": s.account_specific_hits,
        "baseline_ms": llm_ms,
        "cached_avg_ms": overhead + (1 - s.hit_rate) * (llm_ms + write_ms),
        "hit_ms": overhead, "miss_ms": overhead + llm_ms + write_ms,
        "baseline_cost_per_1k": llm_cost * 1000,
        "cached_cost_per_1k": (1 - s.hit_rate) * llm_cost * 1000,
    })
summary = pd.DataFrame(summary)
summary["latency_saved_pct"] = 1 - summary.cached_avg_ms / summary.baseline_ms
summary["cost_saved_pct"] = 1 - summary.cached_cost_per_1k / summary.baseline_cost_per_1k
spark.createDataFrame(summary.assign(run_id=run_id, run_ts=run_ts)).write.mode("append").option("mergeSchema", "true") \
    .saveAsTable(f"{catalog}.{schema}.eval_summary")
display(summary.round(3))

# COMMAND ----------

# MAGIC %md ## Wrong answers at the chosen threshold
# MAGIC Hits whose matched entry is a different FAQ: what the cache would have served incorrectly.

# COMMAND ----------

r = res[res.backend == backends[0]]
display(r[(r.similarity >= default_threshold) & ~r.match_correct]
        [["question", "expected_intent", "matched_question", "matched_intent", "similarity"]]
        .sort_values("similarity", ascending=False))

# COMMAND ----------

for c in caches.values():
    c.close()
