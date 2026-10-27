import pytest

# trunk-ignore(pyright/reportAttributeAccessIssue): conftest.py registers cube_validation
from cube_validation import pipeline

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.config import ColumnPair, Comparison, RowSpec

DS = "[federated.x]"

TWB = f"""<?xml version='1.0' encoding='utf-8' ?>
<workbook xmlns:user='http://www.tableausoftware.com/xml/user'>
  <worksheets>
    <worksheet name='Roster'>
      <table>
        <view>
          <datasource-dependencies datasource='federated.x'>
            <column caption='Region' name='[region]' role='dimension' />
            <column caption='Team' name='[team]' role='dimension' />
            <column caption='Last First' name='[lastfirst]' role='dimension' />
            <column caption='Academic Year' name='[academic_year]' role='dimension' />
            <column caption='Enroll Status' name='[enroll_status]' role='dimension' />
            <column caption='Term' name='[term]' role='dimension' />
            <column caption='Calendar Date' name='[calendardate]' role='dimension' />
            <column caption='School ID' name='[schoolid]' role='dimension' />
            <column caption='My Schools' name='[Calculation_9]' role='dimension'>
              <calculation class='tableau' formula='ISMEMBEROF("x") OR USERNAME() = [email]' />
            </column>
            <column caption='# Tardy' name='[Calculation_1]' role='measure'>
              <calculation class='tableau' formula='SUM([is_tardy])' />
            </column>
          </datasource-dependencies>
          <filter class='categorical' column='{DS}.[:Measure Names]'>
            <groupfilter function='member' level='[:Measure Names]' member='x' />
          </filter>
          <filter class='categorical' column='{DS}.[Regional user filter]' context='true' />
          <filter class='categorical' column='{DS}.[none:Calculation_9:nk]'>
            <groupfilter function='member' level='[none:Calculation_9:nk]' member='true' />
          </filter>
          <filter class='categorical' column='{DS}.[none:academic_year:ok]'>
            <groupfilter function='level-members' level='[none:academic_year:ok]' user:ui-enumeration='all' />
          </filter>
          <filter class='categorical' column='{DS}.[none:enroll_status:ok]'>
            <groupfilter function='member' level='[none:enroll_status:ok]' member='0' user:ui-enumeration='inclusive' />
          </filter>
          <filter class='categorical' column='{DS}.[none:term:nk]'>
            <groupfilter function='level-members' level='[none:term:nk]' user:ui-enumeration='all' />
          </filter>
          <filter class='quantitative' column='{DS}.[none:calendardate:qk]' />
          <filter class='categorical' column='{DS}.[none:team:nk]'>
            <groupfilter function='level-members' level='[none:team:nk]' user:ui-enumeration='all' />
          </filter>
        </view>
        <panes>
          <pane>
            <encodings>
              <lod column='{DS}.[attr:schoolid:qk]' />
              <lod column='{DS}.[:Measure Names]' />
            </encodings>
          </pane>
        </panes>
        <rows>({DS}.[none:lastfirst:nk] / ({DS}.[none:region:nk] / {DS}.[none:team:nk]))</rows>
        <cols>{DS}.[:Measure Names]</cols>
      </table>
    </worksheet>
  </worksheets>
</workbook>
"""


def _comparison(**kw):
    return Comparison(
        id="c",
        measure="count_tardy_days",
        sheet="Roster",
        dims=[ColumnPair(dashboard="region", cube="regions_region_name")],
        filters={
            "Academic Year": ColumnPair(
                dashboard="academic_year", cube="dates_academic_year"
            )
        },
        rows=RowSpec(
            grain=[ColumnPair(dashboard="calendardate", cube="attendance_date")],
            values=[],
        ),
        **kw,
    )


def test_sheet_gaps_name_unmapped_cuts_and_filters():
    gaps = pipeline.sheet_gaps(TWB, _comparison())

    # Region is a mapped dim; ATTR(School ID) is an aggregate, not a cut.
    assert gaps.cuts == ["Last First", "Team"]
    # Team is reported once, as a cut. Academic Year and Calendar Date map to
    # Cube members. Measure Names, the user filter and the ISMEMBEROF field are
    # permissions or layout, not cuts.
    assert gaps.filters == ["Enroll Status", "Term"]
    assert gaps.restricting == ["Enroll Status"]


def test_sheet_gaps_never_copy_filter_values():
    gaps = pipeline.sheet_gaps(TWB, _comparison())
    shown = " ".join(gaps.cuts + gaps.filters + gaps.restricting)
    assert "0" not in shown and "true" not in shown


LONG = [
    {"Region": "Newark", "Team": "A", "Measure Names": "# Tardy", "Measure Values": "3"},
    {"Region": "Newark", "Team": "A", "Measure Names": "# Present", "Measure Values": "90"},
    {"Region": "Newark", "Team": "B", "Measure Names": "# Tardy", "Measure Values": "2"},
    {"Region": "Camden", "Team": "C", "Measure Names": "# Tardy", "Measure Values": ""},
]  # fmt: skip


def test_long_export_keeps_the_named_field():
    rows = pipeline.long_to_wide(LONG, "# Tardy")
    assert rows == [
        {"Region": "Newark", "Team": "A", "# Tardy": "3"},
        {"Region": "Newark", "Team": "B", "# Tardy": "2"},
        {"Region": "Camden", "Team": "C", "# Tardy": ""},
    ]


def test_long_export_without_a_matching_field_lists_the_names():
    with pytest.raises(pipeline.Refusal, match=r"'# Tardies'.*# Present, # Tardy"):
        pipeline.long_to_wide(LONG, "# Tardies")


def test_long_export_needs_sheet_field():
    with pytest.raises(pipeline.Refusal, match=r"sheet_field.*# Present, # Tardy"):
        pipeline.long_to_wide(LONG, None)


def test_wide_export_passes_through():
    wide = [{"Region": "Newark", "Rate": "0.9"}]
    assert pipeline.long_to_wide(wide, "Rate") is wide


def test_sheet_field_names_the_wide_value_column():
    comparison = _comparison(sheet_field="Rate")
    mapping, value = pipeline._export_columns(
        comparison, ["Region", "Rate", "Count"], []
    )
    assert mapping == {"Region": "region"} and value == "Rate"


def test_sheet_field_missing_from_a_wide_export_refuses():
    with pytest.raises(pipeline.Refusal, match=r"sheet_field 'Ratio'.*Rate, Count"):
        pipeline._export_columns(
            _comparison(sheet_field="Ratio"), ["Region", "Rate", "Count"], []
        )


def _cells(split_rows):
    rows = pipeline.long_to_wide(LONG, "# Tardy")
    return pipeline._export_cells(
        _comparison(sheet_field="# Tardy", split_rows=split_rows),
        rows,
        {"Region": "region"},
        "# Tardy",
        [],
        [],
    )


def test_split_rows_sum_adds_rows_sharing_the_mapped_dims():
    cells, totals, summed = _cells("sum")
    assert cells == [
        {"region": "Newark", "value": "5"},
        {"region": "Camden", "value": ""},
    ]
    assert totals == 0 and summed == 1


def test_split_rows_default_leaves_rows_for_the_proof_to_refuse():
    cells, _, summed = _cells("refuse")
    assert [c["region"] for c in cells] == ["Newark", "Newark", "Camden"]
    assert summed == 0


@pytest.mark.parametrize(
    "entry, sql",
    [
        ({"dashboard": "enroll_status", "operator": "equals", "values": [0]}, "enroll_status IN (0)"),
        ({"dashboard": "att_code", "operator": "not_equals", "values": ["TD"]}, "(att_code IS NULL OR NOT CAST(att_code AS STRING) IN ('TD'))"),
        ({"dashboard": "membershipvalue", "operator": "gt", "values": [0]}, "membershipvalue > 0"),
        ({"dashboard": "attendancevalue", "operator": "set"}, "attendancevalue IS NOT NULL"),
    ],
)  # fmt: skip
def test_dashboard_filters_join_every_cut_predicate(entry, sql):
    comparison = _comparison(dashboard_filters=[entry])
    assert pipeline.dashboard_predicate(comparison, {}).endswith(sql)
    # They narrow the dashboard side only, so Cube's filters never see them.
    assert pipeline._cut_cube_filters("v", comparison, {}) == []


def test_sheet_gaps_keep_a_dashboard_only_filter_as_missing():
    entry = {"dashboard": "enroll_status", "operator": "equals", "values": [0]}
    gaps = pipeline.sheet_gaps(TWB, _comparison(dashboard_filters=[entry]))
    assert "Enroll Status" in gaps.filters


SIDE = [
    {"Region": "Newark", "Team": "A", "Membershipvalue": "5", "Measure Names": "# Tardy", "Measure Values": "3"},
    {"Region": "Newark", "Team": "A", "Membershipvalue": "5", "Measure Names": "# Present", "Measure Values": "90"},
    {"Region": "Newark", "Team": "B", "Membershipvalue": "4", "Measure Names": "# Tardy", "Measure Values": "2"},
    {"Region": "Newark", "Team": "B", "Membershipvalue": "4", "Measure Names": "# Present", "Measure Values": "80"},
]  # fmt: skip


def test_long_export_reads_a_column_beside_measure_names_once_per_mark():
    # The column repeats on every Measure Names row of a mark; keeping them all
    # would count it once per field.
    assert pipeline.long_to_wide(SIDE, "Membershipvalue") == [
        {"Region": "Newark", "Team": "A", "Membershipvalue": "5"},
        {"Region": "Newark", "Team": "B", "Membershipvalue": "4"},
    ]


def test_a_column_beside_measure_names_sums_split_rows_once():
    rows = pipeline.long_to_wide(SIDE, "Membershipvalue")
    cells, _, summed = pipeline._export_cells(
        _comparison(sheet_field="Membershipvalue", split_rows="sum"),
        rows,
        {"Region": "region"},
        "Membershipvalue",
        [],
        [],
    )
    assert cells == [{"region": "Newark", "value": "9"}] and summed == 1


def test_unknown_sheet_field_lists_names_and_columns():
    with pytest.raises(pipeline.Refusal, match=r"# Present, # Tardy.*Membershipvalue"):
        pipeline.long_to_wide(SIDE, "Nope")
