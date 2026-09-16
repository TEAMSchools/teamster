"""Warehouse adapters. The only modules that import a BigQuery client."""

from __future__ import annotations

from typing import Any, Protocol

PROJECT = "teamster-332318"


class QueryClient(Protocol):
    def query(self, sql: str, /, job_config: Any = None) -> Any: ...


def client() -> QueryClient:
    from google.cloud import bigquery

    return bigquery.Client(project=PROJECT)


def sql_list(values) -> str:
    return ", ".join(repr(v) if isinstance(v, str) else str(v) for v in values)
