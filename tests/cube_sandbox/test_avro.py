from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import fastavro
import pytest

from teamster.cube_sandbox import avro, snapshot


def test_nullable_columns_become_unions() -> None:
    schema = avro.avro_schema("dim_x", {"a": {"type": "STRING", "nullable": True}})
    field = schema["fields"][0]
    # Avro encodes null in the type, which is why this is not CSV: the
    # manifest's central assertion is about nulls.
    assert field["type"] == ["null", "string"]


def test_logical_types_map_exactly() -> None:
    schema = avro.avro_schema(
        "dim_x",
        {
            "d": {"type": "DATE", "nullable": False},
            "t": {"type": "TIMESTAMP", "nullable": False},
            "n": {"type": "NUMERIC", "nullable": False},
        },
    )
    by_name = {f["name"]: f["type"] for f in schema["fields"]}
    assert by_name["d"] == {"type": "int", "logicalType": "date"}
    assert by_name["t"] == {"type": "long", "logicalType": "timestamp-micros"}
    # The whole NUMERIC mapping, not just its logicalType. BigQuery NUMERIC
    # is exactly DECIMAL(38, 9); a narrowing of either number passes a
    # logicalType-only assertion, truncates silently on write, and loads
    # clean — so the sandbox would carry wrong money and rate values with
    # nothing red anywhere.
    assert by_name["n"] == {
        "type": "bytes",
        "logicalType": "decimal",
        "precision": 38,
        "scale": 9,
    }


def test_the_snapshots_numeric_columns_all_take_that_mapping() -> None:
    # Four NUMERIC columns in the pinned snapshot, so the precision and scale
    # above are load-bearing rather than hypothetical.
    snap = json.loads(
        (
            Path(__file__).parents[2]
            / "src"
            / "cube"
            / "sandbox"
            / "schema_snapshot.json"
        ).read_text()
    )
    numeric = [
        (table, column)
        for table, columns in snap["tables"].items()
        for column, meta in columns.items()
        if meta["type"] == "NUMERIC"
    ]
    assert numeric
    for table, column in numeric:
        field = avro.avro_schema(table, {column: {"type": "NUMERIC", "nullable": True}})
        assert field["fields"][0]["type"][1]["precision"] == avro.NUMERIC_PRECISION
        assert field["fields"][0]["type"][1]["scale"] == avro.NUMERIC_SCALE


def test_an_unmapped_type_fails_loudly() -> None:
    # Letting this through would have BigQuery coerce at load time, and the
    # mismatch would surface as wrong data rather than a failed build.
    with pytest.raises(ValueError, match="no Avro mapping for GEOGRAPHY"):
        avro.avro_schema("dim_x", {"g": {"type": "GEOGRAPHY", "nullable": True}})


def test_bq_schema_type_and_mode_match_snapshot() -> None:
    # Pins the two things that matter for `bq_schema`: the deployed field
    # type is literally the snapshot's declared type string, and the mode
    # tracks the snapshot's `nullable` flag exactly. A wrong mode here is how
    # a column that should reject nulls silently accepts them instead.
    columns = {
        "required_col": {"type": "INT64", "nullable": False},
        "nullable_col": {"type": "STRING", "nullable": True},
    }
    fields = {f.name: f for f in avro.bq_schema("dim_x", columns)}

    assert fields["required_col"].field_type == "INT64"
    assert fields["required_col"].mode == "REQUIRED"
    assert fields["nullable_col"].field_type == "STRING"
    assert fields["nullable_col"].mode == "NULLABLE"


def test_bq_schema_rejects_an_unmapped_type() -> None:
    with pytest.raises(ValueError, match="no BigQuery mapping for GEOGRAPHY"):
        avro.bq_schema("dim_x", {"g": {"type": "GEOGRAPHY", "nullable": True}})


def test_every_snapshot_type_has_a_mapping() -> None:
    # Reads the committed snapshot directly: a future production column
    # arriving with a type nothing here handles must fail this test, not
    # deep inside a load.
    snap = snapshot.load()
    types_in_snapshot = {
        meta["type"] for columns in snap["tables"].values() for meta in columns.values()
    }
    # A nested type is mapped by `struct_fields` rather than by `_LOGICAL`,
    # and its FIELD types still have to be in `_LOGICAL` — a struct carrying
    # an unmapped field type would otherwise pass here and fail at write.
    unmapped = set()
    for kind in types_in_snapshot:
        nested = avro.struct_fields(kind)
        if nested is None:
            if kind not in avro._LOGICAL:
                unmapped.add(kind)
            continue
        unmapped |= {
            field_type for _, field_type in nested if field_type not in avro._LOGICAL
        }
    assert not unmapped, (
        f"types in schema_snapshot.json with no Avro/BQ mapping: {unmapped}"
    )


def test_write_round_trips_a_nullable_union(tmp_path: Path) -> None:
    schema = avro.avro_schema(
        "dim_x",
        {
            "a": {"type": "STRING", "nullable": True},
            "b": {"type": "INT64", "nullable": False},
        },
    )
    rows: list[dict[str, Any]] = [
        {"a": "hello", "b": 1},
        {"a": None, "b": 2},
    ]
    out_path = tmp_path / "dim_x.avro"

    avro.write(out_path, schema, rows)

    with out_path.open("rb") as f:
        read_back = list(fastavro.reader(f))
    assert read_back == rows


# --- nested ARRAY<STRUCT<...>> --------------------------------------------

_GRANTS = (
    "ARRAY<STRUCT<location_scope STRING, region_key STRING, "
    "location_abbreviation STRING, includes_student_data BOOL, "
    "includes_staff_data BOOL>>"
)


def test_struct_fields_parses_an_array_of_struct() -> None:
    assert avro.struct_fields(_GRANTS) == [
        ("location_scope", "STRING"),
        ("region_key", "STRING"),
        ("location_abbreviation", "STRING"),
        ("includes_student_data", "BOOL"),
        ("includes_staff_data", "BOOL"),
    ]


def test_struct_fields_returns_none_for_a_scalar() -> None:
    assert avro.struct_fields("STRING") is None
    assert avro.struct_fields("NUMERIC") is None


def test_struct_fields_splits_at_depth_zero_only() -> None:
    # A comma inside a nested type is not a field separator. Splitting on
    # every comma yields field names like "region_key STRING" attached to the
    # wrong type, which then maps to nothing and fails far from here.
    nested = avro.struct_fields(
        "ARRAY<STRUCT<a STRING, b ARRAY<STRUCT<c STRING, d BOOL>>, e INT64>>"
    )

    assert nested == [
        ("a", "STRING"),
        ("b", "ARRAY<STRUCT<c STRING, d BOOL>>"),
        ("e", "INT64"),
    ]


def test_a_nested_column_is_an_avro_array_of_records() -> None:
    schema = avro.avro_schema("dim_x", {"grants": {"type": _GRANTS, "nullable": False}})
    # Through Any: the schema dict is heterogeneous, so pyright types this
    # value as a union of every branch and rejects the subscript.
    nested: Any = schema["fields"][0]["type"]

    assert nested["type"] == "array"
    assert nested["items"]["type"] == "record"
    assert [f["name"] for f in nested["items"]["fields"]] == [
        "location_scope",
        "region_key",
        "location_abbreviation",
        "includes_student_data",
        "includes_staff_data",
    ]


def test_a_nested_column_takes_no_null_union() -> None:
    # BigQuery has no nullable array — the empty case is an empty array. A
    # null union here would let None through to a REQUIRED column and fail
    # the load rather than the write.
    schema = avro.avro_schema("dim_x", {"grants": {"type": _GRANTS, "nullable": False}})

    assert "null" not in schema["fields"][0]["type"]


def test_a_nested_column_is_a_repeated_bigquery_record() -> None:
    field = avro.bq_schema("dim_x", {"grants": {"type": _GRANTS, "nullable": False}})[0]

    assert field.field_type == "RECORD"
    assert field.mode == "REPEATED"
    assert [(f.name, f.field_type) for f in field.fields][:2] == [
        ("location_scope", "STRING"),
        ("region_key", "STRING"),
    ]


def test_a_nested_column_round_trips_through_a_written_file(tmp_path: Path) -> None:
    schema = avro.avro_schema("dim_x", {"grants": {"type": _GRANTS, "nullable": False}})
    grant = {
        "location_scope": "school",
        "region_key": None,
        "location_abbreviation": "ABC",
        "includes_student_data": True,
        "includes_staff_data": False,
    }
    path = tmp_path / "dim_x.avro"

    avro.write(path, schema, [{"grants": []}, {"grants": [grant]}])

    with path.open("rb") as handle:
        read_back: list[Any] = list(fastavro.reader(handle))
    assert read_back[0]["grants"] == []
    assert read_back[1]["grants"] == [grant]
