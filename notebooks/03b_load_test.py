# Databricks notebook source
# MAGIC %md
# MAGIC # 03b · Load test
# MAGIC
# MAGIC How do the two backends behave as the cache grows? At each cache size (1K → 1M entries) this
# MAGIC notebook measures, for `pgvector` (HNSW) and `lakebase_search` (`lakebase_ann`, IVF + RaBitQ):
# MAGIC
# MAGIC 1. **Index build:** time and size after a bulk load.
# MAGIC 2. **Cache accuracy:** the `02_evaluate` queries, now competing with N distractor entries. More
# MAGIC    entries → more chances for a wrong hit, so the right threshold can move as the cache grows.
# MAGIC 3. **ANN quality** vs exact search (numpy), for *near* queries (the paraphrases) and *far* ones
# MAGIC    (held-out search questions): recall@1 (same entry as exact), similarity gap (how much less
# MAGIC    similar the ANN result is), and decision agreement (same hit/miss at the threshold, which is
# MAGIC    what a cache actually cares about). On dense clusters of near-duplicate questions recall@1
# MAGIC    alone is harsh: a different entry with 0.001 lower similarity is just as good an answer.
# MAGIC    pgvector is also swept over `hnsw.ef_search`.
# MAGIC 4. **Latency & throughput:** the cache's real lookup query (top-1, scope-filtered) from 1–32
# MAGIC    concurrent clients. Query embeddings are precomputed, so this isolates Lakebase; add the
# MAGIC    embedding call (~200 ms) for end-to-end lookup latency. Each backend gets a 15 s untimed warm-up
# MAGIC    first, and the query plan of the lookup is recorded so you can see which index served it.
# MAGIC
# MAGIC Distractors come from `03a_scale_data` (run it first with `target_rows` ≥ the largest size).
# MAGIC Sizes are cumulative: each step appends rows to both tables and rebuilds the indexes.
# MAGIC Lakebase compute autoscales (CU range set on the project), so note it when comparing runs.

# COMMAND ----------

dbutils.widgets.text("catalog", "main")
dbutils.widgets.text("schema", "semantic_cache")
dbutils.widgets.text("sdk_wheel", "/Volumes/main/semantic_cache/libs/databricks_lakebase_adapters-<version>-py3-none-any.whl")
dbutils.widgets.text("lakebase_instance", "semantic-cache")
dbutils.widgets.text("backends", "pgvector,lakebase_search")
dbutils.widgets.text("embedding_endpoint", "databricks-qwen3-embedding-0-6b")
dbutils.widgets.text("llm_endpoint", "databricks-claude-opus-4-8")
dbutils.widgets.text("sizes", "1000,10000,100000,1000000")
dbutils.widgets.text("concurrency", "1,4,16,32")
dbutils.widgets.text("duration_s", "30")
dbutils.widgets.text("index_build_mem", "4GB")
dbutils.widgets.text("hnsw_ef_search", "100")
dbutils.widgets.text("hnsw_m", "16")
dbutils.widgets.text("hnsw_ef_construction", "64")
dbutils.widgets.text("ef_search_sweep", "40,100,200,400")
dbutils.widgets.text("threshold", "0.75")

# COMMAND ----------

sdk_wheel = dbutils.widgets.get("sdk_wheel")
%pip install -q "{sdk_wheel}[pgvector,lakebase-search]" "databricks-sdk>=0.86" plotly
dbutils.library.restartPython()

# COMMAND ----------

import hashlib, json, os, random, sys, threading, time, uuid
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(".."))
from semantic_cache import CacheConfig, SemanticCache

catalog, schema = dbutils.widgets.get("catalog"), dbutils.widgets.get("schema")
backends = [b.strip() for b in dbutils.widgets.get("backends").split(",") if b.strip()]
concurrency = [int(c) for c in dbutils.widgets.get("concurrency").split(",")]
duration_s = int(dbutils.widgets.get("duration_s"))
threshold = float(dbutils.widgets.get("threshold"))
embedded_table = f"{catalog}.{schema}.scale_embeddings"
run_id = str(uuid.uuid4())

available = spark.sql(f"SELECT count(*) AS n FROM {embedded_table} WHERE NOT holdout").first()["n"]
sizes = sorted(s for s in (int(x) for x in dbutils.widgets.get("sizes").split(",")) if s <= available)
print(f"{available:,} embedded distractors available → sizes {sizes}")

# Shared with the other notebooks and the app: the prompt's hash is part of the cache scope.
with open("../data/system_prompt.txt") as f:
    SYSTEM_PROMPT = f.read().strip()
scope = {"model": dbutils.widgets.get("llm_endpoint"),
         "prompt_version": hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()[:8], "tenant": ""}

caches = {b: SemanticCache(CacheConfig(
    lakebase_instance=dbutils.widgets.get("lakebase_instance"), backend=b,
    embedding_endpoint=dbutils.widgets.get("embedding_endpoint"), track_hits=False,
    pool_max_size=max(concurrency) + 4, index_build_mem=dbutils.widgets.get("index_build_mem") or None,
    hnsw_ef_search=int(dbutils.widgets.get("hnsw_ef_search")),
    hnsw_m=int(dbutils.widgets.get("hnsw_m")), hnsw_ef_construction=int(dbutils.widgets.get("hnsw_ef_construction")),
)) for b in backends}
for c in caches.values():
    c.backend.setup()

# COMMAND ----------

# MAGIC %md ## Queries and the FAQ entries

# COMMAND ----------

any_cache = next(iter(caches.values()))
with open("../data/question_bank.json") as f:
    bank = json.load(f)
eval_q = []
for i in bank["intents"]:
    qs = i["paraphrases"] if i["cacheable"] else [i["canonical_question"], *i["paraphrases"]]
    eval_q += [{"question": q, "expected_intent": i["intent_id"] if i["cacheable"] else None} for q in qs]
eval_vecs = np.asarray(any_cache.embed([q["question"] for q in eval_q]), dtype=np.float32)

holdout = spark.sql(f"SELECT question, embedding FROM {embedded_table} WHERE holdout").toPandas()
holdout_vecs = np.stack(holdout["embedding"].map(lambda v: np.asarray(v, dtype=np.float32)))

# Queries used for recall and latency: the eval paraphrases (mostly near an entry) + held-out
# search questions (mostly misses), like real traffic.
query_vecs = np.vstack([eval_vecs, holdout_vecs[:300]])
traffic_vecs = np.vstack([eval_vecs, holdout_vecs])

# The seeded FAQ entries (same in every backend table).
faq = any_cache.backend.execute(
    f"SELECT cache_id, embedding::text AS emb FROM {any_cache.cfg.qualified_table} "
    "WHERE model = %s AND prompt_version = %s AND cache_id NOT LIKE 'scale-%%'",
    [scope["model"], scope["prompt_version"]])
faq_ids = [r["cache_id"] for r in faq]
faq_vecs = np.asarray([json.loads(r["emb"]) for r in faq], dtype=np.float32)
print(f"{len(eval_q)} eval queries, {len(holdout)} held-out queries, {len(faq_ids)} FAQ entries")

# COMMAND ----------

# MAGIC %md ## Helpers

# COMMAND ----------

def unit(m):
    return m / np.linalg.norm(m, axis=1, keepdims=True)

qn = unit(query_vecs)
# Running exact top-1 over everything loaded so far (FAQ entries + distractor prefix).
sims = qn @ unit(faq_vecs).T
best_sim, best_id = sims.max(axis=1), np.asarray(faq_ids, dtype=object)[sims.argmax(axis=1)]

def load_and_track(start, stop, chunk=20_000):
    """Append distractor ranks [start, stop) to every backend table and update exact top-1."""
    global best_sim, best_id
    for lo in range(start, stop, chunk):
        hi = min(lo + chunk, stop)
        pdf = spark.sql(f"""SELECT rank, source, source_label, question, answer, embedding FROM {embedded_table}
                            WHERE NOT holdout AND rank >= {lo} AND rank < {hi}""").toPandas()
        vecs = np.stack(pdf["embedding"].map(lambda v: np.asarray(v, dtype=np.float32)))
        ids = np.asarray([f"scale-{r}" for r in pdf["rank"]], dtype=object)
        rows = [{"cache_id": cid, "question": q, "answer": a, "embedding": v, "scope": scope,
                 "metadata": {"source": s, "label": l}}
                for cid, q, a, v, s, l in zip(ids, pdf["question"], pdf["answer"], vecs, pdf["source"], pdf["source_label"])]
        for c in caches.values():
            c.backend.bulk_load(rows)
        s = qn @ unit(vecs).T
        better = s.max(axis=1) > best_sim
        best_sim = np.where(better, s.max(axis=1), best_sim)
        best_id = np.where(better, ids[s.argmax(axis=1)], best_id)
        print(f"  loaded ranks {lo:,}–{hi:,}")

n_near = len(eval_q)

def ann_quality(ann_ids, ann_sims):
    """ANN vs exact top-1, split into near (eval paraphrases) and far (held-out) queries."""
    ann_ids, ann_sims = np.asarray(ann_ids, dtype=object), np.asarray(ann_sims, dtype=float)
    out = {}
    for part, sl in [("near", slice(0, n_near)), ("far", slice(n_near, None))]:
        a_id, a_sim, e_id, e_sim = ann_ids[sl], ann_sims[sl], best_id[sl], best_sim[sl]
        out[f"{part}_recall_at_1"] = np.mean(a_id == e_id)
        out[f"{part}_sim_gap"] = np.mean(e_sim - a_sim)
        out[f"{part}_decision_agree"] = np.mean((a_sim >= threshold) == (e_sim >= threshold))
    return out

def pgvector_sweep(cache, ef_values):
    """Top-1 under different hnsw.ef_search values (SET LOCAL per query, index forced)."""
    sql = f"SELECT cache_id, 1 - (embedding <=> %s) AS sim FROM {cache.cfg.qualified_table} ORDER BY embedding <=> %s LIMIT 1"
    def run(cur):
        res = {}
        for ef in ef_values:
            ids, ss = [], []
            for v in query_vecs:
                cur.execute("BEGIN")
                cur.execute(f"SET LOCAL hnsw.ef_search = {int(ef)}")
                cur.execute(sql, [v, v])
                cid, sim = cur.fetchone()
                cur.execute("COMMIT")
                ids.append(cid); ss.append(sim)
            res[ef] = ann_quality(ids, ss)
        return res
    return cache.backend._with_connection(run)

def latency_run(cache, n_threads, seconds):
    """n_threads clients issuing real cache lookups for `seconds`; returns per-request ms."""
    lat, lock, stop = [], threading.Lock(), time.time() + seconds
    def worker():
        local, rng = [], random.Random()
        while time.time() < stop:
            v = traffic_vecs[rng.randrange(len(traffic_vecs))]
            t0 = time.perf_counter()
            cache.lookup("", scope, threshold=threshold, embedding=v)
            local.append((time.perf_counter() - t0) * 1e3)
        with lock:
            lat.extend(local)
    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads: t.start()
    for t in threads: t.join()
    return np.asarray(lat)

# COMMAND ----------

# MAGIC %md ## Run

# COMMAND ----------

index_rows, accuracy_rows, latency_rows, quality_rows = [], [], [], []
# Start from the FAQ entries only, so exact search and both tables see identical rows.
for c in caches.values():
    c.backend.drop_vector_index()
    c.backend.execute(f"DELETE FROM {c.cfg.qualified_table} WHERE cache_id LIKE 'scale-%%'")
loaded = 0

for size in sizes:
    print(f"== size {size:,}")
    for c in caches.values():
        c.backend.drop_vector_index()
    t0 = time.time()
    load_and_track(loaded, size)
    load_s = time.time() - t0
    loaded = size

    for b, c in caches.items():
        c.backend.execute(f"ANALYZE {c.cfg.qualified_table}")
        build_s = c.backend.create_vector_index()
        plan = c.backend.explain_lookup(eval_vecs[0], c._scope_filter(scope))
        scan = next((l.strip(" ->") for l in plan if "Scan" in l), plan[0])
        index_rows.append({"size": size, "backend": b, "load_s": load_s, "index_build_s": build_s,
                           "index_mb": c.backend.index_size_bytes() / 1e6, "lookup_plan": scan})
        print(f"  {b}: index built in {build_s:.1f}s; lookup plan: {scan}")

        # Recall@1 and cache accuracy (one lookup per query; no hit tracking)
        ann = [c.lookup("", scope, threshold=0.0, embedding=v) for v in query_vecs]
        quality = ann_quality([r.cache_id for r in ann], [r.similarity for r in ann])
        quality_rows.append({"size": size, "backend": b, "setting": "default", **quality})
        if b == "pgvector":
            for ef, q in pgvector_sweep(c, [int(x) for x in dbutils.widgets.get("ef_search_sweep").split(",")]).items():
                quality_rows.append({"size": size, "backend": b, "setting": f"ef_search={ef}", **q})
        ev = ann[:len(eval_q)]
        sim = np.asarray([r.similarity for r in ev])
        # What the nearest entry is: the right FAQ, another FAQ, or a distractor. A Bitext match is
        # often the *same* question worded by another bank, so it isn't necessarily a wrong answer;
        # we report it separately (an LLM judge can score those later).
        kind = np.asarray([
            (r.matched_metadata or {}).get("source") if (r.matched_metadata or {}).get("source") in ("bitext", "gooaq")
            else ("right_faq" if (r.matched_metadata or {}).get("intent_id") == q["expected_intent"] else "wrong_faq")
            for r, q in zip(ev, eval_q)])
        for t in np.arange(0.60, 0.86, 0.05):
            hit = sim >= t
            n_hit = max(hit.sum(), 1)
            accuracy_rows.append({
                "size": size, "backend": b, "threshold": round(t, 2), "hit_rate": hit.mean(),
                "precision": (hit & (kind == "right_faq")).sum() / n_hit,          # strict: only the right FAQ counts
                "wrong_faq_share": (hit & (kind == "wrong_faq")).sum() / n_hit,
                "bitext_share": (hit & (kind == "bitext")).sum() / n_hit,
                "gooaq_share": (hit & (kind == "gooaq")).sum() / n_hit,
                "near_recall_at_1": quality["near_recall_at_1"]})
        print(f"  {b}: " + "  ".join(f"{k} {v:.3f}" for k, v in quality.items()))

        latency_run(c, max(concurrency), 15)   # untimed warm-up: index pages into cache, pool filled
        for n in concurrency:
            ms = latency_run(c, n, duration_s)
            latency_rows.append({"size": size, "backend": b, "clients": n, "requests": len(ms),
                                 "qps": len(ms) / duration_s, "p50_ms": np.percentile(ms, 50),
                                 "p95_ms": np.percentile(ms, 95), "p99_ms": np.percentile(ms, 99)})
            print(f"  {b}: {n:>2} clients  {len(ms) / duration_s:7.0f} qps  p50 {np.percentile(ms, 50):6.1f} ms  p95 {np.percentile(ms, 95):6.1f} ms")

index_df, accuracy_df, latency_df, quality_df = (pd.DataFrame(x).assign(run_id=run_id)
                                                  for x in (index_rows, accuracy_rows, latency_rows, quality_rows))
for name, df in [("load_test_index", index_df), ("load_test_accuracy", accuracy_df),
                 ("load_test_latency", latency_df), ("load_test_ann_quality", quality_df)]:
    spark.createDataFrame(df).write.mode("append").saveAsTable(f"{catalog}.{schema}.{name}")

# COMMAND ----------

# MAGIC %md ## Results

# COMMAND ----------

display(index_df.round(2))
display(quality_df.round(4))
display(accuracy_df[accuracy_df.threshold.isin([0.7, round(threshold, 2), 0.8])].round(3))
display(latency_df.round(1))

# COMMAND ----------

import plotly.graph_objects as go
from plotly.subplots import make_subplots

COLORS = {"pgvector": "#2a78d6", "lakebase_search": "#eb6834"}
INK, MUTED, GRID, SURFACE = "#1f1f1e", "#6b6a64", "#e8e7e2", "#fcfcfb"

def style(fig, title):
    fig.update_layout(title=dict(text=title, font=dict(color=INK)), plot_bgcolor=SURFACE, paper_bgcolor=SURFACE,
                      font=dict(color=MUTED), legend=dict(orientation="h", y=-0.25), height=420, hovermode="x unified")
    fig.update_xaxes(gridcolor=GRID, zeroline=False)
    fig.update_yaxes(gridcolor=GRID, zeroline=False)
    return fig

def line(fig, x, y, b, name, hover, row=None, col=None, show=True):
    kw = dict(row=row, col=col) if row else {}
    fig.add_trace(go.Scatter(x=x, y=y, name=name, legendgroup=b, showlegend=show, mode="lines+markers",
                             line=dict(color=COLORS[b], width=2),
                             marker=dict(size=8, color=COLORS[b], line=dict(color=SURFACE, width=2)),
                             hovertemplate=hover + "<extra>" + b + "</extra>"), **kw)

# Latency vs cache size at 1 client, and throughput vs clients at the largest size.
fig = make_subplots(rows=1, cols=2, subplot_titles=("p50 / p95 lookup latency, 1 client", f"Throughput at {sizes[-1]:,} entries"))
one = latency_df[latency_df.clients == min(concurrency)]
top = latency_df[latency_df["size"] == sizes[-1]]
for b in backends:
    d = one[one.backend == b]
    line(fig, d["size"], d["p50_ms"], b, b, "p50 %{y:.1f} ms", 1, 1)
    fig.add_trace(go.Scatter(x=d["size"], y=d["p95_ms"], legendgroup=b, showlegend=False, mode="lines",
                             line=dict(color=COLORS[b], width=2, dash="dot"), hovertemplate="p95 %{y:.1f} ms<extra></extra>"), row=1, col=1)
    d = top[top.backend == b]
    line(fig, d["clients"], d["qps"], b, b, "%{y:.0f} qps", 1, 2, show=False)
fig.update_xaxes(type="log", title="Cache entries", row=1, col=1)
fig.update_yaxes(title="ms (solid p50, dotted p95)", rangemode="tozero", row=1, col=1)
fig.update_xaxes(title="Concurrent clients", row=1, col=2)
fig.update_yaxes(title="Lookups / s", rangemode="tozero", row=1, col=2)
style(fig, "Lookup latency and throughput").show()

# COMMAND ----------

# Recall and cache accuracy vs cache size at the chosen threshold.
fig = make_subplots(rows=1, cols=2, subplot_titles=("ANN recall@1 on near queries (default settings)", f"Precision and hit rate at threshold {threshold:.2f}"))
at = accuracy_df[accuracy_df.threshold == round(threshold, 2)]
qd = quality_df[quality_df.setting == "default"]
for b in backends:
    d = qd[qd.backend == b]
    line(fig, d["size"], d["near_recall_at_1"] * 100, b, b, "recall %{y:.1f}%", 1, 1)
    d = at[at.backend == b]
    line(fig, d["size"], d["precision"] * 100, b, b, "precision %{y:.1f}%", 1, 2, show=False)
    fig.add_trace(go.Scatter(x=d["size"], y=d["hit_rate"] * 100, legendgroup=b, showlegend=False, mode="lines",
                             line=dict(color=COLORS[b], width=2, dash="dot"), hovertemplate="hit rate %{y:.1f}%<extra></extra>"), row=1, col=2)
fig.update_xaxes(type="log", title="Cache entries")
fig.update_yaxes(title="%", range=[0, 105])
fig.update_yaxes(title="% (solid precision, dotted hit rate)", row=1, col=2)
style(fig, "Accuracy as the cache grows").show()

# COMMAND ----------

for c in caches.values():
    c.close()
