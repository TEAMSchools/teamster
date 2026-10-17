"""Workbook parsing and review copy (ported tests) plus formulas."""

from pathlib import Path

import pytest

# trunk-ignore(pyright/reportAttributeAccessIssue)
from cube_validate import workbook

FIX = Path(__file__).parents[1] / "fixtures" / "cube_validate"
TWB = (FIX / "review.twb").read_text(encoding="utf-8", newline="")


def test_read_workbook_lists_each_dashboards_sheets():
    wb = workbook.read_workbook(TWB)
    assert wb.dashboards == {"Overview": ["Overview - Table", "Overview - Detail"]}


def test_review_copy_exposes_dashboard_sheets_only():
    out = workbook.review_copy(TWB, ["Overview"])
    assert "<window class='worksheet' name='Overview - Table' />" in out
    assert "<window class='worksheet' name='Overview - Detail' />" in out
    assert "hidden='true'" not in out
    # A sheet on no named dashboard keeps its window untouched.
    assert "<window class='worksheet' name='Scratch Sheet' />" in out


def test_review_copy_exposes_only_the_listed_sheets():
    out = workbook.review_copy(TWB, ["Overview"], sheets={"Overview - Detail"})
    assert "<window class='worksheet' name='Overview - Detail' />" in out
    assert "<window class='worksheet' hidden='true' name='Overview - Table' />" in out


def test_review_copy_sets_on_empty_all_and_strips_click_filters():
    out = workbook.review_copy(TWB, ["Overview"])
    assert "<param name='on-empty' value='all' />" in out
    assert "value='none'" not in out
    assert "[Action (" not in out


def test_review_copy_is_valid_xml_and_leaves_the_rest_alone():
    out = workbook.review_copy(TWB, ["Overview"])
    workbook.SafeET.fromstring(out)
    # The saved "No IEP" filter on the table is not a click filter: it stays.
    assert "member='&quot;No IEP&quot;'" in out


def test_review_copy_refuses_a_dashboard_it_cannot_find():
    with pytest.raises(workbook.ReviewCopyError, match="Nope"):
        workbook.review_copy(TWB, ["Nope"])


def test_review_copy_detects_a_sheet_left_hidden(monkeypatch):
    # Break the expose step: the check must catch it, not pass it silently.
    monkeypatch.setattr(workbook, "_expose", lambda text, sheets: text)
    with pytest.raises(workbook.ReviewCopyError, match="still hidden"):
        workbook.review_copy(TWB, ["Overview"])


def test_views_to_hide_keeps_only_the_named_views():
    out = workbook.review_copy(TWB, ["Overview"])
    hide = workbook.views_to_hide(
        out, {"Overview", "Overview - Table", "Overview - Detail"}
    )
    assert hide == ["Scratch Sheet"]


def test_formulas_maps_captions_to_calculations():
    twb = (
        "<workbook><datasources><datasource name='d' caption='D'>"
        "<column name='[Calc_1]' caption='ADA'><calculation class='tableau' "
        "formula='SUM([is_present]) / SUM([membershipvalue])' /></column>"
        "<column name='[region]' /></datasource></datasources></workbook>"
    )
    assert workbook.formulas(twb) == {
        "ADA": "SUM([is_present]) / SUM([membershipvalue])"
    }


def test_review_copy_strips_click_filters_from_a_sheet_with_an_escaped_name():
    twb = TWB.replace("Overview - Detail", "Absences &amp; Tardies")
    out = workbook.review_copy(twb, ["Overview"])
    assert "[Action (" not in out


def test_strip_click_filters_refuses_a_sheet_it_cannot_find():
    with pytest.raises(workbook.ReviewCopyError, match="Nope"):
        workbook._strip_click_filters(TWB, "Nope")


SHEET_FORMATS = """<?xml version='1.0' encoding='utf-8' ?>
<workbook><worksheets>
<worksheet name='ADA'><table><view><datasource-dependencies datasource='ds'>
<column caption='Metric' datatype='real' default-format='p0%' name='[Calc_1]' role='measure' type='quantitative' />
<column caption='Count' datatype='integer' default-format='n#,##0' name='[Calc_2]' role='measure' type='quantitative' />
<column caption='School' datatype='string' name='[school]' role='dimension' type='nominal' />
</datasource-dependencies></view>
<style><style-rule element='cell'>
<format attr='text-format' field='[ds].[avg:Calc_1:qk]' value='p0.0%' />
</style-rule></style></table></worksheet>
</worksheets></workbook>"""


def test_display_formats_prefer_the_sheet_over_the_column_default():
    got = workbook.display_formats(SHEET_FORMATS)
    assert got == {("ADA", "Metric"): "p0.0%", ("ADA", "Count"): "n#,##0"}


def test_review_copy_strips_measure_formats_so_exports_carry_full_precision():
    twb = TWB.replace(
        "<column caption='Pct Done' datatype='real' name='[Calculation_8]'",
        "<column caption='Pct Done' datatype='real' default-format='p0%' name='[Calculation_8]'",
        1,
    ).replace(
        "<column caption='Group By' datatype='string'",
        "<column caption='Group By' datatype='string' default-format='x'",
        1,
    )
    assert twb.count("default-format=") == 2
    out = workbook.review_copy(twb, ["Overview"])
    # the measure loses its format; a parameter keeps its own
    assert "default-format='p0%'" not in out and "default-format='x'" in out
