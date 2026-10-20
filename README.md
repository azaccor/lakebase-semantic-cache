# Lakebase Semantic Cache

A semantic cache for LLM endpoints on Databricks, stored in **Lakebase** (Postgres) and served by a
Databricks App. A refresh of the 2024
[semantic caching accelerator](https://www.databricks.com/blog/building-cost-optimized-chatbot-semantic-caching),
which used a Vector Search index instead.

Beyond caching, it **measures what the cache gets wrong**: a threshold sweep over held-out paraphrases, and
an LLM judge that grades served answers against freshly generated ones.

> **Dependency:** the Lakebase access layer is `databricks-lakebase-adapters`, which is not on PyPI yet.
> Supply its wheel yourself (see Getting started); everything else installs from PyPI.

> **Data:** the question bank is synthetic, written for a fictional app ("Lux Pay"). The load test uses the
> public [Bitext retail-banking](https://huggingface.co/datasets/bitext/Bitext-retail-banking-llm-chatbot-training-dataset)
> (CDLA-Sharing-1.0) and [GooAQ](https://github.com/allenai/gooaq) (Apache-2.0) datasets. No customer data.

## How it works

```
question ─► embed ─► nearest cached question in the same scope (Lakebase)
                         │
            similarity ≥ threshold ?
               yes │                 │ no
     return cached answer     call the LLM ─► return answer ─► write it to the cache
```

- **Scope keys** (`model`, `prompt_version`, `tenant` by default): a lookup only matches entries with
  the same values, so changing the model or prompt never serves a stale configuration's answer.
- **TTL**: optional per-entry `expires_at`; expired entries are never served.
- **Hit tracking**: `hit_count` / `last_hit_at` per entry (the basis for LRU eviction).

## Backends

| Backend | Index | When |
|---|---|---|
| `pgvector` (default) | HNSW | Caches that grow one entry per miss; any Lakebase instance |
| `lakebase_search` | `lakebase_ann` (IVF + RaBitQ) | Large caches loaded in bulk, with the index rebuilt periodically; requires Lakebase Search to be enabled for your workspace and Lakebase project |

**Choosing.** A cache writes on every miss and deletes on expiry, and HNSW indexes each new row as it is
written. IVF learns its clusters when the index is built, so as entries are added it drifts until the next
rebuild (`REINDEX`). In `03b_load_test`, where both indexes are rebuilt after each bulk load, `lakebase_ann`
was faster and more accurate than HNSW from 1K to 1M entries, and RaBitQ's ~1-bit codes keep its index far
smaller than HNSW's graph of full vectors, which needs to stay in memory for fast lookups. So: `pgvector` for
a write-through cache, `lakebase_search` for a large cache filled in batches (e.g. from inference-table history)
and rebuilt on a schedule.

Both use the same table layout, in one table per backend (`cache_entries_<backend>`): the two indexes serve the
same `<=>` operator, so on a shared table Postgres would pick either one.

**pgvector tuning.** Postgres underprices 1024-d distance math, so for pgvector it prefers a sequential scan over
HNSW well past 10K rows (measured 41 ms vs 1 ms at 10K). By default the cache's own connections set
`enable_seqscan = off` (`CacheConfig.pgvector_prefer_index`); `hnsw_ef_search`, `hnsw_m` and
`hnsw_ef_construction` are configurable. Lakebase Search's `lakebase_ann` index needs none of this.

## Usage

```python
from semantic_cache import CacheConfig, SemanticCache, chat_generator

cache = SemanticCache(CacheConfig(lakebase_instance="my-instance"))
answer_with_llm = chat_generator("databricks-claude-opus-4-8")

res = cache.get_or_generate("How do I reset my password?", answer_with_llm,
                            scope={"model": "databricks-claude-opus-4-8", "prompt_version": "v1"})
res.hit, res.similarity, res.answer
```

## Data journey

```
 data/question_bank.json ─┐                       ┌─ Lakeflow pipeline: semantic_cache_ingest (serverless SQL)
 Bitext + GooAQ (public) ─┴─► UC Volume raw/ ─────┤   bronze_*  (Auto Loader: read_files)
     (00a_land_raw)                               │   silver_faq_intents · silver_eval_questions · silver_public_questions  (expectations)
                                                  └─► gold_scale_embeddings  (ai_query() embeddings)
                                                            │
 01_build_cache ── seeds Lakebase (pgvector HNSW) from silver_faq_intents; every request ─► cache_events (Delta)
 02_evaluate ───── replays silver_eval_questions ─► eval_lookups · eval_threshold_sweep · eval_summary
 App ───────────── live questions, replay, LLM judge ─► cache_events · judge_results
                                                            │
                     Lakeflow pipeline: semantic_cache_metrics ─► gold_cache_daily · gold_judge_daily ·
                     gold_false_hit_monitor · gold_threshold_curve · gold_category_risk
                                                            │
                     Genie space "Lux Pay semantic cache insights" + the app's ROI calculator and Ask Genie tab
```

Everything above is defined in this repo's bundle: the app (`databricks.yml`), the two pipelines
(`resources/pipelines.yml`, SQL in `pipelines/`), the Lakeflow Jobs that run them with the notebooks
(`resources/jobs.yml`), and the Genie space (`resources/genie.yml`).

| Lakeflow construct | What it does |
|---|---|
| Job `semantic_cache_end_to_end` | `land_raw` → `ingest` pipeline → `setup_cache_table` → `seed_cache` → `evaluate` → `metrics` pipeline (serverless; weekly schedule, paused) |
| Pipeline `semantic_cache_ingest` | Raw files → bronze streaming tables (Auto Loader) → silver FAQs, labeled evaluation questions and cleaned public questions (with expectations) → `gold_scale_embeddings` (`ai_query()`) |
| Pipeline `semantic_cache_metrics` | Governed KPIs: daily deflection and cost per question, judged false-hit rate (Wilson 95% interval), a false-hit **drift monitor** against a limit, the threshold curve, and risk by FAQ category (money-movement flagged) |
| Job `semantic_cache_monitor` | Daily refresh of the metrics pipeline (paused) |
| Job `semantic_cache_load_test` | `03b_load_test` on `gold_scale_embeddings`, recording the Lakebase CU size |

## Getting started

1. Upload the `databricks-lakebase-adapters` wheel to a UC Volume (for the notebooks) and copy it into `wheels/`
   (gitignored; the bundle syncs it for the app).
2. Deploy and run with your workspace values (the bundle variables default to placeholders):

```bash
export BUNDLE_VAR_catalog=<catalog> BUNDLE_VAR_warehouse_id=<warehouse-id> \
       BUNDLE_VAR_lakebase_project=<lakebase-project> BUNDLE_VAR_sdk_wheel=/Volumes/<catalog>/semantic_cache/libs/<wheel>.whl
databricks bundle deploy -t dev --profile <profile>        # first time: the Genie space fails until its tables exist
databricks bundle run semantic_cache_end_to_end -t dev --profile <profile>
databricks bundle deploy -t dev --profile <profile>        # now creates the Genie space and attaches it to the app
databricks apps deploy -t dev --skip-validation --profile <profile>
```

`--skip-validation` skips the local Node build; the platform runs `npm install && npm run build` itself.

## Notebooks

| Notebook | |
|---|---|
| `00a_land_raw` | Land the raw files in a UC Volume: the question bank and the public Bitext + GooAQ datasets |
| `00_setup` | Install the SDK, create the cache table + index, smoke test |
| `01_build_cache` | Seed the cache with FAQ answers from the LLM (through the cache), from `silver_faq_intents`; log every request to `cache_events` |
| `02_evaluate` | Replay `silver_eval_questions` on each backend: threshold sweep with leave-one-FAQ-out false-hit rates, latency and cost vs. no cache |
| `03b_load_test` | 1K → 100K entries (1M with a larger `scale_rows`) on both backends: index build, ANN quality vs exact search, cache accuracy, latency/QPS under concurrency |

## Evidence

[`evidence/`](evidence/README.md) holds readable output from real runs, exported by `scripts/export_evidence.py`:
every notebook task's code and printed output, each pipeline update's row counts and expectation results,
snapshots of the governed tables, and responses recorded from the deployed app (including Ask Genie).
The figures in the deck trace back to these files:

| Figure | Measured value | Where |
|---|---|---|
| Opus latency and tokens per answer | ~1.77 s, ~1,876 input / 76 output tokens (53 misses) → ~$0.011 at list price | `app_responses.json` → `measured.llm` |
| Repeat questions caught at 0.75 | 29.3%; wrong on repeats 1.2%, on uncached questions 1.7% (leave-one-FAQ-out) | `runs/evaluate.md` (threshold sweep) |
| Same at 0.70 | 53.3% caught; 3.6% / 9.7% wrong | `runs/evaluate.md` |
| Account-specific questions served from cache | 0 at 0.70 and above | `runs/evaluate.md` |
| Cached answer latency | ~0.22 s (embed + lookup) vs ~1.76 s | `runs/evaluate.md` (savings summary) |
| Judged false-hit rate | 8.2% (4 of 49), 95% CI 3.2–19.2%; 98% agreement with labels; monitor OK | `app_responses.json` → `judge_results`, `genie_monitor`; `tables.md` → `gold_false_hit_monitor` |
| Cost per question with vs without the cache | gold KPIs and Genie's answer | `tables.md` → `gold_cache_daily`; `app_responses.json` → `genie_ask` |
| 1 CU holds a 100K-entry cache | lookup p50 10.8 ms / p95 14.9 ms single client, ~200+ lookups/s with 4–32 clients | `runs/load_test.md` |
| A real false hit | "How do I manage payment notifications?" served the recurring-payments answer at 0.804 | `app_responses.json` → `ask_false_hit_example` |
| Pipeline data quality | 10 expectations, 0 failures over 3.04M public questions, 52 FAQs, 175 labeled questions | `runs/ingest.md` |

## App

A Databricks App (FastAPI + React) on the same module and cache table:

- **ROI calculator**: will a cache save money at your volume, how much, and what happens to latency? Prefilled
  from what the notebooks measured (LLM latency/tokens from `cache_events`, the hit-rate/precision curve from
  `eval_threshold_sweep`); every input is editable and labeled measured, price, or assumption.
- **Playground**: ask questions through the cache (hit/miss, similarity vs threshold, latency breakdown), and
  replay the labeled held-out paraphrases at any threshold.
- **False-hit judge**: for a sample of hits, the LLM writes a fresh answer and judges whether the cached one
  answers the question. Gives a measured false-hit rate (with a 95% CI) and its agreement with the labels.
  Results go to `judge_results`, per judge prompt version and cache prompt version (re-seeding starts over).
- **Ask Genie**: plain-English questions over the gold metrics through the Genie space, showing Genie's answer,
  the result rows and the SQL it ran.

Lookups search the seeded FAQs and the app's own entries; misses are cached under tenant `app`, so
`02_evaluate`'s scope is unchanged. Requests are logged to `cache_events` (`source = 'app'` / `'app-replay'`)
through the SQL warehouse.

After the first deploy (see Getting started), grant the app's service principal (`databricks apps get lakebase-semantic-cache` → `service_principal_client_id`)
access to what the notebooks created:

```sql
-- Unity Catalog (SQL warehouse)
GRANT USE CATALOG ON CATALOG <catalog> TO `<sp-client-id>`;
GRANT USE SCHEMA, SELECT, MODIFY, CREATE TABLE ON SCHEMA <catalog>.semantic_cache TO `<sp-client-id>`;
-- Lakebase (as the table owner)
GRANT USAGE ON SCHEMA semantic_cache TO "<sp-client-id>";
GRANT SELECT, INSERT, UPDATE ON semantic_cache.cache_entries_pgvector TO "<sp-client-id>";
```

## Layout

```
semantic_cache/   the module (config, backends, cache, events)
server/           the app's FastAPI backend (ROI inputs, playground, judge, Ask Genie)
frontend/         the app's React UI (built on the platform by `npm run build` into server/static)
data/             question_bank.json (50 cacheable FAQs + 2 account-specific probes, 167 held-out
                  paraphrases), system_prompt.txt (its hash is part of the cache scope)
pipelines/        Lakeflow Spark Declarative Pipeline SQL: ingest/ (bronze → silver → gold) and metrics/ (gold KPIs)
resources/        bundle resources: pipelines, jobs, Genie space
notebooks/        Databricks notebooks, run by the Lakeflow Jobs
scripts/          export_evidence.py
evidence/         readable output from real runs
```
