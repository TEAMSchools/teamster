"""Re-encode an asset's partitioned GCS Avro files to its current schema.

Use after a schema evolution where only some partitions were re-materialized,
leaving the external table with heterogeneous Avro writer schemas. A BigQuery
external-table read resolves one reader schema across the scanned files and
drops any field absent from the older files — for the whole scan, including the
newer files that contain it. Re-encoding every file to the current schema makes
the files homogeneous so the field reads correctly. See issue #4151.

`reencode_avro_blobs` is generic (any asset key + target schema); the CLI wires
GCS and resolves the schema from a `module:attribute` spec.

Dry run (default) — lists what would change, writes nothing:

    uv run scripts/reencode_avro_partitions.py \
        --asset-key kipptaf/adp/workforce_now/workers \
        --schema teamster.code_locations.kipptaf.adp.workforce_now.api.schema:WORKER_SCHEMA

Add --execute to archive each original and overwrite it in place. Requires GCS
read/write on the target bucket (run where ADC has those permissions).
"""

import importlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from io import BytesIO

import click
import dagster as dg
from dagster_shared import check
from fastavro import parse_schema, reader, writer
from fastavro.read import SchemaResolutionError
from fastavro.schema import SchemaParseException, to_parsing_canonical_form
from fastavro.types import Schema
from google.api_core.exceptions import GoogleAPIError
from google.cloud import storage

from teamster.core.resources import GCS_RESOURCE

# Bytes fetched for the header-only schema check. The Avro writer schema lives in
# the file header, so a small first read resolves the skip/re-encode decision
# without downloading or decoding the record body. GCS's default BlobReader chunk
# is ~40 MB, which would pull the whole partition just to read the header.
_HEADER_CHUNK_SIZE = 64 * 1024


@dataclass
class ReencodeSummary:
    """Per-action counts from a re-encode pass over one asset's blobs."""

    total: int = 0
    skipped: int = 0
    reencoded: int = 0
    archived: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class BlobResult:
    """Outcome of processing one blob. Holds no shared state, so each blob can be
    processed on its own worker thread and the results aggregated afterward."""

    skipped: bool = False
    reencoded: bool = False
    archived: bool = False
    error: str | None = None
    messages: list[str] = field(default_factory=list)


def _process_blob(
    blob: storage.Blob,
    bucket: storage.Bucket,
    *,
    parsed: Schema,
    target_canonical: str,
    asset_prefix: str,
    archive_prefix: str,
    dry_run: bool,
    archive: bool,
) -> BlobResult:
    """Process one blob: header-only schema check, then re-encode if needed.

    The schema decision reads only the Avro header (``_HEADER_CHUNK_SIZE``), so
    skipped files and dry-run reports never download or decode the record body —
    the record stream is read only when an actual re-encode is performed. Catches
    per-blob errors into the result rather than raising, so one bad partition does
    not abort the pool.
    """
    result = BlobResult()
    blob_name = check.not_none(value=blob.name)

    try:
        with blob.open(mode="rb", chunk_size=_HEADER_CHUNK_SIZE) as fo:
            # trunk-ignore(pyright/reportArgumentType): GCS BlobReader is a binary file-like; fastavro stubs type fo as IO[Unknown]
            writer_schema = check.not_none(value=reader(fo).writer_schema)

        if to_parsing_canonical_form(writer_schema) == target_canonical:
            result.skipped = True
            result.messages.append(f"SKIP (already target schema): {blob_name}")
            return result

        if dry_run:
            result.reencoded = True
            result.messages.append(f"WOULD RE-ENCODE: {blob_name}")
            return result

        if archive:
            archive_name = blob_name.replace(
                asset_prefix + "/", archive_prefix + "/", 1
            )
            bucket.copy_blob(
                blob=blob, destination_bucket=bucket, new_name=archive_name
            )
            result.archived = True
            result.messages.append(f"ARCHIVED -> {archive_name}")

        # Re-encode: full body read (default chunk size for an efficient stream).
        with blob.open(mode="rb") as fo:
            # trunk-ignore(pyright/reportArgumentType): GCS BlobReader is a binary file-like; fastavro stubs type fo as IO[Unknown]
            records = list(reader(fo))

        buf = BytesIO()
        writer(fo=buf, schema=parsed, records=records, codec="snappy")
        buf.seek(0)
        blob.upload_from_file(file_obj=buf)
        result.reencoded = True
        result.messages.append(
            f"RE-ENCODED in place ({len(records)} records): {blob_name}"
        )
    except (
        GoogleAPIError,
        SchemaResolutionError,
        SchemaParseException,
        ValueError,
        OSError,
        EOFError,
    ) as e:
        result.error = f"{blob_name}: {e}"

    return result


def reencode_avro_blobs(
    bucket: storage.Bucket,
    asset_key: list[str],
    schema: Schema,
    *,
    dry_run: bool = True,
    archive: bool = True,
    workers: int = 8,
) -> ReencodeSummary:
    """Re-encode every partition Avro file of an asset to a target schema.

    Files whose writer schema already matches ``schema`` (compared by Avro
    parsing canonical form, which ignores aliases/defaults/docs) are skipped, so
    the pass is idempotent and safe to re-run. When not a dry run, each original
    blob is optionally copied to a sibling ``<asset>_archive/`` path (outside the
    external-table glob) before being overwritten in place with the re-encoded
    records.

    The schema check reads only the Avro header, so skips and dry-run reports
    never decode the record body (the dominant cost when most partitions already
    match). Blobs are processed concurrently on a thread pool — the work is
    network-bound, so threads (not processes) give the speedup. Because each
    re-encode loads a full partition into memory, ``workers`` also bounds peak
    memory to roughly that many partitions at once.

    fastavro fills absent optional fields with their schema defaults, so this is
    valid only for additive (superset) schema evolution — fields present in the
    old files but missing from ``schema`` would be dropped.

    Progress is written to stdout via ``click.echo``; per-blob errors to stderr.

    Args:
        bucket: The GCS bucket holding the asset's blobs.
        asset_key: Dagster asset key parts, e.g. ``["kipptaf", "adp", ...]``.
        schema: Target Avro schema (raw dict or already parsed).
        dry_run: When True (default), report actions without writing.
        archive: When True (default), copy each original to an archive sibling
            before overwriting it in place.
        workers: Max concurrent blobs processed; also caps peak memory.

    Returns:
        A ``ReencodeSummary`` with per-action counts and any per-blob errors.
    """
    parsed = parse_schema(schema)
    target_canonical = to_parsing_canonical_form(parsed)

    asset_prefix = "dagster/" + "/".join(asset_key)
    archive_prefix = asset_prefix + "_archive"

    summary = ReencodeSummary()
    blobs = list(bucket.list_blobs(match_glob=f"{asset_prefix}/**/data"))

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                _process_blob,
                blob,
                bucket,
                parsed=parsed,
                target_canonical=target_canonical,
                asset_prefix=asset_prefix,
                archive_prefix=archive_prefix,
                dry_run=dry_run,
                archive=archive,
            )
            for blob in blobs
        ]

        for future in as_completed(futures):
            result = future.result()
            summary.total += 1
            summary.skipped += int(result.skipped)
            summary.reencoded += int(result.reencoded)
            summary.archived += int(result.archived)

            for message in result.messages:
                click.echo(message)

            if result.error is not None:
                summary.errors.append(result.error)
                click.echo(f"ERROR re-encoding {result.error}", err=True)

    click.echo(
        f"done: total={summary.total} skipped={summary.skipped} "
        f"reencoded={summary.reencoded} archived={summary.archived} "
        f"errors={len(summary.errors)}"
    )
    return summary


def resolve_schema(spec: str) -> Schema:
    """Import a schema object from a ``module:attribute`` spec."""
    module_name, _, attr = spec.partition(":")

    if not attr:
        raise ValueError(f"--schema must be 'module:attribute', got: {spec!r}")

    return getattr(importlib.import_module(module_name), attr)


@click.command()
@click.option(
    "--asset-key",
    required=True,
    help="slash-delimited asset key, e.g. kipptaf/adp/workforce_now/workers",
)
@click.option(
    "--schema",
    "schema_spec",
    required=True,
    help="target schema as 'module:attribute' (e.g. '...schema:WORKER_SCHEMA')",
)
@click.option(
    "--bucket",
    "bucket_name",
    default=None,
    help="GCS bucket (default: teamster-<first asset key part>)",
)
@click.option("--execute", is_flag=True, help="write changes (default is a dry run)")
@click.option(
    "--no-archive",
    is_flag=True,
    help="skip copying each original to an archive sibling before overwrite",
)
@click.option(
    "--workers",
    default=8,
    show_default=True,
    type=click.IntRange(min=1),
    help="max concurrent blobs processed; also caps peak memory",
)
def main(
    asset_key: str,
    schema_spec: str,
    bucket_name: str | None,
    execute: bool,
    no_archive: bool,
    workers: int,
) -> None:
    """Re-encode an asset's partitioned GCS Avro files to its current schema."""
    try:
        schema = resolve_schema(schema_spec)
    except (ImportError, AttributeError, ValueError) as e:
        click.echo(f"Error: could not resolve --schema {schema_spec!r}: {e}", err=True)
        raise SystemExit(1) from e

    asset_key_parts = asset_key.strip("/").split("/")
    bucket_name = bucket_name or f"teamster-{asset_key_parts[0]}"

    with dg.build_resources(resources={"gcs": GCS_RESOURCE}) as resources:
        bucket = resources.gcs.bucket(bucket_name)

        summary = reencode_avro_blobs(
            bucket=bucket,
            asset_key=asset_key_parts,
            schema=schema,
            dry_run=not execute,
            archive=not no_archive,
            workers=workers,
        )

    if summary.errors:
        click.echo(f"completed with {len(summary.errors)} error(s)", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
