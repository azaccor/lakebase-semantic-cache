"""Log app requests to cache_events off the request path: a SQL warehouse insert takes
~1 s (more while a serverless warehouse starts), which shouldn't be added to a cache hit."""
from __future__ import annotations

import logging
import queue
import threading

from semantic_cache.events import log_events_sql

log = logging.getLogger(__name__)


class EventLog:
    def __init__(self, w, warehouse_id: str, table: str, **defaults):
        self.w, self.warehouse_id, self.table, self.defaults = w, warehouse_id, table, defaults
        self._q: queue.Queue = queue.Queue()
        threading.Thread(target=self._run, daemon=True, name="event-log").start()

    def log(self, results, **kwargs) -> None:
        self._q.put((results, {**self.defaults, **kwargs}))

    def flush(self, timeout_s: float = 30) -> None:
        """Best effort: wait for queued events (e.g. before reading them back)."""
        done = threading.Event()
        self._q.put((None, done))
        done.wait(timeout_s)

    def _run(self) -> None:
        while True:
            results, kwargs = self._q.get()
            if results is None:
                kwargs.set()
                continue
            try:
                log_events_sql(self.w, self.warehouse_id, self.table, results, **kwargs)
            except Exception:   # never let logging take the app down
                log.exception("Failed to log %d cache event(s)", len(results))
