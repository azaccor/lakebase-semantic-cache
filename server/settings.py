"""App settings, from environment variables set in app.yaml (resource values via valueFrom)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None:
        raise RuntimeError(f"Missing environment variable {name}")
    return value


@dataclass(frozen=True)
class Settings:
    lakebase_instance: str = field(default_factory=lambda: _env("LAKEBASE_INSTANCE", "semantic-cache"))
    pg_schema: str = field(default_factory=lambda: _env("PG_SCHEMA", "semantic_cache"))
    backend: str = field(default_factory=lambda: _env("CACHE_BACKEND", "pgvector"))
    llm_endpoint: str = field(default_factory=lambda: _env("LLM_ENDPOINT", "databricks-claude-opus-4-8"))
    embedding_endpoint: str = field(default_factory=lambda: _env("EMBEDDING_ENDPOINT", "databricks-qwen3-embedding-0-6b"))
    warehouse_id: str = field(default_factory=lambda: _env("DATABRICKS_WAREHOUSE_ID"))
    catalog: str = field(default_factory=lambda: _env("UC_CATALOG"))
    schema: str = field(default_factory=lambda: _env("UC_SCHEMA", "semantic_cache"))
    # Entries the app writes on a miss go to this tenant, so 02_evaluate's scored scope (tenant "")
    # stays as 01_build_cache seeded it. Lookups search both.
    app_tenant: str = field(default_factory=lambda: _env("APP_TENANT", "app"))
    threshold: float = field(default_factory=lambda: float(_env("SIMILARITY_THRESHOLD", "0.70")))
    # USD per 1M tokens: the same list-price assumptions as 01_build_cache; adjust to your contract.
    price_in_per_m: float = field(default_factory=lambda: float(_env("PRICE_IN_PER_M", "15")))
    price_out_per_m: float = field(default_factory=lambda: float(_env("PRICE_OUT_PER_M", "75")))

    def table(self, name: str) -> str:
        return f"{self.catalog}.{self.schema}.{name}"
