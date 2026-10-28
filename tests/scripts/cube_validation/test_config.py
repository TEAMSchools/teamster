from pathlib import Path

import pytest

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.config import ConfigError, load_view_config, write_proof

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
