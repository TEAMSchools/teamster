"""Tests for scripts/tableau-analyze-workbook.py."""

from __future__ import annotations

import io
import json
import pathlib
import subprocess
import zipfile

import pytest

# Import the script module directly via importlib since it uses inline metadata
SCRIPT_PATH = pathlib.Path("scripts/tableau-analyze-workbook.py")
FIXTURES = pathlib.Path("tests/scripts/fixtures")
MINIMAL_TWB = FIXTURES / "minimal.twb"
MULTI_DS_TWB = FIXTURES / "multi_datasource.twb"


# ── Helpers ──────────────────────────────────────────────────────────────────


def _load_module():
    """Import the script as a module."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "tableau_analyze_workbook", SCRIPT_PATH
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_twbx(twb_path: pathlib.Path) -> bytes:
    """Create an in-memory .twbx zip archive from a .twb file."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.write(twb_path, twb_path.name)
    return buf.getvalue()


@pytest.fixture(scope="module")
def mod():
    """Loaded script module."""
    return _load_module()


@pytest.fixture(scope="module")
def minimal_twb_bytes() -> bytes:
    return MINIMAL_TWB.read_bytes()


@pytest.fixture(scope="module")
def multi_ds_twb_bytes() -> bytes:
    return MULTI_DS_TWB.read_bytes()


# ── Zip extraction ──────────────────────────────────────────────────────────


class TestZipExtraction:
    def test_extract_twb_bytes_plain(self, mod):
        result = mod.extract_twb_bytes(MINIMAL_TWB)
        assert b"<workbook>" in result

    def test_extract_twb_bytes_twbx(self, mod, tmp_path):
        twbx_path = tmp_path / "test.twbx"
        twbx_path.write_bytes(_make_twbx(MINIMAL_TWB))
        result = mod.extract_twb_bytes(twbx_path)
        assert b"<workbook>" in result

    def test_extract_twb_bytes_from_bytes(self, mod):
        twbx_bytes = _make_twbx(MINIMAL_TWB)
        result = mod.extract_twb_bytes_from_bytes(twbx_bytes)
        assert b"<workbook>" in result


# ── Datasource listing ──────────────────────────────────────────────────────


class TestListDatasources:
    def test_minimal_single_datasource(self, mod, minimal_twb_bytes):
        sources = mod.list_datasources(minimal_twb_bytes)
        assert len(sources) == 1
        assert sources[0]["caption"] == (
            "rpt_tableau__test_dashboard (kipptaf_tableau)"
        )

    def test_multi_datasource_dedup(self, mod, multi_ds_twb_bytes):
        sources = mod.list_datasources(multi_ds_twb_bytes)
        captions = [s["caption"] for s in sources]
        assert len(captions) == 2
        assert "rpt_tableau__grades (kipptaf_tableau)" in captions
        assert "rpt_tableau__attendance (kipptaf_tableau)" in captions

    def test_parameters_skipped(self, mod, minimal_twb_bytes):
        sources = mod.list_datasources(minimal_twb_bytes)
        captions = [s["caption"] for s in sources]
        assert "Parameters" not in captions


# ── Internal field filtering ────────────────────────────────────────────────


class TestFieldFiltering:
    def test_internal_fields_skipped(self, mod, minimal_twb_bytes):
        parsed = mod.parse_datasource(
            minimal_twb_bytes,
            "rpt_tableau__test_dashboard (kipptaf_tableau)",
        )
        field_names = [f["name"] for f in parsed["fields"]]
        assert "[:internal_field]" not in field_names
        assert "[Number of Records]" not in field_names
        assert "" not in field_names

    def test_user_fields_present(self, mod, minimal_twb_bytes):
        parsed = mod.parse_datasource(
            minimal_twb_bytes,
            "rpt_tableau__test_dashboard (kipptaf_tableau)",
        )
        field_names = [f["name"] for f in parsed["fields"]]
        assert "Attendance Rate" in field_names
        assert "student_number" in field_names
        assert "grade_level" in field_names
        assert "Student Avg" in field_names


# ── Calc name resolution ───────────────────────────────────────────────────


class TestCalcNameResolution:
    def test_formula_uses_caption(self, mod, minimal_twb_bytes):
        parsed = mod.parse_datasource(
            minimal_twb_bytes,
            "rpt_tableau__test_dashboard (kipptaf_tableau)",
        )
        att_field = next(f for f in parsed["fields"] if f["name"] == "Attendance Rate")
        assert att_field["is_calculated"] is True
        # Formula should NOT contain Calculation_1234
        assert "Calculation_1234" not in att_field["formula"]


# ── LOD detection ───────────────────────────────────────────────────────────


class TestLODDetection:
    def test_lod_field_flagged(self, mod, minimal_twb_bytes):
        parsed = mod.parse_datasource(
            minimal_twb_bytes,
            "rpt_tableau__test_dashboard (kipptaf_tableau)",
        )
        lod_field = next(f for f in parsed["fields"] if f["name"] == "Student Avg")
        assert lod_field["contains_lod"] is True
        assert lod_field["is_calculated"] is True

    def test_non_lod_field_not_flagged(self, mod, minimal_twb_bytes):
        parsed = mod.parse_datasource(
            minimal_twb_bytes,
            "rpt_tableau__test_dashboard (kipptaf_tableau)",
        )
        att_field = next(f for f in parsed["fields"] if f["name"] == "Attendance Rate")
        assert att_field["contains_lod"] is False

    def test_lod_expressions_collected(self, mod, minimal_twb_bytes):
        parsed = mod.parse_datasource(
            minimal_twb_bytes,
            "rpt_tableau__test_dashboard (kipptaf_tableau)",
        )
        assert len(parsed["lod_expressions"]) == 1
        assert parsed["lod_expressions"][0]["name"] == "Student Avg"


# ── Parameter extraction ───────────────────────────────────────────────────


class TestParameterExtraction:
    def test_parameters_extracted(self, mod, minimal_twb_bytes):
        parsed = mod.parse_datasource(
            minimal_twb_bytes,
            "rpt_tableau__test_dashboard (kipptaf_tableau)",
        )
        assert len(parsed["parameters"]) == 1
        assert parsed["parameters"][0]["name"] == "Selected Term"
        assert parsed["parameters"][0]["datatype"] == "string"

    def test_multi_parameters(self, mod, multi_ds_twb_bytes):
        parsed = mod.parse_datasource(
            multi_ds_twb_bytes,
            "rpt_tableau__grades (kipptaf_tableau)",
        )
        param_names = [p["name"] for p in parsed["parameters"]]
        assert "School Filter" in param_names
        assert "Year" in param_names


# ── Viz usage tracking ─────────────────────────────────────────────────────


class TestVizUsage:
    def test_dimension_usage(self, mod, minimal_twb_bytes):
        parsed = mod.parse_datasource(
            minimal_twb_bytes,
            "rpt_tableau__test_dashboard (kipptaf_tableau)",
        )
        student_field = next(
            f for f in parsed["fields"] if f["name"] == "student_number"
        )
        assert len(student_field["viz_usage"]) >= 1
        roles = {u["role"] for u in student_field["viz_usage"]}
        assert "dimension" in roles

    def test_measure_usage_with_aggregation(self, mod, minimal_twb_bytes):
        parsed = mod.parse_datasource(
            minimal_twb_bytes,
            "rpt_tableau__test_dashboard (kipptaf_tableau)",
        )
        att_field = next(f for f in parsed["fields"] if f["name"] == "Attendance Rate")
        aggs = {u["aggregation"] for u in att_field["viz_usage"]}
        # Should have SUM from Overview and AVG from Detail
        assert "SUM" in aggs
        assert "AVG" in aggs

    def test_viz_usage_includes_worksheet(self, mod, minimal_twb_bytes):
        parsed = mod.parse_datasource(
            minimal_twb_bytes,
            "rpt_tableau__test_dashboard (kipptaf_tableau)",
        )
        att_field = next(f for f in parsed["fields"] if f["name"] == "Attendance Rate")
        worksheets = {u["worksheet"] for u in att_field["viz_usage"]}
        assert "Overview" in worksheets


# ── Integration: full JSON output ──────────────────────────────────────────


class TestIntegration:
    def test_script_produces_valid_json(self):
        result = subprocess.run(
            ["uv", "run", str(SCRIPT_PATH), "--file", str(MINIMAL_TWB)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, f"Script failed: {result.stderr}"
        data = json.loads(result.stdout)

        # Top-level keys
        assert "workbook" in data
        assert "source" in data
        assert "datasources" in data
        assert len(data["datasources"]) == 1

        # Datasource structure
        ds = data["datasources"][0]
        assert "caption" in ds
        assert "fields" in ds
        assert "parameters" in ds
        assert "lod_expressions" in ds

        # Field structure
        for field in ds["fields"]:
            assert "name" in field
            assert "datatype" in field
            assert "formula" in field
            assert "is_calculated" in field
            assert "contains_lod" in field
            assert "viz_usage" in field

    def test_list_sources_mode(self):
        result = subprocess.run(
            [
                "uv",
                "run",
                str(SCRIPT_PATH),
                "--file",
                str(MULTI_DS_TWB),
                "--list-sources",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, f"Script failed: {result.stderr}"
        data = json.loads(result.stdout)
        assert len(data["datasources"]) == 2

    def test_datasource_filter(self):
        result = subprocess.run(
            [
                "uv",
                "run",
                str(SCRIPT_PATH),
                "--file",
                str(MULTI_DS_TWB),
                "-d",
                "grades",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, f"Script failed: {result.stderr}"
        data = json.loads(result.stdout)
        assert len(data["datasources"]) == 1
        assert "grades" in data["datasources"][0]["caption"]

    def test_twbx_integration(self, tmp_path):
        twbx_path = tmp_path / "test.twbx"
        twbx_path.write_bytes(_make_twbx(MINIMAL_TWB))
        result = subprocess.run(
            ["uv", "run", str(SCRIPT_PATH), "--file", str(twbx_path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, f"Script failed: {result.stderr}"
        data = json.loads(result.stdout)
        assert len(data["datasources"]) == 1
