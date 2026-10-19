"""Measured inputs for the ROI calculator, read from the Delta tables the notebooks write:
LLM latency and tokens from cache misses, embed + lookup overhead from every request,
and the hit-rate / precision curve from 02_evaluate's threshold sweep."""
from __future__ import annotations

import threading
import time

from .settings import Settings
from .warehouse import Warehouse, num

TTL_S = 300
SWEEP_COLUMNS = ("threshold", "hit_rate", "cacheable_hit_rate", "precision", "false_hit_rate",
                 "cacheable_false_hit_rate", "novel_hit_rate", "account_specific_hits")


class Measured:
    def __init__(self, wh: Warehouse, settings: Settings):
        self.wh, self.s = wh, settings
        self._cached: tuple[float, dict] | None = None
        self._lock = threading.Lock()

    def get(self, refresh: bool = False) -> dict:
        with self._lock:
            if refresh or not self._cached or time.monotonic() - self._cached[0] > TTL_S:
                self._cached = (time.monotonic(), self._load())
            return self._cached[1]

    def _load(self) -> dict:
        s, events = self.s, self.s.table("cache_events")
        llm = self.wh.query(
            f"""SELECT count(*) AS n, avg(generate_ms) AS llm_ms, percentile(generate_ms, 0.5) AS llm_p50_ms,
                       percentile(generate_ms, 0.95) AS llm_p95_ms, avg(input_tokens) AS input_tokens,
                       avg(output_tokens) AS output_tokens, avg(write_ms) AS write_ms, max(event_ts) AS last_ts
                FROM {events}
                WHERE NOT hit AND input_tokens > 0 AND backend = :backend AND scope['model'] = :model""",
            {"backend": s.backend, "model": s.llm_endpoint})[0]
        overhead = self.wh.query(
            f"""SELECT count(*) AS n, avg(embed_ms) AS embed_ms, avg(lookup_ms) AS lookup_ms,
                       percentile(embed_ms, 0.5) AS embed_p50_ms, percentile(lookup_ms, 0.5) AS lookup_p50_ms,
                       max(event_ts) AS last_ts
                FROM {events} WHERE backend = :backend
                  AND embed_ms >= 1   -- replays pass precomputed embeddings (older rows logged ~0.0001 ms)""",
            {"backend": s.backend})[0]
        return {
            "backend": s.backend,
            "llm": {
                "source": events, "n": int(llm["n"]), "last_ts": llm["last_ts"],
                **{k: num(llm[k]) for k in ("llm_ms", "llm_p50_ms", "llm_p95_ms", "input_tokens",
                                            "output_tokens", "write_ms")},
            },
            "overhead": {
                "source": events, "n": int(overhead["n"]), "last_ts": overhead["last_ts"],
                **{k: num(overhead[k]) for k in ("embed_ms", "lookup_ms", "embed_p50_ms", "lookup_p50_ms")},
            },
            "sweep": self._sweep(),
        }

    def _sweep(self) -> dict:
        table = self.s.table("eval_threshold_sweep")
        latest = "SELECT run_id FROM {t} WHERE backend = :backend ORDER BY {order} LIMIT 1"
        try:   # run_ts was added to 02_evaluate later; older tables don't have it yet
            run = self.wh.query(latest.format(t=table, order="run_ts DESC NULLS LAST"), {"backend": self.s.backend})
        except RuntimeError:
            run = self.wh.query(latest.format(t=table, order="run_id"), {"backend": self.s.backend})
        if not run:
            return {"source": table, "run_id": None, "points": []}
        rows = self.wh.query(
            # SELECT *: columns added to 02_evaluate later (cacheable_false_hit_rate, novel_hit_rate) are
            # absent from older tables, and NULL for older runs.
            f"SELECT * FROM {table} WHERE backend = :backend AND run_id = :run_id ORDER BY threshold",
            {"backend": self.s.backend, "run_id": run[0]["run_id"]})
        return {
            "source": table, "run_id": run[0]["run_id"],
            "points": [{k: num(r.get(k)) for k in SWEEP_COLUMNS} for r in rows],
        }
