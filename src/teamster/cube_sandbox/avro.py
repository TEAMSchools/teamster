"""Avro output and the matching explicit BigQuery schema.

Creating the table from the snapshot rather than letting BigQuery infer types
from the Avro is what makes the two match by construction: `bq_schema` builds
the table's columns directly from the snapshot's declared types, so the
deployed schema equals the snapshot by construction rather than by whatever
fastavro's writer happens to pick when BigQuery infers from the file.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import fastavro
from google.cloud.bigquery import SchemaField

# BigQuery NUMERIC is exactly DECIMAL(38, 9) — 38 digits of precision, 9 of
# scale. These two numbers are the mapping, not decoration: narrow either and
# fastavro silently truncates on write, the load succeeds, and the sandbox
# carries quietly wrong money and rate values. The snapshot has four NUMERIC
# columns today.
NUMERIC_PRECISION = 38
NUMERIC_SCALE = 9

_LOGICAL: dict[str, Any] = {
    "STRING": "string",
    "INT64": "long",
    "FLOAT64": "double",
    "BOOL": "boolean",
    "DATE": {"type": "int", "logicalType": "date"},
    "DATETIME": {"type": "long", "logicalType": "timestamp-micros"},
    "TIMESTAMP": {"type": "long", "logicalType": "timestamp-micros"},
    "NUMERIC": {
        "type": "bytes",
        "logicalType": "decimal",
        "precision": NUMERIC_PRECISION,
        "scale": NUMERIC_SCALE,
    },
}


_ARRAY_STRUCT = re.compile(r"\AARRAY<STRUCT<(?P<body>.+)>>\Z", re.DOTALL)


def struct_fields(kind: str) -> list[tuple[str, str]] | None:
    """`(name, type)` per field of an `ARRAY<STRUCT<...>>`, or None.

    Splits at depth zero so a nested `ARRAY<...>` or `STRUCT<...>` inside a
    field's own type does not get cut at its internal commas. Nothing in the
    snapshot nests that far today, and a split that only works for flat
    structs would fail silently on the first column that does — producing
    field names like `region_key STRING, location_abbreviation` rather than
    an error.
    """
    match = _ARRAY_STRUCT.match(kind.strip())
    if match is None:
        return None
    body, depth, current = match.group("body"), 0, []
    parts: list[str] = []
    for char in body:
        if char in "<(":
            depth += 1
        elif char in ">)":
            depth -= 1
        if char == "," and depth == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(char)
    parts.append("".join(current))

    out = []
    for part in parts:
        name, _, field_type = part.strip().partition(" ")
        if not name or not field_type:
            raise ValueError(f"cannot parse struct field {part.strip()!r} in {kind}")
        out.append((name, field_type.strip()))
    return out


def avro_schema(table: str, columns: dict[str, dict[str, Any]]) -> dict[str, Any]:
    fields = []
    for name, meta in columns.items():
        nested = struct_fields(meta["type"])
        if nested is not None:
            # A BigQuery REPEATED field is never null — an empty array is the
            # empty case — so this branch does not take the null union below.
            # Wrapping it in one would let a None through to a REQUIRED
            # BigQuery column and fail the load rather than the write.
            fields.append(
                {
                    "name": name,
                    "type": {
                        "type": "array",
                        "items": {
                            "type": "record",
                            "name": f"{table}__{name}",
                            "fields": [
                                {"name": field, "type": ["null", _LOGICAL[field_type]]}
                                for field, field_type in nested
                            ],
                        },
                    },
                }
            )
            continue
        base = _LOGICAL.get(meta["type"])
        if base is None:
            raise ValueError(f"{table}.{name}: no Avro mapping for {meta['type']}")
        # Null-first union ordering: fastavro resolves an untagged Python
        # value (None or the plain scalar) against branches in this order,
        # so putting "null" first is what lets a bare `None` in a row dict
        # resolve without a tagged {"branch": value} wrapper.
        fields.append(
            {"name": name, "type": ["null", base] if meta["nullable"] else base}
        )
    return {"type": "record", "name": table, "fields": fields}


def bq_schema(table: str, columns: dict[str, dict[str, Any]]) -> list[SchemaField]:
    """Build the table's BigQuery schema straight from the snapshot's declared types.

    `SchemaField.field_type` accepts standard-SQL type names (`STRING`,
    `INT64`, `DATE`, ...) directly, so the snapshot's `type` string is passed
    through unchanged rather than translated through `_LOGICAL` — the
    deployed field type is then verifiably the snapshot's type string, not a
    lookalike chosen by a second mapping table.
    """
    fields = []
    for name, meta in columns.items():
        nested = struct_fields(meta["type"])
        if nested is not None:
            # REPEATED, not REQUIRED: BigQuery has no nullable array, and an
            # `ARRAY<STRUCT<...>>` column is a RECORD field repeated. Passing
            # the raw type string here, as the scalar branch does, would have
            # BigQuery reject `ARRAY<STRUCT<...>>` as a field type.
            fields.append(
                SchemaField(
                    name,
                    "RECORD",
                    mode="REPEATED",
                    fields=[
                        SchemaField(field, field_type, mode="NULLABLE")
                        for field, field_type in nested
                    ],
                )
            )
            continue
        if meta["type"] not in _LOGICAL:
            raise ValueError(f"{table}.{name}: no BigQuery mapping for {meta['type']}")
        mode = "NULLABLE" if meta["nullable"] else "REQUIRED"
        fields.append(SchemaField(name, meta["type"], mode=mode))
    return fields


def write(path: Path, schema: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    with Path(path).open("wb") as f:
        fastavro.writer(f, schema, rows)
