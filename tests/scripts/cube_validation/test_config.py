from pathlib import Path

import pytest
import yaml

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.config import (
    ConfigError,
    load_view_config,
    mask_digits,
    write_decision,
    write_proof,
)

EXAMPLE = """\
view: student_attendance_enrollment_daily_view
fact: kipptaf_marts.fct_student_attendance_enrollment_daily
time_dimension: attendance_date
comparisons:
  - id: ada-y1-region
    measure: avg_daily_attendance
    confirmed: true
    workbook: 87c13e78-a912-40a4-95dd-33248fc1cbd3
    sheet: Y1 ADA - Region
    dashboard_view: kipptaf_tableau.rpt_tableau__attendance_dashboard
    probe: avg(is_present)
    decimals: 3
    dims:
      - { dashboard: region, cube: regions_region_name }
    filters:
      Academic Year: { dashboard: academic_year, cube: dates_academic_year }
      Region: { dashboard: region, cube: regions_region_name }
    defaults: { Academic Year: "2026", Region: [Camden, Newark, Paterson] }
    cuts: [{}, { Region: Miami }]
    scope: []
    rows:
      grain:
        - { dashboard: student_number, cube: lea_student_identifier }
        - { dashboard: calendardate, cube: attendance_date }
      values:
        - { dashboard: is_present, cube: attendance_value }
    proof: null
  - id: second
    measure: other
anchors:
  - measure: avg_daily_attendance
    value: 0.912
    source: PowerSchool ADA report
    as_of: 2026-10-15
    date_range: [2026-08-12, 2026-10-15]
    filters: { regions_region_name: Newark }
identities:
  - name: ada-is-attendance-over-membership
    left: avg_daily_attendance
    right: sum_attendance_value / sum_membership_value
decisions:
  - id: example
    comparison: ada-y1-region
    group: { column: grade_level, values: ["9"] }
    call: deliberate
    reason: counted differently
    task: ""
    fingerprints: { cube: abc, dashboard: def }
"""


def _write(tmp_path: Path, text: str, name: str = "v.yml") -> Path:
    path = tmp_path / name
    path.write_text(text)
    return path


def test_loads_example(tmp_path):
    cfg = load_view_config(_write(tmp_path, EXAMPLE))

    assert cfg.view == "student_attendance_enrollment_daily_view"
    assert cfg.email is None
    first = cfg.comparisons[0]
    assert first.dims[0].cube == "regions_region_name"
    assert first.filters["Region"].dashboard == "region"
    assert first.rows is not None and first.rows.grain[1].cube == "attendance_date"
    assert first.defaults["Region"] == ["Camden", "Newark", "Paterson"]
    assert first.proof is None
    assert cfg.anchors[0].value == 0.912
    assert cfg.identities[0].right == "sum_attendance_value / sum_membership_value"
    assert cfg.decisions[0].call == "deliberate"


def test_email_is_optional_but_read_when_present(tmp_path):
    cfg = load_view_config(_write(tmp_path, "email: a@example.org\n" + EXAMPLE))

    assert cfg.email == "a@example.org"


def test_unknown_call_is_refused(tmp_path):
    path = _write(tmp_path, EXAMPLE.replace("call: deliberate", "call: maybe"))

    with pytest.raises(ConfigError, match=r"decisions\[0\]\.call"):
        load_view_config(path)


def test_probe_and_probe_sql_are_exclusive(tmp_path):
    text = EXAMPLE.replace(
        "probe: avg(is_present)", "probe: avg(is_present)\n    probe_sql: select 1"
    )

    with pytest.raises(ConfigError, match=r"comparisons\[0\]"):
        load_view_config(_write(tmp_path, text))


def test_file_under_model_is_refused(tmp_path):
    model_dir = tmp_path / "src" / "cube" / "model"
    model_dir.mkdir(parents=True)

    with pytest.raises(ConfigError, match="src/cube/model"):
        load_view_config(_write(model_dir, EXAMPLE, "x.yml"))


def test_fix_calls_need_a_task(tmp_path):
    path = _write(tmp_path, EXAMPLE.replace("call: deliberate", "call: fix_cube"))

    with pytest.raises(ConfigError, match=r"decisions\[0\]\.task"):
        load_view_config(path)


@pytest.mark.parametrize(
    "task", ["Ask Ms. Smith", "see #12", "http://x.example/1", "#12 and more"]
)
def test_decision_task_must_be_a_link(tmp_path, task):
    text = EXAMPLE.replace("call: deliberate", "call: fix_cube")
    path = _write(tmp_path, text.replace('task: ""', f'task: "{task}"'))

    with pytest.raises(ConfigError, match=r"decisions\[0\]\.task.*https://"):
        load_view_config(path)


@pytest.mark.parametrize("task", ["https://app.asana.com/0/1/2", "#6150"])
def test_decision_task_takes_a_link_or_issue_number(tmp_path, task):
    text = EXAMPLE.replace("call: deliberate", "call: fix_cube")
    path = _write(tmp_path, text.replace('task: ""', f'task: "{task}"'))

    assert load_view_config(path).decisions[0].task == task


@pytest.mark.parametrize(
    "value",
    ["9.50", "true", "no", "010", "12:30", "1_000", "+9", "2026-10-01T12:00:00Z"],
)
def test_decision_value_yaml_would_rewrite_is_refused(tmp_path, value):
    path = _write(tmp_path, EXAMPLE.replace('values: ["9"]', f"values: [{value}]"))

    with pytest.raises(ConfigError, match=r"decisions\[0\]\.group\.values\[0\].*quote"):
        load_view_config(path)


def test_decision_values_keep_ints_and_quoted_text(tmp_path):
    path = _write(tmp_path, EXAMPLE.replace('values: ["9"]', 'values: [9, "9.50"]'))

    assert load_view_config(path).decisions[0].group["values"] == [9, "9.50"]


def test_decision_values_keep_quoted_rewritable_text(tmp_path):
    values = '["9", "010", "12:30", "2026-10-01", 0, -3, null]'
    path = _write(tmp_path, EXAMPLE.replace('values: ["9"]', f"values: {values}"))

    assert load_view_config(path).decisions[0].group["values"] == [
        "9", "010", "12:30", "2026-10-01", 0, -3, None,
    ]  # fmt: skip


SCOPE = (
    "    scope:\n"
    "      - { cube: membership_value, values: [1] }\n"
    "      - { cube: attendance_value, operator: set }\n"
)


def test_scope_reads_equals_by_default_and_set(tmp_path):
    cfg = load_view_config(_write(tmp_path, EXAMPLE.replace("    scope: []\n", SCOPE)))

    assert cfg.comparisons[0].scope == [
        {"cube": "membership_value", "operator": "equals", "values": [1]},
        {"cube": "attendance_value", "operator": "set"},
    ]


@pytest.mark.parametrize(
    ("entry", "key"),
    [
        ("{ cube: x, operator: between, values: [1] }", "operator"),
        ("{ cube: x, operator: set, values: [1] }", "values"),
        ("{ cube: x }", "values"),
        ("{ values: [1] }", "cube"),
    ],
)
def test_scope_entry_is_refused(tmp_path, entry, key):
    text = EXAMPLE.replace("    scope: []\n", f"    scope:\n      - {entry}\n")

    with pytest.raises(ConfigError, match=rf"comparisons\[0\]\.scope\[0\]\.{key}"):
        load_view_config(_write(tmp_path, text))


def test_error_names_the_file(tmp_path):
    path = _write(tmp_path, "view: v\ncomparisons: []\n")

    with pytest.raises(ConfigError, match=r"v\.yml"):
        load_view_config(path)


def test_write_proof_changes_only_that_comparison(tmp_path):
    path = _write(tmp_path, EXAMPLE)
    proof = {"fingerprint": "f00", "cells": 12, "proven_at": "2026-10-27"}

    write_proof(path, "ada-y1-region", proof)

    text = path.read_text()
    assert text == EXAMPLE.replace(
        "    proof: null\n",
        "    proof:\n      fingerprint: f00\n      cells: 12\n"
        "      proven_at: '2026-10-27'\n",
    )
    cfg = load_view_config(path)
    assert cfg.comparisons[0].proof is not None
    assert cfg.comparisons[0].proof.fingerprint == "f00"
    assert cfg.comparisons[1].proof is None


def test_write_proof_adds_missing_key_and_replaces_existing(tmp_path):
    path = _write(tmp_path, EXAMPLE)

    write_proof(path, "second", {"fingerprint": "a", "cells": 1, "proven_at": "x"})
    write_proof(path, "second", {"fingerprint": "b", "cells": 2, "proven_at": "y"})

    cfg = load_view_config(path)
    assert cfg.comparisons[1].proof is not None
    assert cfg.comparisons[1].proof.fingerprint == "b"
    assert cfg.anchors[0].measure == "avg_daily_attendance"


def test_write_proof_unknown_id(tmp_path):
    path = _write(tmp_path, EXAMPLE)

    with pytest.raises(ConfigError, match="nope"):
        write_proof(path, "nope", {})


def test_time_dimension_is_read(tmp_path):
    cfg = load_view_config(_write(tmp_path, EXAMPLE))

    assert cfg.time_dimension == "attendance_date"


def test_anchors_need_a_time_dimension(tmp_path):
    text = EXAMPLE.replace("time_dimension: attendance_date\n", "")

    with pytest.raises(ConfigError, match="time_dimension"):
        load_view_config(_write(tmp_path, text))


def test_rows_need_a_time_dimension(tmp_path):
    text = EXAMPLE.replace("time_dimension: attendance_date\n", "")
    text = text.split("anchors:")[0] + "identities:" + text.split("identities:")[1]

    with pytest.raises(ConfigError, match="time_dimension.*rows"):
        load_view_config(_write(tmp_path, text))


def test_time_dimension_is_optional_without_anchors_or_rows(tmp_path):
    text = EXAMPLE.replace("time_dimension: attendance_date\n", "")
    text = text.split("anchors:")[0] + "identities:" + text.split("identities:")[1]
    head, tail = text.split("    rows:\n", 1)
    text = head + "    proof: null" + tail.split("    proof: null", 1)[1]

    cfg = load_view_config(_write(tmp_path, text))

    assert cfg.time_dimension is None and cfg.anchors == []
    assert cfg.comparisons[0].rows is None


def test_proof_keeps_workbook_updated_at(tmp_path):
    path = _write(tmp_path, EXAMPLE)
    write_proof(
        path,
        "ada-y1-region",
        {
            "fingerprint": "f",
            "cells": 3,
            "proven_at": "2026-10-27T10:00:00+00:00",
            "workbook_updated_at": "2026-10-20T09:00:00+00:00",
            "probe_fingerprint": "p00",
            "cuts": ["{}", '{"Region": "Miami"}'],
        },
    )

    proof = load_view_config(path).comparisons[0].proof

    assert proof is not None
    assert proof.workbook_updated_at == "2026-10-20T09:00:00+00:00"
    assert proof.probe_fingerprint == "p00"
    assert proof.cuts == ["{}", '{"Region": "Miami"}']


def test_proof_keeps_totals_skipped(tmp_path):
    path = _write(tmp_path, EXAMPLE)
    write_proof(
        path,
        "ada-y1-region",
        {"fingerprint": "f", "cells": 1, "proven_at": "x", "totals_skipped": 2},
    )

    proof = load_view_config(path).comparisons[0].proof

    assert proof is not None and proof.totals_skipped == 2


def test_negative_totals_skipped_is_refused(tmp_path):
    path = _write(tmp_path, EXAMPLE)
    write_proof(
        path,
        "ada-y1-region",
        {"fingerprint": "f", "cells": 1, "proven_at": "x", "totals_skipped": -1},
    )

    with pytest.raises(ConfigError, match=r"proof\.totals_skipped"):
        load_view_config(path)


def test_proof_without_cuts_reads_as_unknown(tmp_path):
    path = _write(tmp_path, EXAMPLE)
    write_proof(
        path, "ada-y1-region", {"fingerprint": "f", "cells": 1, "proven_at": "x"}
    )

    proof = load_view_config(path).comparisons[0].proof

    assert proof is not None and proof.cuts is None
    assert proof.totals_skipped is None


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("fact: kipptaf_marts.fct_student_attendance_enrollment_daily", "fact: a.b.c"),
        (
            "fact: kipptaf_marts.fct_student_attendance_enrollment_daily",
            "fact: 'a;b.c'",
        ),
        ("time_dimension: attendance_date", "time_dimension: 'x) --'"),
        ("view: student_attendance_enrollment_daily_view", "view: 'v`; DROP'"),
        (
            "measure: avg_daily_attendance\n    confirmed",
            "measure: 'a b'\n    confirmed",
        ),
        (
            "dashboard_view: kipptaf_tableau.rpt_tableau__attendance_dashboard",
            "dashboard_view: 'x.y`; DROP TABLE t; --'",
        ),
        (
            "dashboard: region, cube: regions_region_name }\n    filters",
            "dashboard: 'r, 1', cube: x }\n    filters",
        ),
        ("dashboard: student_number", "dashboard: 'a b'"),
        ("cube: attendance_value", "cube: 'a-b'"),
        ("dashboard: academic_year", "dashboard: \"x' OR '1\""),
        ("cube: dates_academic_year", "cube: 'd.y'"),
    ],
)
def test_sql_identifier_that_is_not_plain_is_refused(tmp_path, old, new):
    assert old in EXAMPLE
    with pytest.raises(ConfigError):
        load_view_config(_write(tmp_path, EXAMPLE.replace(old, new, 1)))


def test_scope_cube_that_is_not_plain_is_refused(tmp_path):
    text = EXAMPLE.replace("scope: []", "scope: [{ cube: 'x; y', values: [a] }]", 1)
    with pytest.raises(ConfigError, match="plain identifier"):
        load_view_config(_write(tmp_path, text))


# --- sheet shape and missing cuts ---------------------------------------------

SHAPE = "    probe: avg(is_present)\n"
GAP_DECISION = """\
  - id: no-team
    missing_cut: Team
    call: deliberate
    reason: Team is a homeroom label
"""


def test_sheet_field_and_split_rows_load(tmp_path):
    text = EXAMPLE.replace(
        SHAPE, SHAPE + '    sheet_field: "# Tardy"\n    split_rows: sum\n'
    )
    first = load_view_config(_write(tmp_path, text)).comparisons[0]
    assert first.sheet_field == "# Tardy" and first.split_rows == "sum"


def test_split_rows_defaults_to_refuse(tmp_path):
    first = load_view_config(_write(tmp_path, EXAMPLE)).comparisons[0]
    assert first.sheet_field is None and first.split_rows == "refuse"


def test_split_rows_takes_only_known_modes(tmp_path):
    text = EXAMPLE.replace(SHAPE, SHAPE + "    split_rows: average\n")
    with pytest.raises(ConfigError, match=r"split_rows.*refuse, sum"):
        load_view_config(_write(tmp_path, text))


def test_proof_reads_missing_cuts_and_filters(tmp_path):
    proof = """\
    proof:
      fingerprint: f
      cells: 3
      proven_at: '2026-10-27T00:00:00+00:00'
      missing_cuts: [Team]
      missing_filters: [Enroll Status, Term]
      restricting_filters: [Enroll Status]
      filter_notes:
        Grade Copy: copy of Grade
      missing_columns:
        Enroll Status: enroll_status
"""
    text = EXAMPLE.replace("    proof: null\n", proof)
    p = load_view_config(_write(tmp_path, text)).comparisons[0].proof
    assert p.filter_notes == {"Grade Copy": "copy of Grade"}
    assert p.missing_columns == {"Enroll Status": "enroll_status"}
    assert p.missing_cuts == ["Team"]
    assert p.missing_filters == ["Enroll Status", "Term"]
    assert p.restricting_filters == ["Enroll Status"]


def test_old_proof_reads_missing_lists_as_unknown(tmp_path):
    text = EXAMPLE.replace(
        "    proof: null\n", "    proof:\n      fingerprint: f\n      cells: 1\n"
    )
    p = load_view_config(_write(tmp_path, text)).comparisons[0].proof
    assert p.missing_cuts is None and p.missing_filters is None
    assert p.filter_notes is None and p.missing_columns is None


def test_gap_decision_loads_without_comparison_or_fingerprints(tmp_path):
    cfg = load_view_config(_write(tmp_path, EXAMPLE + GAP_DECISION))
    d = cfg.decisions[1]
    assert (d.missing_cut, d.missing_filter, d.comparison) == ("Team", "", "")


@pytest.mark.parametrize(
    "extra, match",
    [
        ("    missing_filter: Term\n", "only one of group, missing_cut"),
        ("    group: { column: region, values: [x] }\n", "only one of group"),
        ("    comparison: ada-y1-region\n", "belongs to the view"),
    ],
)
def test_gap_decision_shape_is_checked(tmp_path, extra, match):
    with pytest.raises(ConfigError, match=match):
        load_view_config(_write(tmp_path, EXAMPLE + GAP_DECISION + extra))


def test_group_decision_still_needs_comparison(tmp_path):
    text = EXAMPLE.replace("    comparison: ada-y1-region\n    group:", "    group:")
    with pytest.raises(ConfigError, match=r"decisions\[0\]\.comparison"):
        load_view_config(_write(tmp_path, text))


# --- scope operators and dashboard-only filters --------------------------------

SCOPE_LINE = "    scope: []\n"


@pytest.mark.parametrize(
    "entry",
    [
        "{ cube: membership_value, operator: gt, values: [0] }",
        "{ cube: membership_value, operator: lte, values: [1.5] }",
        "{ cube: attendance_code, operator: not_equals, values: [TD, SHI] }",
    ],
)
def test_scope_takes_comparison_operators(tmp_path, entry):
    text = EXAMPLE.replace(SCOPE_LINE, f"    scope:\n      - {entry}\n")
    assert load_view_config(_write(tmp_path, text)).comparisons[0].scope


@pytest.mark.parametrize(
    "entry, match",
    [
        ("{ cube: m, operator: gt, values: [0, 1] }", "exactly 1 number"),
        ("{ cube: m, operator: gt, values: [a] }", "exactly 1 number"),
        ("{ cube: m, operator: between, values: [0] }", "equals, not_equals, gt"),
    ],
)
def test_scope_operator_values_are_checked(tmp_path, entry, match):
    text = EXAMPLE.replace(SCOPE_LINE, f"    scope:\n      - {entry}\n")
    with pytest.raises(ConfigError, match=match):
        load_view_config(_write(tmp_path, text))


def test_dashboard_filters_load(tmp_path):
    text = EXAMPLE.replace(
        SCOPE_LINE,
        SCOPE_LINE
        + "    dashboard_filters:\n      - { dashboard: enroll_status, values: [0] }\n",
    )
    first = load_view_config(_write(tmp_path, text)).comparisons[0]
    assert first.dashboard_filters == [
        {"dashboard": "enroll_status", "operator": "equals", "values": [0]}
    ]


def test_dashboard_filters_refuse_sql_in_the_column(tmp_path):
    text = EXAMPLE.replace(
        SCOPE_LINE,
        SCOPE_LINE
        + '    dashboard_filters:\n      - { dashboard: "x OR 1=1", values: [0] }\n',
    )
    with pytest.raises(ConfigError, match=r"dashboard_filters\[0\]\.dashboard"):
        load_view_config(_write(tmp_path, text))


def _dashboard_filter(tmp_path, entry):
    text = EXAMPLE.replace(
        SCOPE_LINE, SCOPE_LINE + f"    dashboard_filters:\n      - {entry}\n"
    )
    return load_view_config(_write(tmp_path, text)).comparisons[0]


def test_dashboard_filter_loads_a_week_end_date(tmp_path):
    first = _dashboard_filter(
        tmp_path, "{ dashboard: administered_at, operator: lte, days_from_week_end: 0 }"
    )
    assert first.dashboard_filters == [
        {"dashboard": "administered_at", "operator": "lte", "days_from_week_end": 0}
    ]


@pytest.mark.parametrize(
    "entry, match",
    [
        ("{ dashboard: d, operator: lte, days_from_week_end: '0' }", "must be int"),
        ("{ dashboard: d, operator: lte, days_from_week_end: true }", "must be int"),
        ("{ dashboard: d, operator: lte, days_from_week_end: 1.5 }", "must be int"),
        ("{ dashboard: d, days_from_week_end: 0 }", "takes gt, gte, lt, lte; got 'equals'"),
        ("{ dashboard: d, operator: set, days_from_week_end: 0 }", "got 'set'"),
        ("{ dashboard: d, operator: lt, values: [1], days_from_week_end: 0 }", r"\.values: must be absent"),
    ],
)  # fmt: skip
def test_dashboard_filter_week_end_is_checked(tmp_path, entry, match):
    with pytest.raises(ConfigError, match=match):
        _dashboard_filter(tmp_path, entry)


def test_scope_refuses_a_week_end_date(tmp_path):
    text = EXAMPLE.replace(
        SCOPE_LINE,
        "    scope:\n      - { cube: d, operator: lte, days_from_week_end: 0 }\n",
    )
    with pytest.raises(ConfigError, match="applies to dashboard_filters only"):
        load_view_config(_write(tmp_path, text))


# --- shared comparison blocks --------------------------------------------------

SHARED = """\
view: v
fact: kipptaf_marts.fct_f
time_dimension: attendance_date
shared:
  roster: &roster
    confirmed: true
    workbook: wb-1
    sheet: Roster
    dashboard_view: kipptaf_tableau.rpt_d
    decimals: 0
    split_rows: sum
    dims:
      - { dashboard: student_number, cube: lea_student_identifier }
    filters:
      Academic Year: { dashboard: academic_year, cube: dates_academic_year }
    defaults: { Academic Year: "2026" }
    cuts: [{}]
comparisons:
  - id: tardy
    <<: *roster
    measure: count_tardy_days
    sheet_field: "# Tardy"
    probe: sum(is_tardy)
    proof: null
  - id: absent
    <<: *roster
    measure: count_absent_days
    sheet_field: "# Absences"
    probe: sum(is_absent)
"""


def test_shared_blocks_load_like_repeated_keys(tmp_path):
    cfg = load_view_config(_write(tmp_path, SHARED))
    tardy, absent = cfg.comparisons
    assert (tardy.sheet, absent.sheet) == ("Roster", "Roster")
    assert tardy.split_rows == absent.split_rows == "sum"
    assert tardy.sheet_field == "# Tardy" and absent.sheet_field == "# Absences"
    assert tardy.dims == absent.dims


def test_write_proof_keeps_the_shared_block(tmp_path):
    path = _write(tmp_path, SHARED)
    write_proof(path, "absent", {"fingerprint": "f", "cells": 3})
    text = path.read_text()
    assert "roster: &roster" in text and text.count("<<: *roster") == 2
    cfg = load_view_config(path)
    assert cfg.comparisons[1].proof.cells == 3
    assert cfg.comparisons[0].proof is None


def test_shared_must_be_a_mapping(tmp_path):
    text = SHARED.replace(
        "shared:\n  roster: &roster\n", "shared: [x]\nignored: &roster\n"
    )
    with pytest.raises(ConfigError, match="shared"):
        load_view_config(_write(tmp_path, text))


DEFINITIONS = (
    "    definitions:\n"
    '      dashboard: "Tardy code group: ET, T, T10, TLE"\n'
    "      cube: \"att_code LIKE 'T%'\"\n"
)


def test_definitions_load(tmp_path):
    text = EXAMPLE.replace(SCOPE_LINE, SCOPE_LINE + DEFINITIONS)
    first = load_view_config(_write(tmp_path, text)).comparisons[0]
    assert first.definitions == {
        "dashboard": "Tardy code group: ET, T, T10, TLE",
        "cube": "att_code LIKE 'T%'",
    }


def test_definitions_need_both_sides(tmp_path):
    one = "    definitions:\n      dashboard: x\n"
    text = EXAMPLE.replace(SCOPE_LINE, SCOPE_LINE + one)
    with pytest.raises(ConfigError, match=r"definitions\.cube"):
        load_view_config(_write(tmp_path, text))


def test_domain_owner_task_can_wait_for_the_review_issue(tmp_path):
    text = EXAMPLE.replace("call: deliberate", "call: domain_owner")
    assert load_view_config(_write(tmp_path, text)).decisions[0].task == ""


CELLS_DECISION = """\
  - id: tardy-cells
    comparison: ada-y1-region
    cells: true
    call: domain_owner
    reason: the owner picks the tardy codes
    fingerprints: { cube: abc, dashboard: def }
"""


def test_cells_decision_loads(tmp_path):
    d = load_view_config(_write(tmp_path, EXAMPLE + CELLS_DECISION)).decisions[1]
    assert d.cells is True and d.comparison == "ada-y1-region" and d.group == {}


def test_cells_decision_takes_no_group(tmp_path):
    text = EXAMPLE + CELLS_DECISION + "    group: { column: region, values: [x] }\n"
    with pytest.raises(ConfigError, match="only one of group"):
        load_view_config(_write(tmp_path, text))


def test_parameters_load_as_text(tmp_path):
    text = EXAMPLE.replace(
        SCOPE_LINE,
        SCOPE_LINE + "    parameters: { Attendance Metric: Chronic Absenteeism }\n",
    )
    first = load_view_config(_write(tmp_path, text)).comparisons[0]
    assert first.parameters == {"Attendance Metric": "Chronic Absenteeism"}


def _shelves(tmp_path, shelves):
    text = EXAMPLE.replace(SCOPE_LINE, SCOPE_LINE + f"    shelves: {shelves}\n")
    return load_view_config(_write(tmp_path, text)).comparisons[0]


def test_shelves_load_when_each_added_field_maps_to_a_dim(tmp_path):
    # `Region` maps by its filters caption, `region` by the dim's own name.
    first = _shelves(
        tmp_path,
        "{ drop: [Week Start Monday], add: { rows: [Region], cols: [region] } }",
    )
    assert first.shelves == {
        "drop": ["Week Start Monday"],
        "add": {"rows": ["Region"], "cols": ["region"]},
    }


def test_shelves_load_a_cleared_filter_alone(tmp_path):
    first = _shelves(tmp_path, "{ clear_filters: [Discipline] }")
    assert first.shelves == {"clear_filters": ["Discipline"]}


@pytest.mark.parametrize(
    "shelves, message",
    [
        (
            "{ add: { rows: [Grade Level] } }",
            r"shelves\.add: 'Grade Level' maps to no dim",
        ),
        ("{ add: { rows: [Academic Year] } }", "'Academic Year' maps to no dim"),
        ("{ add: { pages: [Region] } }", r"shelves\.add: takes rows and cols"),
        ("{ drop: Week }", r"shelves\.drop: must be list"),
        ("{ drop: [2026] }", r"shelves\.drop: captions must be text"),
        ("{ clear_filters: Discipline }", r"shelves\.clear_filters: must be list"),
        ("{ keep: [Region] }", "shelves: takes drop, add and clear_filters"),
        ("{}", "shelves: set drop, add or clear_filters"),
    ],
)
def test_shelves_refuse_an_unmapped_add_and_a_bad_shape(tmp_path, shelves, message):
    with pytest.raises(ConfigError, match=message):
        _shelves(tmp_path, shelves)


def test_fix_source_needs_a_task(tmp_path):
    path = _write(tmp_path, EXAMPLE.replace("call: deliberate", "call: fix_source"))

    with pytest.raises(ConfigError, match=r"decisions\[0\]\.task"):
        load_view_config(path)


def test_fix_source_takes_a_task(tmp_path):
    text = EXAMPLE.replace("call: deliberate", "call: fix_source")
    path = _write(tmp_path, text.replace('task: ""', 'task: "#6150"'))

    assert load_view_config(path).decisions[0].call == "fix_source"


def test_tasks_block_is_read(tmp_path):
    text = EXAMPLE + (
        "tasks:\n  cube_fix: '#6150'\n  dashboard_fix: https://app.asana.com/0/1/2\n"
    )

    cfg = load_view_config(_write(tmp_path, text))

    assert cfg.tasks == {
        "cube_fix": "#6150",
        "dashboard_fix": "https://app.asana.com/0/1/2",
    }


def test_tasks_block_is_optional(tmp_path):
    assert load_view_config(_write(tmp_path, EXAMPLE)).tasks == {}


def test_tasks_block_accepts_only_known_keys(tmp_path):
    path = _write(tmp_path, EXAMPLE + "tasks:\n  other_fix: '#6150'\n")

    with pytest.raises(ConfigError, match=r"tasks\.other_fix"):
        load_view_config(path)


def test_tasks_block_values_must_be_links(tmp_path):
    path = _write(tmp_path, EXAMPLE + "tasks:\n  cube_fix: see Asana\n")

    with pytest.raises(ConfigError, match=r"tasks\.cube_fix.*https://"):
        load_view_config(path)


def test_write_decision_replaces_by_id_and_keeps_comments(tmp_path):
    text = EXAMPLE.replace("decisions:\n", "# why each call was made\ndecisions:\n")
    path = _write(tmp_path, text + "# tasks follow\n")

    write_decision(
        path,
        {
            "id": "example",
            "comparison": "ada-y1-region",
            "group": {"column": "grade_level", "values": ["9.50", "010", "no"]},
            "call": "fix_cube",
            "reason": "Cube: drops grade 9",
            "task": "#6150",
            "fingerprints": {"cube": "abc", "dashboard": "def"},
        },
    )

    after = path.read_text()
    assert "# why each call was made\ndecisions:\n" in after
    assert after.endswith("# tasks follow\n")
    assert after.split("decisions:", 1)[0] == text.split("decisions:", 1)[0]
    (d,) = load_view_config(path).decisions
    assert (d.id, d.call, d.task, d.reason) == (
        "example",
        "fix_cube",
        "#6150",
        "Cube: drops grade 9",
    )
    # Values YAML would rewrite are written quoted, so they load as text.
    assert d.group == {"column": "grade_level", "values": ["9.50", "010", "no"]}


def test_write_decision_appends_a_new_id(tmp_path):
    path = _write(tmp_path, EXAMPLE)
    new = {"id": "no-team", "missing_cut": "Team", "call": "deliberate",
           "reason": "homeroom label only"}  # fmt: skip

    write_decision(path, new)

    first, second = load_view_config(path).decisions
    assert first.id == "example" and first.reason == "counted differently"
    assert (second.id, second.missing_cut) == ("no-team", "Team")


def test_write_decision_starts_a_decisions_block(tmp_path):
    path = _write(tmp_path, EXAMPLE.split("decisions:")[0])

    write_decision(
        path, {"id": "a", "missing_filter": "Team", "call": "deliberate", "reason": "r"}
    )

    (d,) = load_view_config(path).decisions
    assert (d.id, d.missing_filter) == ("a", "Team")


def test_write_decision_restores_file_when_result_does_not_load(tmp_path):
    path = _write(tmp_path, EXAMPLE)
    bad = {"id": "example", "comparison": "ada-y1-region", "call": "fix_cube",
           "reason": "r", "fingerprints": {"cube": "abc", "dashboard": "def"}}  # fmt: skip

    with pytest.raises(ConfigError, match=r"decisions\[0\]\.task"):
        write_decision(path, bad)

    assert path.read_text() == EXAMPLE


def test_write_decision_refuses_an_id_it_cannot_find_by_its_line(tmp_path):
    # `id` is not the item's first key, so a line edit could not replace it.
    text = EXAMPLE.replace(
        "  - id: example\n    comparison: ada-y1-region\n",
        "  - comparison: ada-y1-region\n    id: example\n",
    )
    path = _write(tmp_path, text)

    with pytest.raises(ConfigError, match="example"):
        write_decision(
            path,
            {"id": "example", "missing_cut": "T", "call": "deliberate", "reason": "r"},
        )

    assert path.read_text() == text


def test_write_decision_replaces_an_item_with_a_column_0_comment_inside(tmp_path):
    text = EXAMPLE.replace(
        "    reason: counted differently\n",
        "# the owner asked about this\n    reason: counted differently\n",
    )
    path = _write(tmp_path, text)

    write_decision(
        path,
        {
            "id": "example",
            "comparison": "ada-y1-region",
            "group": {"column": "grade_level", "values": ["9"]},
            "call": "fix_cube",
            "reason": "Owner: Cube is wrong",
            "task": "#6150",
            "fingerprints": {"cube": "abc", "dashboard": "def"},
        },  # fmt: skip
    )

    (d,) = load_view_config(path).decisions
    assert (d.call, d.reason, d.task) == ("fix_cube", "Owner: Cube is wrong", "#6150")
    assert "counted differently" not in path.read_text()


def test_write_decision_restores_when_the_file_does_not_hold_what_was_asked(
    tmp_path, monkeypatch
):
    path = _write(tmp_path, EXAMPLE)
    asked = {"id": "example", "comparison": "ada-y1-region",
             "group": {"column": "grade_level", "values": ["9"]},
             "call": "deliberate", "reason": "asked",
             "fingerprints": {"cube": "abc", "dashboard": "def"}}  # fmt: skip
    real_dump = yaml.safe_dump
    monkeypatch.setattr(
        yaml,
        "safe_dump",
        lambda data, **kw: real_dump([{**data[0], "reason": "other"}], **kw),
    )

    with pytest.raises(ConfigError, match="reason"):
        write_decision(path, asked)

    assert path.read_text() == EXAMPLE


@pytest.mark.parametrize(
    "line",
    [
        "decisions: [{id: example, missing_cut: T, call: deliberate, reason: r}]",
        "decisions: null",
        "decisions: ~",
    ],
)
def test_write_decision_refuses_a_decisions_key_it_cannot_extend(tmp_path, line):
    text = EXAMPLE.split("decisions:")[0] + line + "\n"
    path = _write(tmp_path, text)

    with pytest.raises(ConfigError, match="decisions"):
        write_decision(
            path, {"id": "a", "missing_cut": "U", "call": "deliberate", "reason": "r"}
        )

    assert path.read_text() == text


# --- cause decisions (T17) ---------------------------------------------------

CAUSE_DECISION = """\
  - id: no-section
    comparison: ada-y1-region
    cause:
      side: cube
      label: score has no section on the anchor date
    call: domain_owner
    reason: the owner says whether a score with no section counts
    fingerprints: { cube: abc, dashboard: def, proof: "0f0f" }
"""


def test_cause_decision_loads(tmp_path):
    d = load_view_config(_write(tmp_path, EXAMPLE + CAUSE_DECISION)).decisions[1]

    assert (d.comparison, d.group, d.cells, d.answer) == (
        "ada-y1-region",
        {},
        False,
        "",
    )
    assert d.cause == {
        "side": "cube",
        "label": "score has no section on the anchor date",
    }
    assert d.fingerprints["proof"] == "0f0f"


LABEL_LINE = "      label: score has no section on the anchor date\n"


@pytest.mark.parametrize(
    "old, new, match",
    [
        ("side: cube", "side: both", r"cause\.side.*dashboard, cube"),
        (LABEL_LINE, "      label: ''\n", r"cause\.label.*words"),
        (LABEL_LINE, "      label: term 20250701\n", r"cause\.label.*5 or more.*<n>"),
        (LABEL_LINE, "      label: call 973-555-1234\n", r"cause\.label.*5 or more.*<n>"),
        (LABEL_LINE, LABEL_LINE + "      groups: [a]\n", r"cause\.groups.*side and label"),
        ("comparison: ada-y1-region\n    cause", "cause", r"comparison"),
        ("    call: domain_owner\n", "    call: domain_owner\n    answer: maybe\n",
         r"answer.*one of"),
    ],
)  # fmt: skip
def test_cause_decision_shape_is_checked(tmp_path, old, new, match):
    text = EXAMPLE + CAUSE_DECISION.replace(old, new)

    with pytest.raises(ConfigError, match=match):
        load_view_config(_write(tmp_path, text))


def test_only_a_cause_decision_takes_an_answer(tmp_path):
    text = EXAMPLE.replace('    task: ""\n', '    task: ""\n    answer: fix_cube\n')

    with pytest.raises(ConfigError, match=r"answer.*cause decision"):
        load_view_config(_write(tmp_path, text))


def test_cause_decision_takes_no_group(tmp_path):
    text = EXAMPLE + CAUSE_DECISION + "    group: { column: region, values: [x] }\n"

    with pytest.raises(ConfigError, match="only one of group.*cause"):
        load_view_config(_write(tmp_path, text))


def test_write_decision_round_trips_a_cause_decision(tmp_path):
    path = _write(tmp_path, EXAMPLE)
    decision = {
        "id": "no-section",
        "comparison": "ada-y1-region",
        "cause": {"side": "cube", "label": "term <n> has no section"},
        "call": "fix_cube",
        "reason": "r",
        "task": "#1",
        "answer": "fix_cube",
        "fingerprints": {"cube": "abc", "dashboard": "def", "proof": "0f"},
    }

    write_decision(path, decision)

    d = load_view_config(path).decisions[1]
    assert (d.cause, d.answer) == (decision["cause"], "fix_cube")
    assert d.fingerprints == decision["fingerprints"]


@pytest.mark.parametrize(
    "text, want",
    [
        ("term 20250701", "term <n>"),
        ("call 973-555-1234 or 1,234,567", "call <n> or <n>"),
        ("id 12.345", "id <n>"),
        # Not ID-shaped: school years, a date, small numbers apart.
        ("since 2024-25 and 2025-2026", "since 2024-25 and 2025-2026"),
        ("after 2025-07-01", "after 2025-07-01"),
        ("grades 9 10 11 12", "grades 9 10 11 12"),
        ("grades 9, 10, 11 since 2024", "grades 9, 10, 11 since 2024"),
        ("1234 5678", "1234 5678"),
    ],
)
def test_mask_digits_masks_only_id_shaped_numbers(text, want):
    assert mask_digits(text) == want
