"""Tests for scripts/extract_edfi_schema.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = Path("scripts/extract_edfi_schema.py")


def _load_script():
    spec = importlib.util.spec_from_file_location("extract_edfi_schema", _SCRIPT)
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
