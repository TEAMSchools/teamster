"""Tests for scripts/cube_validate_snapshot.py. No live calls."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).parents[2] / "scripts" / "cube_validate_snapshot.py"
FIX = Path(__file__).parent / "fixtures" / "cube_validate"


def _load():
    spec = importlib.util.spec_from_file_location("cube_validate_snapshot", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    # Registration before exec_module lets the module's dataclasses resolve.
    sys.modules["cube_validate_snapshot"] = mod
    spec.loader.exec_module(mod)
    return mod


snap = _load()
TWB = (FIX / "review.twb").read_text(encoding="utf-8", newline="")


def test_read_workbook_lists_each_dashboards_sheets():
    wb = snap.read_workbook(TWB)
    assert wb.dashboards == {"Overview": ["Overview - Table", "Overview - Detail"]}


def test_filter_cards_carry_field_caption_and_default():
    wb = snap.read_workbook(TWB)
    cards = {c.field: c for c in wb.filters}
    assert set(cards) == {
        "region",
        "school",
        "grade_level",
        "iep_status",
        "student_name",
        "Calculation_1",
        "academic_year",
    }
    assert cards["school"].caption == "School Name"  # explicit caption wins
    assert cards["grade_level"].caption == "Grade Level"  # Tableau's default
    assert cards["region"].default_all is True
    assert cards["iep_status"].default_all is False  # saved as "No IEP" only
    assert cards["school"].datasource == "rpt_demo (kipptaf_tableau)"


def test_calculated_filter_values_come_from_formula_literals():
    wb = snap.read_workbook(TWB)
    calc = next(c for c in wb.filters if c.field == "Calculation_1")
    assert calc.calculated is True
    assert calc.caption == "Is Tested"
    assert calc.values == ("Yes", "No")


def test_parameters_list_values_and_range_has_none():
    wb = snap.read_workbook(TWB)
    params = {p.caption: p for p in wb.params}
    assert params["Group By"].values == ("School", "Teacher", "Student")
    assert params["Group By"].default == "School"
    assert params["Goal %"].values == ()


def test_actions_are_filter_or_link():
    wb = snap.read_workbook(TWB)
    acts = {a.caption: a for a in wb.actions}
    assert acts["Table to Detail"].kind == "filter"
    assert acts["Table to Detail"].source_sheet == "Overview - Table"
    assert acts["Table to Detail"].target == "Overview"
    assert acts["Table to Detail"].exclude == ("Overview - Table",)
    assert acts["Open Report"].kind == "link"


@pytest.mark.parametrize(
    ("field", "caption"),
    [
        ("grade_level", "Grade Level"),
        ("c_504_status", "C 504 Status"),
        ("Title", "Title"),
    ],
)
def test_default_caption(field, caption):
    assert snap.default_caption(field) == caption


def test_review_copy_exposes_dashboard_sheets_only():
    out = snap.review_copy(TWB, ["Overview"])
    assert "<window class='worksheet' name='Overview - Table' />" in out
    assert "<window class='worksheet' name='Overview - Detail' />" in out
    assert "hidden='true'" not in out
    # A sheet on no named dashboard keeps its window untouched.
    assert "<window class='worksheet' name='Scratch Sheet' />" in out


def test_review_copy_sets_on_empty_all_and_strips_click_filters():
    out = snap.review_copy(TWB, ["Overview"])
    assert "<param name='on-empty' value='all' />" in out
    assert "value='none'" not in out
    assert "[Action (" not in out


def test_review_copy_is_valid_xml_and_leaves_the_rest_alone():
    out = snap.review_copy(TWB, ["Overview"])
    snap.SafeET.fromstring(out)
    # The saved "No IEP" filter on the table is not a click filter: it stays.
    assert "member='&quot;No IEP&quot;'" in out


def test_review_copy_refuses_a_dashboard_it_cannot_find():
    with pytest.raises(snap.ReviewCopyError, match="Nope"):
        snap.review_copy(TWB, ["Nope"])


def test_review_copy_detects_a_sheet_left_hidden(monkeypatch):
    # Break the expose step: the check must catch it, not pass it silently.
    monkeypatch.setattr(snap, "_expose", lambda text, sheets: text)
    with pytest.raises(snap.ReviewCopyError, match="still hidden"):
        snap.review_copy(TWB, ["Overview"])


def test_views_to_hide_keeps_only_the_named_views():
    out = snap.review_copy(TWB, ["Overview"])
    hide = snap.views_to_hide(
        out, {"Overview", "Overview - Table", "Overview - Detail"}
    )
    assert hide == ["Scratch Sheet"]
