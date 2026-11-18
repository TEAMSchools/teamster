import xml.etree.ElementTree as ET
from pathlib import Path

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.find_field import (
    Calc,
    aggregated_fields,
    bins,
    calculated_fields,
    columns_read,
    explain_bins,
    null_mode,
    rank,
    restricts,
    sheet_shape,
    shown_values,
    text_values,
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
        "decide whether the sheet query needs it",
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


def test_a_table_calculation_on_a_shelf_is_not_a_cut():
    twb = TWB.replace(
        "[federated.x].[none:student_number:ok])</rows>",
        "[federated.x].[none:student_number:ok] / [federated.x].[cum:ctd:student_number:qk])</rows>",
    )
    assert sheet_shape(twb, "Roster").rows == ["Region", "Student Number"]


def test_a_level_members_filter_keeps_everything_whatever_its_ui_attribute():
    # Region [Filter] on the periods sheets: every member, no ui-enumeration.
    twb = TWB.replace(
        "<groupfilter function='level-members' level='[none:region:nk]' user:ui-enumeration='all' />",
        "<groupfilter function='level-members' level='[none:region:nk]' />",
    )
    assert "Region: All" in sheet_shape(twb, "Roster").filters


NON_NULL = (
    "<filter class='quantitative' column='[ds].[none:score:qk]' "
    "included-values='non-null'/>"
)


def _one_filter_twb(filter_xml):
    return (
        "<workbook><worksheets><worksheet name='S'><table><view>"
        f"{filter_xml}</view><rows/><cols/></table></worksheet></worksheets></workbook>"
    )


def test_a_non_null_quantitative_filter_restricts():
    assert restricts(ET.fromstring(NON_NULL))
    assert null_mode(ET.fromstring(NON_NULL)) == "non-null"
    assert not restricts(
        ET.fromstring(
            "<filter class='quantitative' column='[ds].[none:score:qk]' "
            "included-values='all'/>"
        )
    )


def test_sheet_shape_says_non_null_values_only():
    shape = sheet_shape(_one_filter_twb(NON_NULL), "S")
    assert shape.filters == ["score: non-null values only (narrows the sheet)"]


def test_text_values_names_a_string_attr_but_not_its_countd():
    twb = (
        "<workbook><worksheets><worksheet name='S'><table><view>"
        "<datasource-dependencies datasource='f'>"
        "<column datatype='string' name='[status]' role='dimension' />"
        "</datasource-dependencies></view>"
        "<rows>([f].[attr:status:nk] + [f].[ctd:status:qk])</rows>"
        "</table></worksheet></worksheets></workbook>"
    )
    assert text_values(twb, "S") == {"status"}


def _filter(column, body, cls="categorical", **attrs):
    extra = "".join(f" {k}='{v}'" for k, v in attrs.items())
    return ET.fromstring(
        f"<filter class='{cls}' column='[ds].[{column}]'{extra}>{body}</filter>"
    )


def test_shown_values_lists_chosen_members_of_an_allowlisted_field():
    union = _filter(
        "none:response_type:nk",
        "<groupfilter function='union'>"
        "<groupfilter function='member' level='[response_type]' member='&quot;Overall&quot;' />"
        "<groupfilter function='member' level='[response_type]' member='&quot;Growth&quot;' />"
        "</groupfilter>",
    )
    assert shown_values(union, "response_type", {}) == "Overall, Growth"
    out = _filter(
        "none:response_type:nk",
        "<groupfilter function='except'>"
        "<groupfilter function='level-members' level='[response_type]' />"
        "<groupfilter function='member' level='[response_type]' member='&quot;Overall&quot;' />"
        "</groupfilter>",
    )
    assert shown_values(out, "response_type", {}) == "all except Overall"


def test_shown_values_gives_a_quantitative_filter_s_bounds_and_mode():
    ranged = _filter(
        "none:is_normed_scope:qk", "<min>1</min><max>1</max>", cls="quantitative"
    )
    assert shown_values(ranged, "is_normed_scope", {}) == "from 1 to 1"
    low = _filter("none:is_normed_scope:qk", "<min>2</min>", cls="quantitative")
    assert shown_values(low, "is_normed_scope", {}) == "from 2"
    high = _filter("none:is_normed_scope:qk", "<max>3</max>", cls="quantitative")
    assert shown_values(high, "is_normed_scope", {}) == "up to 3"
    non_null = _filter(
        "none:is_normed_scope:qk",
        "",
        cls="quantitative",
        **{"included-values": "non-null"},
    )
    assert shown_values(non_null, "is_normed_scope", {}) == "non-null values only"


def test_shown_values_hides_a_field_off_the_allowlist():
    el = _filter(
        "none:student_number:ok",
        "<groupfilter function='member' level='[student_number]' member='999999' />",
    )
    assert shown_values(el, "student_number", {}) is None


def test_a_calc_filter_shows_only_when_every_column_it_reads_is_allowlisted():
    formulas = {
        "Calculation_1": "[module_type] = 'WPP' AND [region] = 'Newark'",
        "Calculation_2": "[student_number] > 0",
        "Calculation_3": "[Calculation_2] AND [region] = 'Newark'",
        "Calculation_4": "[Parameters].[Parameter 1]",
    }

    def calc(name):
        return _filter(
            f"none:{name}:nk",
            f"<groupfilter function='member' level='[{name}]' member='true' />",
        )

    assert shown_values(calc("Calculation_1"), "Calculation_1", formulas) == "true"
    assert shown_values(calc("Calculation_2"), "Calculation_2", formulas) is None
    assert shown_values(calc("Calculation_3"), "Calculation_3", formulas) is None
    assert shown_values(calc("Calculation_4"), "Calculation_4", formulas) is None


def test_columns_read_follows_calcs_and_skips_parameters():
    formulas = {"A": "[B] + [x] + [Parameters].[P]", "B": "[y]"}
    assert columns_read("A", formulas) == ("x", "y")
    assert columns_read("plain", formulas) == ("plain",)


def test_a_pass_through_calc_hides_its_values_even_over_allowlisted_columns():
    formulas = {
        "Calculation_1": "RAWSQL_STR('student_name || %1', [region])",
        "Calculation_2": "script_str('return _arg1', [region])",
        "Calculation_3": "[Calculation_1] = 'x'",
        "Calculation_4": "RAWSQLAGG_REAL('SUM(%1)', [region])",
    }

    def calc(name):
        return _filter(
            f"none:{name}:nk",
            f"<groupfilter function='member' level='[{name}]' member='true' />",
        )

    for name in formulas:
        assert shown_values(calc(name), name, formulas) is None
