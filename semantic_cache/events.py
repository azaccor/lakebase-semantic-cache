"""Log cache requests to a Delta table: the record used to measure hit rate, latency,
cost and false hits. ``log_events`` writes with Spark (notebooks); ``log_events_sql``
writes through a SQL warehouse (apps and other places without Spark)."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from .cache import CacheResult

EVENTS_SCHEMA = """
  event_ts timestamp, run_id string, source string, backend string,
  question string, answer string, hit boolean, similarity double, threshold double,
  cache_id string, matched_question string, matched_metadata string, scope map<string,string>,
  embed_ms double, lookup_ms double, generate_ms double, write_ms double, total_ms double,
  input_tokens bigint, output_tokens bigint, cost_usd double, attributes string
"""

# Column name -> SQL type, in table order.
_COLUMNS = [tuple(c.split()) for c in " ".join(EVENTS_SCHEMA.split()).split(", ")]


def _event_rows(results: list[CacheResult], *, run_id: str, source: str, backend: str,
                price_in_per_m: float, price_out_per_m: float, attributes: list[dict] | None) -> list[tuple]:
    now = datetime.now(timezone.utc)
    rows = []
    for i, r in enumerate(results):
        rows.append((
            now, run_id, source, backend,
            r.question, r.answer, r.hit, r.similarity, r.threshold,
            r.cache_id, r.matched_question, json.dumps(r.matched_metadata) if r.matched_metadata else None,
            {k: str(v) for k, v in r.scope.items()},
            r.embed_ms, r.lookup_ms, r.generate_ms, r.write_ms, r.total_ms,
            r.input_tokens, r.output_tokens,
            (r.input_tokens * price_in_per_m + r.output_tokens * price_out_per_m) / 1e6,
            json.dumps(attributes[i]) if attributes else None,
        ))
    return rows


def log_events(spark, table: str, results: list[CacheResult], *, run_id: str, source: str, backend: str,
               price_in_per_m: float = 0.0, price_out_per_m: float = 0.0,
               attributes: list[dict] | None = None) -> int:
    """Append results to ``table`` (created if missing). ``cost_usd`` is the LLM cost of the
    request from token counts and the given prices (0 on a hit; embedding cost excluded).
    ``attributes`` is an optional per-result dict (e.g. the ground-truth intent in an eval)."""
    rows = _event_rows(results, run_id=run_id, source=source, backend=backend, price_in_per_m=price_in_per_m,
                       price_out_per_m=price_out_per_m, attributes=attributes)
    spark.sql(f"CREATE TABLE IF NOT EXISTS {table} ({EVENTS_SCHEMA})")
    spark.createDataFrame(rows, EVENTS_SCHEMA).write.mode("append").saveAsTable(table)
    return len(rows)


def log_events_sql(w, warehouse_id: str, table: str, results: list[CacheResult], *, run_id: str, source: str,
                   backend: str, price_in_per_m: float = 0.0, price_out_per_m: float = 0.0,
                   attributes: list[dict] | None = None) -> int:
    """``log_events`` through a SQL warehouse (``w`` is a WorkspaceClient), in one INSERT: the rows
    are bound as a single JSON parameter (never interpolated) and parsed with ``from_json``.
    The table must exist."""
    from databricks.sdk.service.sql import StatementParameterListItem, StatementState

    rows = _event_rows(results, run_id=run_id, source=source, backend=backend, price_in_per_m=price_in_per_m,
                       price_out_per_m=price_out_per_m, attributes=attributes)
    if not rows:
        return 0
    names = [n for n, _ in _COLUMNS]
    payload = json.dumps([
        {n: v.isoformat(timespec="milliseconds") if isinstance(v, datetime) else v for n, v in zip(names, row)}
        for row in rows
    ])
    struct = "array<struct<" + ",".join(f"{n}:{t}" for n, t in _COLUMNS) + ">>"
    cols = ", ".join(names)
    resp = w.statement_execution.execute_statement(
        warehouse_id=warehouse_id, wait_timeout="50s",
        parameters=[StatementParameterListItem(name="rows", value=payload)],
        statement=f"INSERT INTO {table} ({cols}) SELECT {cols} FROM (SELECT inline(from_json(:rows, '{struct}')))",
    )
    if resp.status.state != StatementState.SUCCEEDED:
        raise RuntimeError(f"Event insert failed: {resp.status.state} {resp.status.error}")
    return len(rows)
