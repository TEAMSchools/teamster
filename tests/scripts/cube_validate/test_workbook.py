"""Workbook parsing and review copy (ported tests) plus formulas."""

from pathlib import Path

import pytest

# trunk-ignore(pyright/reportAttributeAccessIssue)
from cube_validate import workbook

FIX = Path(__file__).parents[1] / "fixtures" / "cube_validate"
TWB = (FIX / "review.twb").read_text(encoding="utf-8", newline="")
DS = "rpt_demo (kipptaf_tableau)"


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


def test_read_workbook_reads_each_sheets_saved_filters():
    sf = {
        f.caption: f
        for f in workbook.read_workbook(TWB).sheet_filters["Overview - Table"]
    }
    assert set(sf) == {
        "iep_status",
        "Subject Group",
        "response_type",
        "standard_code",
        "score",
        "Pct Done",
    }
    assert sf["iep_status"].op == "in" and sf["iep_status"].values == ("No IEP",)
    # A group becomes its underlying column and the bin's members.
    assert (sf["Subject Group"].field, sf["Subject Group"].values) == (
        "subject",
        ("English", "Writing"),
    )
    assert sf["response_type"].values == ("O", "overall")
    assert sf["standard_code"].op == "not_in" and sf["standard_code"].values == (
        "Overall",
    )
    assert (sf["score"].op, sf["score"].low, sf["score"].high, sf["score"].numeric) == (
        "range",
        "0.75",
        None,
        True,
    )
    # A calculation the extract has no column for is flagged; one that only reads a
    # parameter (a sheet swap) is left out.
    assert sf["Pct Done"].calculated is True
    assert "View Switch" not in sf


def test_read_workbook_lists_groups_with_their_bins():
    g = workbook.read_workbook(TWB).groups["Subject Group"]
    assert g == {
        "datasource": DS,
        "field": "subject",
        "bins": {"Literacy": ["English", "Writing"]},
        "other": "Other",
    }


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
