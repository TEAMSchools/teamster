"""Cut drafting from the workbook."""

import yaml

# trunk-ignore(pyright/reportAttributeAccessIssue)
from cube_validate import cuts, workbook


def _wb():
    return workbook.Workbook(
        dashboards={"Overview": ["ADA by School", "Trend"]},
        filters=[
            workbook.FilterCard("Overview", "region", "Region", "ds", False, True),
            workbook.FilterCard(
                "Overview",
                "academic_year",
                "Year",
                "ds",
                False,
                False,
                default_values=("2026",),
            ),
        ],
        params=[workbook.Param("Overview", "Metric", ("ADA", "Tardy"), "ADA")],
        actions=[
            workbook.Action(
                "Overview", "Click school", "ADA by School", "filter", "Overview", ()
            )
        ],
    )


def test_draft_cuts_one_per_piece_of_logic():
    got = cuts.draft_cuts(
        _wb(),
        ["Overview"],
        {"Region": ["Camden", "Newark"], "Year": ["2025", "2026"]},
    )
    assert got == [
        {"id": "default"},
        {"id": "filter-region", "filters": {"Region": "Camden"}},
        {"id": "filter-year", "filters": {"Year": "2025"}},
        {"id": "param-metric-tardy", "params": {"Metric": "Tardy"}},
        {
            "id": "click-ada-by-school",
            "click": {"source_sheet": "ADA by School", "mark": "largest"},
        },
    ]


def test_plan_yaml_lists_sheets_columns_and_cuts():
    text = cuts.plan_yaml(
        _wb(), ["Overview"], ["student_number", "region"], {"Region": ["Camden"]}
    )
    d = yaml.safe_load(text)
    assert d["sheets"] == {"ADA by School": {}, "Trend": {}}
    assert d["extract_columns"] == ["student_number", "region"]
    assert d["cuts"][0] == {"id": "default"}


def test_plan_yaml_prints_each_cards_default_values():
    d = yaml.safe_load(cuts.plan_yaml(_wb(), ["Overview"], [], {}))
    assert d["filter_card_defaults"] == {"Region": "(All)", "Year": ["2026"]}
