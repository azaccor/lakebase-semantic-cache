"""Minimal SQL warehouse client: parameterized statements, results as dicts."""
from __future__ import annotations

import time

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementParameterListItem, StatementState

_DONE = {StatementState.SUCCEEDED, StatementState.FAILED, StatementState.CANCELED, StatementState.CLOSED}


class Warehouse:
    def __init__(self, w: WorkspaceClient, warehouse_id: str):
        self.w, self.warehouse_id = w, warehouse_id

    def query(self, sql: str, params: dict | None = None, timeout_s: float = 110) -> list[dict]:
        """Run ``sql`` with ``:name`` parameters bound from ``params`` (sent as strings; cast in
        SQL where a type matters). Returns rows as dicts of strings (None for NULL)."""
        items = [StatementParameterListItem(name=k, value=None if v is None else str(v))
                 for k, v in (params or {}).items()]
        resp = self.w.statement_execution.execute_statement(
            warehouse_id=self.warehouse_id, statement=sql, parameters=items, wait_timeout="30s")
        deadline = time.monotonic() + timeout_s
        while resp.status.state not in _DONE:   # e.g. the serverless warehouse is still starting
            if time.monotonic() > deadline:
                self.w.statement_execution.cancel_execution(resp.statement_id)
                raise TimeoutError("SQL warehouse query timed out")
            time.sleep(1)
            resp = self.w.statement_execution.get_statement(resp.statement_id)
        if resp.status.state != StatementState.SUCCEEDED:
            raise RuntimeError(f"Query failed: {resp.status.error.message if resp.status.error else resp.status.state}")
        if not resp.manifest or not resp.manifest.schema or not resp.manifest.schema.columns:
            return []
        cols = [c.name for c in resp.manifest.schema.columns]
        return [dict(zip(cols, row)) for row in (resp.result.data_array or [])] if resp.result else []


def num(v, default=None):
    return default if v is None else float(v)
