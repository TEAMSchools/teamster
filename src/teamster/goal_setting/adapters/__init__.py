"""Warehouse adapters. The only modules that import a BigQuery client."""

from __future__ import annotations

PROJECT = "teamster-332318"


def client():
    from google.cloud import bigquery

    return bigquery.Client(project=PROJECT)


def sql_list(values) -> str:
    return ", ".join(repr(v) if isinstance(v, str) else str(v) for v in values)
