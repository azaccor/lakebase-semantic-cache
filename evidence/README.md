# Run evidence

Exported 2026-10-20 15:46 UTC by `scripts/export_evidence.py` from real runs. Workspace identifiers are replaced with placeholders.

## End-to-end job: `semantic_cache_end_to_end` (run 32232528631469)

Result: **SUCCESS**, started 2026-10-20 00:59:13 UTC.

| task | result | started | duration | evidence |
|---|---|---|---|---|
| land_raw | SUCCESS | 2026-10-20 00:59:13 UTC | 36 s | [runs/land_raw.md](runs/land_raw.md) |
| setup_cache_table | SUCCESS | 2026-10-20 00:59:13 UTC | 55 s | [runs/setup_cache_table.md](runs/setup_cache_table.md) |
| ingest | SUCCESS | 2026-10-20 00:59:49 UTC | 83 s | [runs/ingest.md](runs/ingest.md) |
| seed_cache | SUCCESS | 2026-10-20 01:01:12 UTC | 78 s | [runs/seed_cache.md](runs/seed_cache.md) |
| evaluate | SUCCESS | 2026-10-20 01:02:30 UTC | 78 s | [runs/evaluate.md](runs/evaluate.md) |
| metrics | SUCCESS | 2026-10-20 01:03:48 UTC | 53 s | [runs/metrics.md](runs/metrics.md) |

## Load test job: `semantic_cache_load_test` (run 905528556699230)

Result: **SUCCESS**, started 2026-10-20 01:05:31 UTC.

| task | result | started | duration | evidence |
|---|---|---|---|---|
| load_test | FAILED (retried) | 2026-10-20 01:05:31 UTC | | |
| load_test | SUCCESS | 2026-10-20 01:06:10 UTC | 845 s | [runs/load_test.md](runs/load_test.md) |

## Also

- [tables.md](tables.md): snapshots of the gold, silver and evaluation tables.
- [app_responses.json](app_responses.json): responses recorded from the deployed app: a cached paraphrase, a known false hit, a labeled replay, the judge's results, and two Ask Genie answers.
