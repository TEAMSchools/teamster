"""Stage Avro to GCS and create native tables from the snapshot's schema."""

from __future__ import annotations

from typing import Any

SANDBOX_PROJECT = "teamster-cube-sandbox"
SANDBOX_DATASET = "kipptaf_marts"


def assert_complete(snap: dict[str, Any], loaded: dict[str, set[str]]) -> None:
    """Fail loudly if the sandbox is short of what the snapshot expects.

    The generator writes table by table, so a failure partway leaves the
    sandbox holding fewer columns than the snapshot it was built from.
    Nothing else notices: the tables exist, queries succeed, and the data is
    quietly short. This is the only thing that catches it.
    """
    missing = sorted(
        f"{table}.{column}"
        for table, columns in snap["tables"].items()
        for column in columns
        if column not in loaded.get(table, set())
    )
    if missing:
        raise ValueError(
            f"load incomplete, sandbox is short of the snapshot: {missing}"
        )


def loaded_columns(client: Any, project: str, dataset: str) -> dict[str, set[str]]:
    rows = client.query(
        # trunk-ignore(bandit/B608): project/dataset are our own module constants, never user input.
        f"SELECT table_name, column_name "
        f"FROM `{project}.{dataset}.INFORMATION_SCHEMA.COLUMNS`"
    ).result()
    out: dict[str, set[str]] = {}
    for row in rows:
        out.setdefault(row.table_name, set()).add(row.column_name)
    return out


def load_table(client: Any, table: str, gcs_uri: str, schema: list[Any]) -> None:
    """Create the table from the snapshot's schema, then load the Avro.

    The explicit schema is what makes the deployed types match the snapshot by
    construction. Letting BigQuery infer them from the Avro would make it match
    by luck.
    """
    from google.cloud import bigquery

    client.load_table_from_uri(
        gcs_uri,
        f"{SANDBOX_PROJECT}.{SANDBOX_DATASET}.{table}",
        job_config=bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.AVRO,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            schema=schema,
            use_avro_logical_types=True,
        ),
    ).result()


def main() -> int:
    from google.cloud import bigquery

    from teamster.cube_sandbox import avro, snapshot

    snap = snapshot.load()
    client = bigquery.Client(project=SANDBOX_PROJECT)
    for table, columns in snap["tables"].items():
        load_table(
            client,
            table,
            f"gs://{SANDBOX_PROJECT}-staging/{table}.avro",
            avro.bq_schema(table, columns),
        )
    assert_complete(snap, loaded_columns(client, SANDBOX_PROJECT, SANDBOX_DATASET))
    print(f"loaded {len(snap['tables'])} tables and verified against the snapshot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
