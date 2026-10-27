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
        ("{ cube: x, operator: gt, values: [1] }", "operator"),
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
        },
    )

    proof = load_view_config(path).comparisons[0].proof

    assert proof is not None
    assert proof.workbook_updated_at == "2026-10-20T09:00:00+00:00"
    assert proof.probe_fingerprint == "p00"
