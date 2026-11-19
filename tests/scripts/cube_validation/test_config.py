import dataclasses
from pathlib import Path

import pytest
import yaml

# trunk-ignore(pyright/reportAttributeAccessIssue): conftest.py registers cube_validation
from cube_validation import decisions, latest, pipeline

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.config import (
    ConfigError,
    comparison_item,
    find_comparison,
    load_view_config,
    mask_digits,
    with_fact_dataset,
    write_decision,
    write_rebuild_check,
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
    sheet_query: avg(is_present)
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
    rebuild_check: null
  - id: second
    measure: other
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
    first = cfg.comparisons[0]
    assert first.dims[0].cube == "regions_region_name"
    assert first.filters["Region"].dashboard == "region"
    assert first.rows is not None and first.rows.grain[1].cube == "attendance_date"
    assert first.defaults["Region"] == ["Camden", "Newark", "Paterson"]
    assert first.rebuild_check is None
    assert cfg.decisions[0].call == "deliberate"


def test_an_email_key_is_refused(tmp_path):
    path = _write(tmp_path, "email: a@example.org\n" + EXAMPLE)

    with pytest.raises(ConfigError, match=r"email: .*--email"):
        load_view_config(path)


def test_dashboard_columns_names_must_be_identifiers(tmp_path):
    text = EXAMPLE.replace(
        "    sheet_query: avg(is_present)\n",
        '    sheet_query: avg(is_present)\n    dashboard_columns: {"bad name": "1"}\n',
        1,
    )

    with pytest.raises(ConfigError, match=r"dashboard_columns"):
        load_view_config(_write(tmp_path, text))


def test_unknown_call_is_refused(tmp_path):
    path = _write(tmp_path, EXAMPLE.replace("call: deliberate", "call: maybe"))

    with pytest.raises(ConfigError, match=r"decisions\[0\]\.call"):
        load_view_config(path)


def test_sheet_query_and_sheet_query_sql_are_exclusive(tmp_path):
    text = EXAMPLE.replace(
        "sheet_query: avg(is_present)",
        "sheet_query: avg(is_present)\n    sheet_query_sql: select 1",
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


def test_write_rebuild_check_changes_only_that_comparison(tmp_path):
    path = _write(tmp_path, EXAMPLE)
    proof = {"fingerprint": "f00", "cells": 12, "matched_at": "2026-10-27"}

    write_rebuild_check(path, "ada-y1-region", proof)

    text = path.read_text()
    assert text == EXAMPLE.replace(
        "    rebuild_check: null\n",
        "    rebuild_check:\n      fingerprint: f00\n      cells: 12\n"
        "      matched_at: '2026-10-27'\n",
    )
    cfg = load_view_config(path)
    assert cfg.comparisons[0].rebuild_check is not None
    assert cfg.comparisons[0].rebuild_check.fingerprint == "f00"
    assert cfg.comparisons[1].rebuild_check is None


def test_write_rebuild_check_adds_missing_key_and_replaces_existing(tmp_path):
    path = _write(tmp_path, EXAMPLE)

    write_rebuild_check(
        path, "second", {"fingerprint": "a", "cells": 1, "matched_at": "x"}
    )
    write_rebuild_check(
        path, "second", {"fingerprint": "b", "cells": 2, "matched_at": "y"}
    )

    cfg = load_view_config(path)
    assert cfg.comparisons[1].rebuild_check is not None
    assert cfg.comparisons[1].rebuild_check.fingerprint == "b"


def test_write_rebuild_check_unknown_id(tmp_path):
    path = _write(tmp_path, EXAMPLE)

    with pytest.raises(ConfigError, match="nope"):
        write_rebuild_check(path, "nope", {})


def test_time_dimension_is_read(tmp_path):
    cfg = load_view_config(_write(tmp_path, EXAMPLE))

    assert cfg.time_dimension == "attendance_date"


@pytest.mark.parametrize("key", ["anchors", "identities"])
def test_an_anchor_or_identity_block_is_refused(tmp_path, key):
    path = _write(tmp_path, EXAMPLE + f"{key}: []\n")

    with pytest.raises(ConfigError, match=f"{key}: delete this block"):
        load_view_config(path)


def test_rows_need_a_time_dimension(tmp_path):
    text = EXAMPLE.replace("time_dimension: attendance_date\n", "")

    with pytest.raises(ConfigError, match="time_dimension.*comparison rows"):
        load_view_config(_write(tmp_path, text))


def test_time_dimension_is_optional_without_rows(tmp_path):
    text = EXAMPLE.replace("time_dimension: attendance_date\n", "")
    head, tail = text.split("    rows:\n", 1)
    text = (
        head + "    rebuild_check: null" + tail.split("    rebuild_check: null", 1)[1]
    )

    cfg = load_view_config(_write(tmp_path, text))

    assert cfg.time_dimension is None
    assert cfg.comparisons[0].rows is None


def test_proof_keeps_workbook_updated_at(tmp_path):
    path = _write(tmp_path, EXAMPLE)
    write_rebuild_check(
        path,
        "ada-y1-region",
        {
            "fingerprint": "f",
            "cells": 3,
            "matched_at": "2026-10-27T10:00:00+00:00",
            "workbook_updated_at": "2026-10-20T09:00:00+00:00",
            "sheet_query_fingerprint": "p00",
            "cuts": ["{}", '{"Region": "Miami"}'],
        },
    )

    proof = load_view_config(path).comparisons[0].rebuild_check

    assert proof is not None
    assert proof.workbook_updated_at == "2026-10-20T09:00:00+00:00"
    assert proof.sheet_query_fingerprint == "p00"
    assert proof.cuts == ["{}", '{"Region": "Miami"}']


def test_proof_keeps_totals_skipped(tmp_path):
    path = _write(tmp_path, EXAMPLE)
    write_rebuild_check(
        path,
        "ada-y1-region",
        {"fingerprint": "f", "cells": 1, "matched_at": "x", "totals_skipped": 2},
    )

    proof = load_view_config(path).comparisons[0].rebuild_check

    assert proof is not None and proof.totals_skipped == 2


def test_negative_totals_skipped_is_refused(tmp_path):
    path = _write(tmp_path, EXAMPLE)
    write_rebuild_check(
        path,
        "ada-y1-region",
        {"fingerprint": "f", "cells": 1, "matched_at": "x", "totals_skipped": -1},
    )

    with pytest.raises(ConfigError, match=r"rebuild_check\.totals_skipped"):
        load_view_config(path)


def test_proof_without_cuts_reads_as_unknown(tmp_path):
    path = _write(tmp_path, EXAMPLE)
    write_rebuild_check(
        path, "ada-y1-region", {"fingerprint": "f", "cells": 1, "matched_at": "x"}
    )

    proof = load_view_config(path).comparisons[0].rebuild_check

    assert proof is not None and proof.cuts is None
    assert proof.totals_skipped is None


def test_also_facts_load_as_listed(tmp_path):
    text = EXAMPLE.replace(
        "time_dimension: attendance_date\n",
        "time_dimension: attendance_date\nalso_facts: [kipptaf_marts.fct_g]\n",
    )

    assert load_view_config(_write(tmp_path, text)).also_facts == [
        "kipptaf_marts.fct_g"
    ]
    assert load_view_config(_write(tmp_path, EXAMPLE)).also_facts == []


@pytest.mark.parametrize(
    "value",
    ["kipptaf_marts.fct_g", "[kipptaf_marts]", "[a.b.c]", "['a;b.c']", "[fct_g]"],
)
def test_also_facts_that_are_not_a_list_of_tables_are_refused(tmp_path, value):
    text = EXAMPLE.replace(
        "time_dimension: attendance_date\n",
        f"time_dimension: attendance_date\nalso_facts: {value}\n",
    )

    with pytest.raises(ConfigError, match="also_facts"):
        load_view_config(_write(tmp_path, text))


def test_fact_dataset_moves_also_facts_with_the_fact(tmp_path):
    text = EXAMPLE.replace(
        "time_dimension: attendance_date\n",
        "time_dimension: attendance_date\nalso_facts: [kipptaf_marts.fct_g]\n",
    )

    cfg = with_fact_dataset(
        load_view_config(_write(tmp_path, text)), "zz_a_kipptaf_marts"
    )

    assert cfg.also_facts == ["zz_a_kipptaf_marts.fct_g"]


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

SHAPE = "    sheet_query: avg(is_present)\n"
GAP_DECISION = """\
  - id: no-team
    missing_cut: Team
    call: deliberate
    reason: Team is a homeroom label
"""


VALUES = "        - { dashboard: is_present, cube: attendance_value }\n"


def test_rows_take_a_dashboard_side_scope(tmp_path):
    scope = "      dashboard_scope:\n        - { dashboard: iep_status, values: [No IEP] }\n"
    text = EXAMPLE.replace(VALUES, VALUES + scope, 1)

    rows = load_view_config(_write(tmp_path, text)).comparisons[0].rows

    assert rows.dashboard_scope == [
        {"dashboard": "iep_status", "operator": "equals", "values": ["No IEP"]}
    ]


def test_rows_dashboard_scope_defaults_to_none(tmp_path):
    rows = load_view_config(_write(tmp_path, EXAMPLE)).comparisons[0].rows
    assert rows.dashboard_scope == []


@pytest.mark.parametrize("kind", ["mean", "count_students"])
def test_rows_cell_is_refused(tmp_path, kind):
    text = EXAMPLE.replace(VALUES, VALUES + f"      cell: {kind}\n", 1)
    with pytest.raises(ConfigError, match=r"rows\.cell: delete it; cells close by"):
        load_view_config(_write(tmp_path, text))


def test_rows_dashboard_scope_takes_only_a_column_name(tmp_path):
    scope = '      dashboard_scope:\n        - { dashboard: "x; DROP", values: [1] }\n'
    text = EXAMPLE.replace(VALUES, VALUES + scope, 1)
    with pytest.raises(ConfigError, match="dashboard_scope"):
        load_view_config(_write(tmp_path, text))


REDUCE = "      reduce: { rule: latest, by: calendardate }\n"


def test_rows_reduce_takes_latest_and_a_column(tmp_path):
    text = EXAMPLE.replace(VALUES, VALUES + REDUCE, 1)

    rows = load_view_config(_write(tmp_path, text)).comparisons[0].rows

    assert rows.reduce == {"rule": "latest", "by": "calendardate"}


def test_rows_reduce_defaults_to_none(tmp_path):
    rows = load_view_config(_write(tmp_path, EXAMPLE)).comparisons[0].rows
    assert rows.reduce == {}


@pytest.mark.parametrize(
    "reduce, why",
    [
        ("{ rule: first, by: d }", "must be one of latest"),
        ("{ rule: latest }", "by"),
        ('{ rule: latest, by: "d; drop" }', "identifier"),
        ("{ rule: latest, by: d, sql: x }", "sql"),
        ("{ rule: latest, by: __reduce_by }", "__"),
    ],
)
def test_rows_reduce_refuses(tmp_path, reduce, why):
    text = EXAMPLE.replace(VALUES, VALUES + f"      reduce: {reduce}\n", 1)
    with pytest.raises(ConfigError, match=why):
        load_view_config(_write(tmp_path, text))


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
    rebuild_check:
      fingerprint: f
      cells: 3
      matched_at: '2026-10-27T00:00:00+00:00'
      missing_cuts: [Team]
      missing_filters: [Enroll Status, Term]
      restricting_filters: [Enroll Status]
      filter_notes:
        Grade Copy: copy of Grade
      missing_columns:
        Enroll Status: enroll_status
"""
    text = EXAMPLE.replace("    rebuild_check: null\n", proof)
    p = load_view_config(_write(tmp_path, text)).comparisons[0].rebuild_check
    assert p.filter_notes == {"Grade Copy": "copy of Grade"}
    assert p.missing_columns == {"Enroll Status": "enroll_status"}
    assert p.missing_cuts == ["Team"]
    assert p.missing_filters == ["Enroll Status", "Term"]
    assert p.restricting_filters == ["Enroll Status"]


def test_old_rebuild_check_reads_missing_lists_as_unknown(tmp_path):
    text = EXAMPLE.replace(
        "    rebuild_check: null\n",
        "    rebuild_check:\n      fingerprint: f\n      cells: 1\n",
    )
    p = load_view_config(_write(tmp_path, text)).comparisons[0].rebuild_check
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
    sheet_query: sum(is_tardy)
    rebuild_check: null
  - id: absent
    <<: *roster
    measure: count_absent_days
    sheet_field: "# Absences"
    sheet_query: sum(is_absent)
"""


def test_shared_blocks_load_like_repeated_keys(tmp_path):
    cfg = load_view_config(_write(tmp_path, SHARED))
    tardy, absent = cfg.comparisons
    assert (tardy.sheet, absent.sheet) == ("Roster", "Roster")
    assert tardy.split_rows == absent.split_rows == "sum"
    assert tardy.sheet_field == "# Tardy" and absent.sheet_field == "# Absences"
    assert tardy.dims == absent.dims


def test_write_rebuild_check_keeps_the_shared_block(tmp_path):
    path = _write(tmp_path, SHARED)
    write_rebuild_check(path, "absent", {"fingerprint": "f", "cells": 3})
    text = path.read_text()
    assert "roster: &roster" in text and text.count("<<: *roster") == 2
    cfg = load_view_config(path)
    assert cfg.comparisons[1].rebuild_check.cells == 3
    assert cfg.comparisons[0].rebuild_check is None


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


@pytest.mark.parametrize("value", ["true", "false"])
def test_a_cells_decision_is_refused(tmp_path, value):
    text = EXAMPLE + CELLS_DECISION.replace("cells: true", f"cells: {value}")
    with pytest.raises(
        ConfigError,
        match="cells: delete this decision; covered cells need none, and a "
        "formula difference takes formula: true",
    ):
        load_view_config(_write(tmp_path, text))


FORMULA_DECISION = CELLS_DECISION.replace("cells: true", "formula: true")


def test_a_formula_decision_loads(tmp_path):
    (*_, d) = load_view_config(_write(tmp_path, EXAMPLE + FORMULA_DECISION)).decisions
    assert (d.id, d.comparison, d.formula) == ("tardy-cells", "ada-y1-region", True)
    assert d.fingerprints == {"cube": "abc", "dashboard": "def"} and d.group == {}


def test_a_formula_decision_needs_a_comparison(tmp_path):
    text = EXAMPLE + FORMULA_DECISION.replace("    comparison: ada-y1-region\n", "")
    with pytest.raises(ConfigError, match=r"comparison: is required"):
        load_view_config(_write(tmp_path, text))


def test_formula_and_group_are_exclusive(tmp_path):
    both = FORMULA_DECISION.replace(
        "formula: true\n", "formula: true\n    group: { column: x, values: ['1'] }\n"
    )
    with pytest.raises(
        ConfigError,
        match="set only one of group, missing_cut, missing_filter, formula and cause",
    ):
        load_view_config(_write(tmp_path, EXAMPLE + both))


def test_a_formula_decision_loads_its_recorded_check_cells(tmp_path):
    text = EXAMPLE + FORMULA_DECISION.replace("def }", "def, matched_only: '3' }")
    (*_, d) = load_view_config(_write(tmp_path, text)).decisions
    assert d.fingerprints["matched_only"] == "3"


@pytest.mark.parametrize(
    ("decision", "value", "match"),
    [
        (FORMULA_DECISION, "many", "must be a whole number"),
        (FORMULA_DECISION, "'-1'", "must be a whole number"),
        # A digit `int` cannot read.
        (FORMULA_DECISION, "'²'", "must be a whole number"),
        (
            FORMULA_DECISION.replace(
                "formula: true", "group: { column: x, values: ['1'] }"
            ),
            "'3'",
            "belongs to a formula decision",
        ),
    ],
)
def test_a_bad_recorded_check_cell_count_is_refused(tmp_path, decision, value, match):
    text = EXAMPLE + decision.replace("def }", f"def, matched_only: {value} }}")
    with pytest.raises(ConfigError, match=rf"fingerprints\.matched_only: {match}"):
        load_view_config(_write(tmp_path, text))


def test_formula_must_be_true(tmp_path):
    text = EXAMPLE + FORMULA_DECISION.replace("formula: true", "formula: false")
    with pytest.raises(ConfigError, match=r"formula: must be true"):
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


EXAMPLE_DECISION = (
    "  - id: example\n    comparison: ada-y1-region\n"
    '    group: { column: grade_level, values: ["9"] }\n'
    "    call: deliberate\n    reason: counted differently\n"
    '    task: ""\n    fingerprints: { cube: abc, dashboard: def }\n'
)


@pytest.mark.parametrize(
    "flow",
    [
        "  - {id: example, missing_filter: T, call: deliberate, reason: r}\n",
        # The commit hook's formatter wraps a long flow item over lines.
        "  - {\n      id: example,\n      missing_filter: T,\n"
        "      call: deliberate,\n      reason: r,\n    }\n",
    ],
    ids=["one line", "wrapped"],
)
def test_write_decision_replaces_a_flow_mapping_item(tmp_path, flow):
    path = _write(tmp_path, EXAMPLE.replace(EXAMPLE_DECISION, flow) + "# tail\n")
    assert [d.id for d in load_view_config(path).decisions] == ["example"]

    write_decision(
        path,
        {"id": "example", "missing_filter": "T", "call": "fix_cube", "reason": "o",
         "task": "#1"},
    )  # fmt: skip

    (d,) = load_view_config(path).decisions
    assert (d.missing_filter, d.call, d.reason, d.task) == ("T", "fix_cube", "o", "#1")
    after = path.read_text()
    assert "{" not in after.split("decisions:", 1)[1]
    assert after.endswith("# tail\n")


def test_write_decision_writes_block_items(tmp_path):
    path = _write(tmp_path, EXAMPLE.split("decisions:")[0])
    write_decision(
        path, {"id": "a", "missing_filter": "Team", "call": "deliberate", "reason": "r"}
    )
    group = {"id": "b", "comparison": "ada-y1-region",
             "group": {"column": "grade_level", "values": ["9"]},
             "call": "deliberate", "reason": "r",
             "fingerprints": {"cube": "abc", "dashboard": "def"}}  # fmt: skip
    write_decision(path, group)

    written = path.read_text().split("decisions:\n", 1)[1]
    assert written.startswith(
        "  - id: a\n    missing_filter: Team\n    call: deliberate\n    reason: r\n"
        "  - id: b\n"
    )
    assert "{" not in written and "[" not in written
    assert load_view_config(path).decisions[1].group == group["group"]


def test_block_and_flow_decisions_share_one_fingerprint(tmp_path):
    decisions_fingerprint = decisions.decisions_fingerprint
    flow = "  - {id: example, missing_filter: T, call: deliberate, reason: r}\n"
    path = _write(tmp_path, EXAMPLE.replace(EXAMPLE_DECISION, flow))
    before = decisions_fingerprint(load_view_config(path).decisions)

    write_decision(
        path,
        {"id": "example", "missing_filter": "T", "call": "deliberate", "reason": "r"},
    )

    assert "{" not in path.read_text().split("decisions:", 1)[1]
    assert decisions_fingerprint(load_view_config(path).decisions) == before


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
    fingerprints: { cube: abc, dashboard: def, explanation: "0f0f" }
"""


def test_cause_decision_loads(tmp_path):
    d = load_view_config(_write(tmp_path, EXAMPLE + CAUSE_DECISION)).decisions[1]

    assert (d.comparison, d.group, d.answer) == ("ada-y1-region", {}, "")
    assert d.cause == {
        "side": "cube",
        "label": "score has no section on the anchor date",
    }
    assert d.fingerprints["explanation"] == "0f0f"


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
        "fingerprints": {"cube": "abc", "dashboard": "def", "explanation": "0f"},
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


@pytest.mark.parametrize(
    "old, new",
    [("probe", "sheet_query"), ("probe_sql", "sheet_query_sql"),
     ("proof", "rebuild_check")],
)  # fmt: skip
def test_an_old_key_is_refused_with_its_new_name(tmp_path, old, new):
    measure = "    measure: avg_daily_attendance\n"
    path = _write(tmp_path, EXAMPLE.replace(measure, measure + f"    {old}: x\n", 1))

    with pytest.raises(ConfigError) as exc:
        load_view_config(path)

    assert str(exc.value) == (
        f"{path}: comparisons[0].{old}: renamed; write it as {new}"
    )


@pytest.mark.parametrize(
    "old, new",
    [("proven_at", "matched_at"), ("probe_fingerprint", "sheet_query_fingerprint")],
)
def test_an_old_rebuild_check_key_is_refused_with_its_new_name(tmp_path, old, new):
    block = f"    rebuild_check:\n      fingerprint: f00\n      {old}: x\n"
    path = _write(tmp_path, EXAMPLE.replace("    rebuild_check: null\n", block, 1))

    with pytest.raises(ConfigError) as exc:
        load_view_config(path)

    assert str(exc.value) == (
        f"{path}: comparisons[0].rebuild_check.{old}: renamed; write it as {new}"
    )


def test_an_old_decision_proof_fingerprint_is_refused_with_its_new_name(tmp_path):
    old = CAUSE_DECISION.replace('explanation: "0f0f"', 'proof: "0f0f"')
    path = _write(tmp_path, EXAMPLE + old)

    with pytest.raises(ConfigError) as exc:
        load_view_config(path)

    assert str(exc.value) == (
        f"{path}: decisions[1].fingerprints.proof: renamed; write it as explanation"
    )


MERGED = """\
view: v
fact: d.t
shared:
  roster: &roster
    workbook: wb
comparisons:
  - <<: *roster
    id: goal  # the goal sheet
    measure: m
decisions:
  - id: goal
    comparison: goal
    call: deliberate
    reason: r
    formula: true
"""


def test_write_rebuild_check_finds_a_comparison_that_opens_with_a_merge_key(tmp_path):
    path = _write(tmp_path, MERGED)

    write_rebuild_check(
        path, "goal", {"fingerprint": "f", "cells": 1, "matched_at": "t"}
    )

    c = load_view_config(path).comparisons[0]
    assert c.rebuild_check.fingerprint == "f" and c.workbook == "wb"


def test_comparison_item_ignores_a_decision_with_the_same_id():
    lines = MERGED.splitlines()

    start, end, key_indent = comparison_item(lines, "goal")

    assert lines[start] == "  - <<: *roster"
    assert lines[end] == "decisions:"
    assert key_indent == 4
    assert comparison_item(lines, "missing") is None


def test_find_comparison_raises_when_no_item_matches(tmp_path):
    path = _write(
        tmp_path,
        MERGED.replace(
            "  - <<: *roster\n    id: goal  # the goal sheet\n    measure: m\n",
            "  - {id: other}\n",
        ),
    )

    with pytest.raises(ConfigError, match="no comparison with id 'goal'"):
        find_comparison(path, "goal")


def test_write_rebuild_check_rewrites_a_flow_mapping_comparison_as_block(tmp_path):
    path = _write(
        tmp_path,
        MERGED.replace(
            "  - <<: *roster\n    id: goal  # the goal sheet\n    measure: m\n",
            "  - {id: other, measure: m}\n  - {id: goal, measure: m}\n",
        ),
    )
    find_comparison(path, "goal")
    assert comparison_item(path.read_text().splitlines(), "goal") == (7, 8, 4)

    write_rebuild_check(path, "goal", {"fingerprint": "f"})

    other, goal = load_view_config(path).comparisons
    assert (goal.id, goal.measure, goal.rebuild_check.fingerprint) == ("goal", "m", "f")
    assert other.rebuild_check is None
    assert "  - id: goal\n    measure: m\n    rebuild_check:\n" in path.read_text()


def test_write_rebuild_check_restores_a_flow_comparison_that_does_not_load(tmp_path):
    text = MERGED.replace(
        "  - <<: *roster\n    id: goal  # the goal sheet\n    measure: m\n",
        "  - {id: goal, measure: m}\n",
    )
    path = _write(tmp_path, text)

    with pytest.raises(ConfigError, match=r"proven_at.*the file is unchanged"):
        write_rebuild_check(path, "goal", {"fingerprint": "f", "proven_at": "t"})

    assert path.read_text() == text


def test_find_comparison_names_a_flow_list_of_comparisons(tmp_path):
    old = "comparisons:\n  - <<: *roster\n    id: goal  # the goal sheet\n    measure: m\n"
    path = _write(
        tmp_path, MERGED.replace(old, "comparisons: [{id: goal, measure: m}]\n")
    )

    for edit in (
        lambda: find_comparison(path, "goal"),
        lambda: write_rebuild_check(path, "goal", {"fingerprint": "f"}),
    ):
        with pytest.raises(ConfigError) as exc:
            edit()
        assert str(exc.value) == (
            f"{path}: comparisons: 'goal' cannot be edited by line; write it "
            "as a block list (`- id: ...` items)"
        )


@pytest.mark.parametrize(
    "id_line", ['  - id: "goal"', "  - id: 'goal'", "  - id: goal  # the goal sheet"]
)
def test_comparison_item_reads_a_quoted_or_commented_id(id_line):
    lines = ["comparisons:", "  - id: other", id_line, "    measure: m"]

    assert comparison_item(lines, "goal") == (2, 4, 4)


def test_comparison_item_reads_a_block_list_at_indent_0():
    lines = [
        "comparisons:",
        "- id: other",
        "  measure: m",
        "- id: goal",
        "  measure: m",
        "decisions: []",
    ]

    assert comparison_item(lines, "goal") == (3, 5, 2)


def test_comparison_item_takes_the_first_of_two_items_with_one_id():
    lines = [
        "comparisons:",
        "  - id: goal",
        "    measure: first",
        "  - id: goal",
        "    measure: second",
    ]

    assert comparison_item(lines, "goal") == (1, 3, 4)


def test_write_rebuild_check_inserts_before_trailing_blanks_and_comments(tmp_path):
    text = (
        "view: v\nfact: d.t\ncomparisons:\n"
        "  - id: goal\n    measure: m\n\n  # the next one\n"
        "  - id: other\n    measure: m\n\n# the end\n"
    )
    path = _write(tmp_path, text)

    write_rebuild_check(path, "goal", {"fingerprint": "f"})
    write_rebuild_check(path, "other", {"fingerprint": "g"})

    assert path.read_text() == (
        "view: v\nfact: d.t\ncomparisons:\n"
        "  - id: goal\n    measure: m\n    rebuild_check:\n      fingerprint: f\n"
        "\n  # the next one\n"
        "  - id: other\n    measure: m\n    rebuild_check:\n      fingerprint: g\n"
        "\n# the end\n"
    )


def test_write_decision_replaces_a_decision_whose_id_is_not_its_first_key(tmp_path):
    path = _write(
        tmp_path,
        MERGED.replace(
            "  - id: goal\n    comparison: goal\n",
            "  - comparison: goal\n    id: goal\n",
        ),
    )

    write_decision(
        path,
        {"id": "goal", "comparison": "goal", "call": "deliberate", "reason": "new"},
    )

    (d,) = load_view_config(path).decisions
    assert (d.call, d.reason) == ("deliberate", "new")


# Every field an existing validation file sets, the rebuild check included,
# with placeholder values. The golden digests below were taken from the code
# before `unpublished` and `rebuild_check.published` existed: a file without
# them must keep every saved result and checkpoint it has.
FINGERPRINT_FIXTURE = """\
view: example_view
fact: kipptaf_marts.fct_example
time_dimension: week_start_date
comparisons:
  - id: example__sheet
    measure: example_measure
    confirmed: true
    workbook: 00000000-0000-0000-0000-000000000000
    sheet: Example Sheet
    dashboard_view: kipptaf_tableau.rpt_tableau__example
    sheet_query: MAX(goal_tableau) - AVG(is_mastery_int)
    decimals: 2
    sheet_field: Example Field
    split_rows: sum
    dims:
      - { dashboard: week_start_monday, cube: week_start_date }
      - { dashboard: grade_level, cube: grade_level }
    filters:
      Academic Year: { dashboard: academic_year, cube: academic_year }
      Response Type: { dashboard: response_type, cube: response_type }
    defaults:
      Academic Year: 2026
      Response Type: overall
    cuts: [{}, { Response Type: standard }]
    scope:
      - { cube: is_enrolled, operator: equals, values: [true] }
    dashboard_filters:
      - { dashboard: is_mastery_int, operator: set }
    rows:
      grain:
        - { dashboard: row_key_a, cube: row_key_a }
        - { dashboard: row_key_b, cube: row_key_b }
      values:
        - { dashboard: is_mastery, cube: is_mastery }
      dashboard_scope:
        - { dashboard: source, operator: equals, values: [example] }
      reduce: { rule: latest, by: loaded_at }
    dashboard_columns:
      goal_tableau: CASE WHEN grade_level < 9 THEN 0.8 ELSE goal END
    parameters:
      Example Parameter: Example Member
    shelves:
      drop: [Example Group]
      add: { rows: [Grade Level] }
      clear_filters: [Example Filter]
    definitions:
      dashboard: The dashboard's words.
      cube: Cube's words.
    rebuild_check:
      fingerprint: aaaa
      cells: 483
      matched_at: "2026-11-16T00:10:47.795513+00:00"
      workbook_updated_at: "2026-11-15T23:42:43+00:00"
      sheet_query_fingerprint: bbbb
      source_fingerprint: cccc
      cuts:
        - "{}"
      totals_skipped: 0
      shelves:
        drop:
          - Example Group
        clear_filters:
          - Example Filter
        add:
          rows:
            - Grade Level
      missing_cuts: []
      missing_filters:
        - Example Missing Filter
      restricting_filters: []
      filter_notes:
        Example Switch: display switch on Example Parameter
      missing_columns:
        Example Missing Filter: example_column
"""
MINIMAL = """\
view: v
fact: kipptaf_marts.f
comparisons:
  - id: minimal
    measure: m
    rebuild_check: null
"""


@pytest.mark.parametrize(
    "text, entry, checkpoint",
    [
        (
            FINGERPRINT_FIXTURE,
            "5a184bcc491098df1b50e0a6af9f1de9f41bce44920054038d976b21ccfb1072",
            "6b3cf179e7cd4c959a72054a5a898285198046c9597758d83eae453c62e47024",
        ),
        (
            MINIMAL,
            "1e6d1d3e1cbe17e054a53083c55be46390cd0fca9ffeb4d1202e382505a078cb",
            "971e691dcc902e25342ba3fb3865b2e20a96979fd785fd8812c7edada308e7d0",
        ),
    ],
)
def test_new_keys_left_unset_keep_every_fingerprint(tmp_path, text, entry, checkpoint):
    (c,) = load_view_config(_write(tmp_path, text)).comparisons

    assert latest.entry_fingerprint(c) == entry
    assert (
        pipeline.checkpoint_fingerprint(c, {"cube": "x", "dashboard": "y"})
        == checkpoint
    )


def test_new_keys_set_change_the_fingerprints(tmp_path):
    (c,) = load_view_config(_write(tmp_path, FINGERPRINT_FIXTURE)).comparisons
    assert c.rebuild_check is not None
    opted = dataclasses.replace(c, unpublished=True)
    recorded = dataclasses.replace(
        c, rebuild_check=dataclasses.replace(c.rebuild_check, published=True)
    )

    entries = {latest.entry_fingerprint(x) for x in (c, opted, recorded)}
    assert len(entries) == 3
    sides = {"cube": "x", "dashboard": "y"}
    checkpoints = {
        pipeline.checkpoint_fingerprint(x, sides) for x in (c, opted, recorded)
    }
    assert len(checkpoints) == 3


def test_unpublished_and_published_load(tmp_path):
    text = FINGERPRINT_FIXTURE.replace(
        "    sheet_field: Example Field\n",
        "    sheet_field: Example Field\n    unpublished: true\n",
    ).replace("      cells: 483\n", "      cells: 483\n      published: false\n")

    (c,) = load_view_config(_write(tmp_path, text)).comparisons

    assert c.unpublished is True
    assert c.rebuild_check is not None and c.rebuild_check.published is False
    (unset,) = load_view_config(_write(tmp_path, FINGERPRINT_FIXTURE)).comparisons
    assert unset.unpublished is False
    assert unset.rebuild_check is not None and unset.rebuild_check.published is None


@pytest.mark.parametrize(
    "old, new, where",
    [
        ("    sheet_field: Example Field\n", "    sheet_field: Example Field\n    unpublished: yes please\n", "unpublished"),
        ("      cells: 483\n", "      cells: 483\n      published: 1\n", "rebuild_check.published"),
    ],
)  # fmt: skip
def test_unpublished_and_published_refuse_a_non_boolean(tmp_path, old, new, where):
    with pytest.raises(ConfigError, match=rf"{where}: must be bool"):
        load_view_config(_write(tmp_path, FINGERPRINT_FIXTURE.replace(old, new)))
