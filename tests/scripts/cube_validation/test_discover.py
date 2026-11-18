from pathlib import Path

from cube_validation.discover import (
    Calc,
    calculated_fields,
    rank,
    tableau_exposures,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_exposure_luid_path(tmp_path):
    path = tmp_path / "tableau.yml"
    path.write_text(
        """
exposures:
  - name: good
    label: Good Dash
    type: dashboard
    depends_on:
      - ref("rpt_a")
      - ref('rpt_b')
    config:
      meta:
        dagster:
          asset:
            metadata:
              id: luid-1
  - name: no_luid
    label: No Luid
    depends_on:
      - ref("rpt_c")
  - name: no_deps
    label: No Deps
    config:
      meta:
        dagster:
          asset:
            metadata:
              id: luid-3
"""
    )
    found = tableau_exposures(path)
    assert [(e.name, e.label, e.luid, e.models) for e in found] == [
        ("good", "Good Dash", "luid-1", ["rpt_a", "rpt_b"])
    ]
    assert found.skipped == ["no_luid", "no_deps"]


def test_calculated_fields_from_twb():
    calcs = calculated_fields((FIXTURES / "calcs.twb").read_text(encoding="utf-8"))
    by_caption = {c.caption: c for c in calcs}

    assert sorted(by_caption) == ["Attendance Pts", "Attendance Rate", "Parameter 1"]
    assert by_caption["Attendance Pts"].formula == (
        'IF [pts] > 3 THEN "High"\nELSE "Low" END'
    )
    assert by_caption["Attendance Rate"].worksheets == [
        "Points Detail",
        "Rate by School",
    ]
    assert by_caption["Attendance Pts"].worksheets == ["Points Detail"]
    assert by_caption["Parameter 1"].worksheets == []


def test_rank_prefers_formula_on_shared_columns():
    calcs = [
        Calc("Attendance Pts", "IF [pts] > 3 THEN 1 END", ["S1"]),
        Calc("Rate", "SUM([is_present]) / COUNT([membership_value])", ["S2"]),
        Calc("Unrelated", "[foo] + [bar]", []),
    ]
    ranked = rank(
        "attendance_rate",
        "sum(is_present) / nullif(count(membership_value), 0)",
        calcs,
        workbook_luid="w1",
        workbook_label="Dash",
    )
    assert [c.caption for c in ranked] == ["Rate", "Attendance Pts"]
    assert ranked[0].score > ranked[1].score > 0
    assert ranked[0].workbook_luid == "w1"
    assert ranked[0].worksheets == ["S2"]


def test_rank_caps_at_five_and_breaks_ties_by_caption():
    calcs = [Calc(f"Rate {i}", "", []) for i in "gfedcba"]
    ranked = rank("rate", "x", calcs)
    assert [c.caption for c in ranked] == [f"Rate {i}" for i in "abcde"]
