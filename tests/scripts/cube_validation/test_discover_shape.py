from pathlib import Path

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.discover import (
    Calc,
    aggregated_fields,
    bins,
    calculated_fields,
    explain_bins,
    rank,
    sheet_shape,
)

TARDY_FORMULA = 'SUM(IF [Att Code (group)] = "Tardy" THEN 1 ELSE 0 END)'

TWB = (Path(__file__).parent / "fixtures" / "roster.twb").read_text()


def test_bins_list_each_group_and_its_codes():
    assert bins(TWB) == {"Att Code (group)": "Tardy = T, ET; Absent = A"}


def test_explain_bins_appends_the_codes_a_formula_uses():
    assert explain_bins(TARDY_FORMULA, bins(TWB)) == (
        TARDY_FORMULA + "  [Att Code (group): Tardy = T, ET; Absent = A]"
    )
    assert explain_bins("SUM([x])", bins(TWB)) == "SUM([x])"


def test_bins_are_not_listed_as_calculated_fields():
    assert [c.caption for c in calculated_fields(TWB)] == ["# Tardy"]


def test_aggregated_fields_list_raw_aggregations_on_sheets():
    found = {c.caption: c for c in aggregated_fields(TWB)}
    assert sorted(found) == ["COUNTD(Student Number)", "SUM(Membership)"]
    assert found["SUM(Membership)"].formula == "SUM([membershipvalue])"
    assert found["SUM(Membership)"].worksheets == ["Roster"]


def test_sheet_shape_names_shelves_export_and_decimals():
    shape = sheet_shape(TWB, "Roster")
    assert shape.rows == ["Region", "Student Number"]
    assert shape.cols == []
    assert shape.long_export
    assert shape.decimals == {"# Tardy": 0, "SUM(Membership)": 3}


def test_sheet_shape_hides_values_of_a_member_filter_on_a_person():
    shape = sheet_shape(TWB, "Roster")
    assert shape.filters == [
        "Enroll Status: 0 (narrows the sheet)",
        "Region: All",
        "Student Number: chosen values hidden (narrows the sheet); "
        "decide whether the probe needs it",
    ]
    assert "999999" not in " ".join(shape.filters)


def test_rank_boosts_the_dashboard_caption_and_can_return_all():
    calcs = [
        Calc("# Late", "SUM([x])", ["S"]),
        *(Calc(f"Tardy {i}", "", []) for i in range(7)),
    ]
    ranked = rank("count_tardy_days", "sum(is_tardy)", calcs, caption="# late")
    assert ranked[0].caption == "# Late" and ranked[0].score >= 1
    assert len(ranked) == 5
    assert len(rank("count_tardy_days", "sum(is_tardy)", calcs, limit=None)) == 7


def test_sheet_shape_skips_an_empty_number_format():
    twb = TWB.replace(
        "value='n#,##0' />",
        "value='n#,##0' />\n            "
        "<format attr='text-format' field='[federated.x].[none:region:nk]' value='' />",
    )
    assert sheet_shape(twb, "Roster").decimals == {"# Tardy": 0, "SUM(Membership)": 3}
