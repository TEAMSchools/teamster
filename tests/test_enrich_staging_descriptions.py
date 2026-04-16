"""Unit tests for scripts/enrich_staging_descriptions.py.

The script filename uses underscores specifically so we can import it.
We use importlib.util rather than changing project-wide pytest config,
keeping the import pattern local to this test file.
"""

from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path
from types import ModuleType

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT = _REPO_ROOT / "scripts" / "enrich_staging_descriptions.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "enrich_staging_descriptions", _SCRIPT
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_script_module_loads() -> None:
    module = _load_script()
    assert callable(module.main)


# Minimal YAML fixture representing a staging model
YAML_FIXTURE = """\
models:
  - name: stg_powerschool__students
    columns:
      - name: id
        data_type: int64
        data_tests:
          - unique:
              config:
                severity: error
      - name: first_name
        data_type: string
      - name: ssn
        data_type: string
      - name: grade_level
        data_type: string
        description: Existing hand-written description.
"""

# Mapping entries for the fixture
MAPPING_ENTRIES = [
    {
        "model": "stg_powerschool__students",
        "column": "id",
        "description": "Auto-incrementing unique record identifier.",
        "contains_pii": False,
    },
    {
        "model": "stg_powerschool__students",
        "column": "first_name",
        "description": "The student's legal first name.",
        "contains_pii": True,
    },
    {
        "model": "stg_powerschool__students",
        "column": "ssn",
        "description": "Social security number.",
        "contains_pii": True,
    },
    {
        "model": "stg_powerschool__students",
        "column": "grade_level",
        "description": "PDF description that should be IGNORED.",
        "contains_pii": False,
    },
]


class TestEnrichYamlData:
    """Test the YAML enrichment function."""

    def test_adds_description_to_empty_column(self) -> None:
        module = _load_script()
        doc = yaml.safe_load(YAML_FIXTURE)
        result = module.enrich_yaml_data(doc, MAPPING_ENTRIES)
        columns = result["models"][0]["columns"]
        by_name = {c["name"]: c for c in columns}
        assert by_name["first_name"]["description"] == (
            "The student's legal first name."
        )

    def test_preserves_existing_description(self) -> None:
        module = _load_script()
        doc = yaml.safe_load(YAML_FIXTURE)
        result = module.enrich_yaml_data(doc, MAPPING_ENTRIES)
        columns = result["models"][0]["columns"]
        by_name = {c["name"]: c for c in columns}
        assert by_name["grade_level"]["description"] == (
            "Existing hand-written description."
        )

    def test_adds_pii_flag(self) -> None:
        module = _load_script()
        doc = yaml.safe_load(YAML_FIXTURE)
        result = module.enrich_yaml_data(doc, MAPPING_ENTRIES)
        columns = result["models"][0]["columns"]
        by_name = {c["name"]: c for c in columns}
        assert by_name["ssn"]["config"]["meta"]["contains_pii"] is True
        assert by_name["id"]["config"]["meta"]["contains_pii"] is False

    def test_pii_flag_overwrites_existing(self) -> None:
        """PII classification from PDF is authoritative -- overwrites."""
        module = _load_script()
        fixture_with_pii = YAML_FIXTURE.replace(
            "      - name: ssn\n        data_type: string",
            (
                "      - name: ssn\n        data_type: string\n"
                "        config:\n          meta:\n            contains_pii: false"
            ),
        )
        doc = yaml.safe_load(fixture_with_pii)
        result = module.enrich_yaml_data(doc, MAPPING_ENTRIES)
        columns = result["models"][0]["columns"]
        by_name = {c["name"]: c for c in columns}
        assert by_name["ssn"]["config"]["meta"]["contains_pii"] is True

    def test_preserves_data_tests(self) -> None:
        module = _load_script()
        doc = yaml.safe_load(YAML_FIXTURE)
        result = module.enrich_yaml_data(doc, MAPPING_ENTRIES)
        columns = result["models"][0]["columns"]
        by_name = {c["name"]: c for c in columns}
        assert "data_tests" in by_name["id"]
        assert len(by_name["id"]["data_tests"]) == 1

    def test_returns_enrichment_stats(self) -> None:
        module = _load_script()
        doc = yaml.safe_load(YAML_FIXTURE)
        result, stats = module.enrich_yaml_data(doc, MAPPING_ENTRIES, return_stats=True)
        assert stats["enriched"] == 3  # id, first_name, ssn
        assert stats["skipped"] == 1  # grade_level (existing description)
        assert stats["total"] == 4

    def test_unmatched_columns_not_modified(self) -> None:
        """Columns with no mapping entry stay untouched."""
        module = _load_script()
        doc = yaml.safe_load(YAML_FIXTURE)
        # Only provide mapping for 'id'
        partial_entries = [MAPPING_ENTRIES[0]]
        result = module.enrich_yaml_data(doc, partial_entries)
        columns = result["models"][0]["columns"]
        by_name = {c["name"]: c for c in columns}
        assert "description" not in by_name["first_name"]
        assert "config" not in by_name["first_name"]


class TestFindYamlFile:
    """Test finding the YAML file for a given model name."""

    def test_finds_powerschool_students(self) -> None:
        module = _load_script()
        path = module.find_yaml_file("stg_powerschool__students")
        assert path is not None
        assert path.name == "stg_powerschool__students.yml"
        assert path.exists()

    def test_finds_adp_workers(self) -> None:
        module = _load_script()
        path = module.find_yaml_file("stg_adp_workforce_now__workers")
        assert path is not None
        assert path.name == "stg_adp_workforce_now__workers.yml"
        assert path.exists()

    def test_returns_none_for_nonexistent(self) -> None:
        module = _load_script()
        path = module.find_yaml_file("stg_nonexistent__model")
        assert path is None


class TestWriteYaml:
    """Test YAML write output format."""

    def test_write_preserves_key_order(self) -> None:
        module = _load_script()
        doc = yaml.safe_load(YAML_FIXTURE)
        result = module.enrich_yaml_data(doc, MAPPING_ENTRIES)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as fh:
            module.write_yaml(result, fh)
            tmp_path = Path(fh.name)

        try:
            content = tmp_path.read_text(encoding="utf-8")
            # models: should appear before columns
            assert content.index("models:") < content.index("columns:")
            # name: should appear before data_type:
            assert content.index("- name:") < content.index("data_type:")
        finally:
            tmp_path.unlink()

    def test_write_roundtrip(self) -> None:
        module = _load_script()
        doc = yaml.safe_load(YAML_FIXTURE)
        result = module.enrich_yaml_data(doc, MAPPING_ENTRIES)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as fh:
            module.write_yaml(result, fh)
            tmp_path = Path(fh.name)

        try:
            with tmp_path.open(encoding="utf-8") as fh:
                reloaded = yaml.safe_load(fh)
            columns = reloaded["models"][0]["columns"]
            by_name = {c["name"]: c for c in columns}
            assert by_name["first_name"]["description"] == (
                "The student's legal first name."
            )
            assert by_name["ssn"]["config"]["meta"]["contains_pii"] is True
        finally:
            tmp_path.unlink()
