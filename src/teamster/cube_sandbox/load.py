"""Stage Avro to GCS and create native tables from the snapshot's schema.

**BigQuery ignores `LoadJobConfig.schema` for AVRO.** Google's own
"Specifying a schema" page says it plainly: "Specifying a schema is supported
when you load CSV and JSON (newline delimited) files. When you load Avro,
Parquet, ORC, Firestore export data, or Datastore export data, the schema is
automatically retrieved from the self-describing source data"
(https://cloud.google.com/bigquery/docs/schemas), and the schema-detection
page repeats it: "Schema auto-detection is not used with Avro files ... the
table schema is automatically retrieved from the self-describing source
data" (https://cloud.google.com/bigquery/docs/schema-detect). So passing a
`schema=` beside `SourceFormat.AVRO` reads as an explicit schema and is not
one — the load succeeds and the table's types come from whatever fastavro
wrote.

The spec asks for the opposite: "create each table's schema explicitly from
the pinned snapshot, rather than letting BigQuery infer it from the Avro".
This module does that for real, in two steps the API does honour:

1. `create_table` replaces the table with one whose columns and types come
   from `avro.bq_schema`, which reads the pinned snapshot.
2. The load runs with `WRITE_TRUNCATE_DATA`, which the API documents as
   "overwrites the data, but keeps the constraints and schema of the existing
   table" — against `WRITE_TRUNCATE`, which "uses the schema from the load
   job" and would put the Avro-derived schema back. `CREATE_NEVER` closes the
   last door: a load can never conjure an Avro-shaped table of its own.

`assert_complete` then compares names AND types against the snapshot, because
those two steps are a claim and the check is what makes it verified.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

SANDBOX_PROJECT = "teamster-cube-sandbox"
SANDBOX_DATASET = "kipptaf_marts"
STAGING_BUCKET = f"{SANDBOX_PROJECT}-staging"
SERVICE_ACCOUNT = f"cube-cloud-sandbox@{SANDBOX_PROJECT}.iam.gserviceaccount.com"
DEFAULT_AVRO_DIR = Path("build/cube_sandbox/full")


def assert_complete(snap: dict[str, Any], loaded: dict[str, dict[str, str]]) -> None:
    """Fail loudly if the sandbox is not the snapshot, column for column.

    Two failures, not one. A missing column is a partial load: the generator
    writes table by table, so a failure partway leaves the sandbox holding
    fewer columns than the snapshot it was built from, and nothing else
    notices — the tables exist, queries succeed, and the data is quietly
    short.

    A column present under the WRONG TYPE is the quieter one. Comparing names
    alone passes a `NUMERIC` that landed as `FLOAT64`, and a kit built on that
    sandbox learns that money and rate columns are floats. It repoints onto
    production NUMERICs and starts rounding. Nothing about the name check
    would have fired.
    """
    problems = []
    for table, columns in sorted(snap["tables"].items()):
        found = loaded.get(table, {})
        for column, meta in sorted(columns.items()):
            if column not in found:
                problems.append(f"{table}.{column}: missing")
            elif found[column] != meta["type"]:
                problems.append(
                    f"{table}.{column}: loaded as {found[column]}, "
                    f"snapshot says {meta['type']}"
                )
    if problems:
        raise ValueError(
            "the sandbox does not match the pinned snapshot: " + "; ".join(problems)
        )


_IDENTIFIER = re.compile(r"\A[A-Za-z0-9_-]{1,1024}\Z")


def _checked(kind: str, value: str) -> str:
    """A BigQuery project or dataset id, or a raise.

    INFORMATION_SCHEMA cannot be reached through a query parameter — it is
    part of the table path, not a value — so this identifier is interpolated
    and has to be validated instead. Both are module constants at the only
    call site today, but they are parameters, and "the caller is trustworthy"
    is a property of a call site rather than of a signature.
    """
    if not _IDENTIFIER.match(value):
        raise ValueError(f"unsafe BigQuery {kind} identifier: {value!r}")
    return value


def loaded_schema(client: Any, project: str, dataset: str) -> dict[str, dict[str, str]]:
    """The dataset as it actually stands: table -> column -> declared type."""
    project = _checked("project", project)
    dataset = _checked("dataset", dataset)
    # The two interpolated identifiers are validated against _IDENTIFIER
    # immediately above; a path element cannot be passed as a query parameter.
    rows = client.query(
        # trunk-ignore(bandit/B608): validated identifiers, see above
        f"SELECT table_name, column_name, data_type "
        f"FROM `{project}.{dataset}.INFORMATION_SCHEMA.COLUMNS`"
    ).result()
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        out.setdefault(row.table_name, {})[row.column_name] = row.data_type
    return out


def upload(storage_client: Any, path: Path, bucket_name: str) -> str:
    """Stage one Avro file to GCS and return the URI the load job reads.

    `main` used to read `gs://.../<table>.avro` that nothing ever wrote, so
    the first real run would have failed on a missing object after creating
    every table.
    """
    from google.api_core import exceptions

    blob = storage_client.bucket(bucket_name).blob(path.name)
    try:
        blob.upload_from_filename(str(path), content_type="application/octet-stream")
    except exceptions.NotFound as err:
        # Two setup steps nothing else checks, and a stack trace buries both.
        raise SystemExit(
            f"the staging bucket gs://{bucket_name} does not exist. Create it "
            f"and grant the sandbox service account write access, using your "
            f"own identity rather than the key:\n\n"
            f"  gcloud storage buckets create gs://{bucket_name} \\\n"
            f"      --project={SANDBOX_PROJECT} --location=US\n"
            f"  gcloud storage buckets add-iam-policy-binding gs://{bucket_name} \\\n"
            f"      --member=serviceAccount:{SERVICE_ACCOUNT} \\\n"
            f"      --role=roles/storage.objectAdmin\n"
        ) from err
    except exceptions.Forbidden as err:
        raise SystemExit(
            f"the sandbox service account cannot write to gs://{bucket_name}. "
            f"Its project roles are BigQuery-only, which grant nothing in "
            f"Cloud Storage. Grant it object access, using your own identity:"
            f"\n\n"
            f"  gcloud storage buckets add-iam-policy-binding gs://{bucket_name} \\\n"
            f"      --member=serviceAccount:{SERVICE_ACCOUNT} \\\n"
            f"      --role=roles/storage.objectAdmin\n"
        ) from err
    return f"gs://{bucket_name}/{path.name}"


def create_table(client: Any, table: str, schema: list[Any]) -> None:
    """Replace the table with one whose schema IS the pinned snapshot's.

    Replace rather than create-if-missing: a table left over from an earlier
    pin carries that pin's columns, and a load into it would be measured
    against the wrong contract.
    """
    from google.cloud import bigquery

    table_id = f"{SANDBOX_PROJECT}.{SANDBOX_DATASET}.{table}"
    client.delete_table(table_id, not_found_ok=True)
    client.create_table(bigquery.Table(table_id, schema=schema))


def load_table(client: Any, table: str, gcs_uri: str) -> None:
    """Load the Avro into the table `create_table` already shaped.

    No `schema=` here. BigQuery ignores it for AVRO (see the module
    docstring), and passing one would document a guarantee the API does not
    give. The guarantee comes from the pre-created table plus the two
    dispositions below.
    """
    from google.cloud import bigquery

    client.load_table_from_uri(
        gcs_uri,
        f"{SANDBOX_PROJECT}.{SANDBOX_DATASET}.{table}",
        job_config=bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.AVRO,
            # Keeps the schema of the table created above. WRITE_TRUNCATE
            # would replace it with the load job's — i.e. the Avro's.
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE_DATA,
            # Nothing may create a table here except create_table.
            create_disposition=bigquery.CreateDisposition.CREATE_NEVER,
            # Without this a DATE lands as INT64 and a NUMERIC as BYTES, and
            # the load into the typed table fails — loudly, which is right.
            use_avro_logical_types=True,
        ),
    ).result()


def main(argv: list[str] | None = None) -> int:
    from google.cloud import bigquery, storage

    from teamster.cube_sandbox import avro, snapshot

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--avro-dir", type=Path, default=DEFAULT_AVRO_DIR)
    parser.add_argument("--bucket", default=STAGING_BUCKET)
    args = parser.parse_args(argv)

    snap = snapshot.load()
    missing = [
        table
        for table in snap["tables"]
        if not (args.avro_dir / f"{table}.avro").exists()
    ]
    if missing:
        raise SystemExit(
            f"no Avro to load in {args.avro_dir} for: {', '.join(sorted(missing))}. "
            "Run `uv run python -m teamster.cube_sandbox.generate --scale full` first."
        )

    client = bigquery.Client(project=SANDBOX_PROJECT)
    storage_client = storage.Client(project=SANDBOX_PROJECT)

    # Report per table. A silent run and a hung one are indistinguishable, and
    # the full profile spends a long time on the two big facts — long enough
    # that someone will kill a working load believing it stuck.
    total = len(snap["tables"])
    for index, (table, columns) in enumerate(sorted(snap["tables"].items()), start=1):
        path = args.avro_dir / f"{table}.avro"
        size_mb = path.stat().st_size / 1_048_576
        print(f"[{index}/{total}] {table} ({size_mb:.1f} MiB) uploading", flush=True)
        uri = upload(storage_client, path, args.bucket)
        print(f"[{index}/{total}] {table} creating table from the snapshot", flush=True)
        create_table(client, table, avro.bq_schema(table, columns))
        print(f"[{index}/{total}] {table} loading", flush=True)
        load_table(client, table, uri)

    print("verifying every column name and type against the snapshot", flush=True)
    assert_complete(snap, loaded_schema(client, SANDBOX_PROJECT, SANDBOX_DATASET))
    print(f"loaded {total} tables and verified against the snapshot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
