"""Tests for scripts/cube_validate.py. No live calls."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_SCRIPT = Path(__file__).parents[2] / "scripts" / "cube_validate.py"
FIX = Path(__file__).parent / "fixtures" / "cube_validate"


def _load():
    spec = importlib.util.spec_from_file_location("cube_validate", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    # Registration before exec_module lets the module's dataclasses resolve.
    sys.modules["cube_validate"] = mod
    spec.loader.exec_module(mod)
    return mod


cv = _load()


# ---------------------------------------------------------------- Task 1: grains
def test_parse_twb_keeps_only_sheets_on_named_dashboards():
    sheets = cv.parse_twb(FIX / "mini.twb", ["Live"])
    assert [s.name for s in sheets] == ["Tardy by School", "Headcount"]


def test_parse_twb_reads_shelves_filters_and_formulas():
    tardy = cv.parse_twb(FIX / "mini.twb", ["Live"])[0]
    assert tardy.dashboards == ["Live"]
    assert tardy.datasource == "rpt_demo (kipptaf_tableau)"
    assert tardy.measures == {"# Tardy": "IIF([att_code] = 'T', 1, 0)"}
    assert tardy.shelf_dims == ["region", "School", "calendardate@month"]
    assert tardy.filter_dims == ["gender"]
    assert tardy.other_filters == ["Region User Filter"]


def test_parse_twb_plain_column_measure_has_empty_formula():
    headcount = cv.parse_twb(FIX / "mini.twb", ["Live"])[1]
    assert headcount.measures == {"student_number": ""}


def test_propose_grains_adds_total_shelf_and_one_filter_at_a_time():
    sheets = cv.parse_twb(FIX / "mini.twb", ["Live"])
    assert cv.propose_grains(sheets, "# Tardy") == [
        [],
        ["region", "School", "calendardate@month"],
        ["region", "School", "calendardate@month", "gender"],
    ]


def test_grains_cli_prints_json(capsys):
    rc = cv.main(
        ["grains", str(FIX / "mini.twb"), "--dashboard", "Live", "--measure", "# Tardy"]
    )
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["measure"] == "# Tardy"
    assert [s["name"] for s in out["sheets"]] == ["Tardy by School"]
    assert out["grains"][0] == []


def test_parse_twb_reads_measures_shown_through_measure_values():
    (counts,) = cv.parse_twb(FIX / "mini.twb", ["Counts"])
    assert counts.measures == {"# Tardy": "IIF([att_code] = 'T', 1, 0)"}
    assert counts.shelf_dims == ["team"]
    assert counts.other_filters == []
