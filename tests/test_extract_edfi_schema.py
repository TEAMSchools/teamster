"""Tests for scripts/extract_edfi_schema.py."""

from __future__ import annotations

import csv
import importlib.util
import io
from pathlib import Path

import yaml

_SCRIPT = Path("scripts/extract_edfi_schema.py")


def _load_script():
    spec = importlib.util.spec_from_file_location("extract_edfi_schema", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_camel_to_snake_simple() -> None:
    module = _load_script()
    assert module._camel_to_snake("birthDate") == "birth_date"


def test_camel_to_snake_consecutive_caps() -> None:
    module = _load_script()
    assert module._camel_to_snake("studentUniqueId") == "student_unique_id"


def test_camel_to_snake_all_lower() -> None:
    module = _load_script()
    assert module._camel_to_snake("name") == "name"


def test_camel_to_snake_leading_lower() -> None:
    module = _load_script()
    assert module._camel_to_snake("firstName") == "first_name"


def test_camel_to_snake_descriptor_suffix() -> None:
    module = _load_script()
    assert module._camel_to_snake("birthSexDescriptor") == "birth_sex_descriptor"


def test_camel_to_snake_acronym_in_name() -> None:
    module = _load_script()
    assert module._camel_to_snake("iepBeginDate") == "iep_begin_date"


FIXTURE_PATH = Path("tests/fixtures/edfi_sample_spec.yml")


def test_extract_attributes_returns_all_properties() -> None:
    module = _load_script()
    with FIXTURE_PATH.open() as fh:
        spec = yaml.safe_load(fh)
    rows = module._extract_attributes(spec)
    assert len(rows) == 10


def test_extract_attributes_row_structure() -> None:
    module = _load_script()
    with FIXTURE_PATH.open() as fh:
        spec = yaml.safe_load(fh)
    rows = module._extract_attributes(spec)
    first = rows[0]
    assert set(first.keys()) == {
        "entity",
        "attribute_camel",
        "attribute_snake",
        "description",
    }


def test_extract_attributes_snake_conversion() -> None:
    module = _load_script()
    with FIXTURE_PATH.open() as fh:
        spec = yaml.safe_load(fh)
    rows = module._extract_attributes(spec)
    birth_dates = [r for r in rows if r["attribute_camel"] == "birthDate"]
    assert all(r["attribute_snake"] == "birth_date" for r in birth_dates)
    assert len(birth_dates) == 2  # student + staff


def test_extract_attributes_preserves_descriptions() -> None:
    module = _load_script()
    with FIXTURE_PATH.open() as fh:
        spec = yaml.safe_load(fh)
    rows = module._extract_attributes(spec)
    entry_dates = [r for r in rows if r["attribute_camel"] == "entryDate"]
    assert len(entry_dates) == 1
    assert "enters and begins to receive" in entry_dates[0]["description"]


def test_write_csv_header_and_rows() -> None:
    module = _load_script()
    rows = [
        {
            "entity": "edFi_student",
            "attribute_camel": "birthDate",
            "attribute_snake": "birth_date",
            "description": "Date of birth.",
        },
    ]
    buf = io.StringIO()
    module._write_csv(rows, buf)
    buf.seek(0)
    reader = csv.DictReader(buf)
    result = list(reader)
    assert len(result) == 1
    assert result[0]["entity"] == "edFi_student"
    assert result[0]["attribute_snake"] == "birth_date"


def test_write_csv_field_order() -> None:
    module = _load_script()
    rows = [
        {
            "entity": "edFi_student",
            "attribute_camel": "firstName",
            "attribute_snake": "first_name",
            "description": "First name.",
        },
    ]
    buf = io.StringIO()
    module._write_csv(rows, buf)
    buf.seek(0)
    header = buf.readline().strip()
    assert header == "entity,attribute_camel,attribute_snake,description"
