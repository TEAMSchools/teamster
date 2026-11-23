from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts/asana_migrate.py"

LIT, DDI, STAT, MIA = (
    "1000000000000001",
    "1000000000000002",
    "1000000000000003",
    "1000000000000004",
)


def _load():
    spec = importlib.util.spec_from_file_location("asana_migrate", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["asana_migrate"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mig(monkeypatch, tmp_path):
    monkeypatch.delenv("ASANA_PAT", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    return _load()


def link(*gids):
    return "Used by: " + " ".join(f"https://app.asana.com/0/0/{g}/f" for g in gids)


def row(gid, name, used_by, *, done=False, tags=("dimension",), deps=()):
    return {
        "gid": gid,
        "name": name,
        "completed": done,
        "notes": link(*used_by),
        "tags": [{"name": t} for t in tags],
        "dependencies": [{"gid": d} for d in deps],
    }


def stage(gid, name, *, done=False):
    return {
        "gid": gid,
        "name": name,
        "completed": done,
        "notes": "",
        "tags": [],
        "dependencies": [],
    }


DASHES = [
    {"gid": DDI, "name": "DDI Suite", "due_on": "2026-12-01"},
    {"gid": LIT, "name": "Literacy Dashboard", "due_on": "2026-12-02"},
    {"gid": STAT, "name": "State Testing Analysis Tool", "due_on": "2026-12-11"},
    {"gid": MIA, "name": "KIPP Miami FAST & iReady Analysis", "due_on": None},
]


def ops(actions, op):
    return [a for a in actions if a["op"] == op]


def test_owner_is_the_earliest_due_and_undated_sorts_last(mig):
    by_gid = {d["gid"]: d for d in DASHES}
    assert mig.owner_of({STAT, DDI, MIA}, by_gid) == DDI
    assert mig.owner_of({MIA, STAT}, by_gid) == STAT
    assert mig.owner_of({"9999999999999999"}, by_gid) is None


def test_done_row_goes_to_the_owners_already_in_cube_holder(mig):
    table = {
        "gid": "T1",
        "name": "dim_regions",
        "notes": "",
        "subtasks": [row("R1", "Region", [STAT, DDI], done=True)],
    }
    actions = mig.plan(DASHES, [table], {d["gid"]: [] for d in DASHES}, None)
    creates = ops(actions, "create")
    holder = [
        c for c in creates if c["parent"] == DDI and c["name"] == "Already in Cube"
    ]
    assert holder
    assert {
        "op": "move",
        "task": "R1",
        "parent": f"new:{holder[0]['key']}",
        "name": "Region",
    } in actions
    assert not [c for c in creates if c["name"].startswith("Confirm")]


def test_open_row_goes_to_an_existing_pr_that_names_its_table(mig):
    table = {
        "gid": "T2",
        "name": "fct_assessment_scores_enrollment_scoped",
        "notes": "",
        "subtasks": [
            row("R2", "Performance band x", [STAT], deps=("S2",)),
            stage("S2", "cube: assessment_scores"),
        ],
    }
    pr = {
        "gid": "P1",
        "name": "PR (dbt): score columns · fct_assessment_scores_enrollment_scoped",
    }
    children = {d["gid"]: [] for d in DASHES} | {STAT: [pr]}
    actions = mig.plan(DASHES, [table], children, None)
    assert {
        "op": "move",
        "task": "R2",
        "parent": "P1",
        "name": "Performance band x",
    } in actions
    assert {"op": "unlink", "task": "R2", "deps": ["S2"]} in actions
    assert not [c for c in ops(actions, "create") if c["name"].startswith("PR ")]


def test_open_row_with_no_pr_gets_a_new_pr_typed_by_its_open_mart_stage(mig):
    table = {
        "gid": "T3",
        "name": "fct_iready_lessons",
        "notes": "Work: New mart and cube",
        "subtasks": [
            row("R3", "Lessons passed", [STAT], tags=("measure",)),
            stage("S3", "mart: fct_iready_lessons"),
        ],
    }
    actions = mig.plan(DASHES, [table], {d["gid"]: [] for d in DASHES}, None)
    pr = [c for c in ops(actions, "create") if c["name"].startswith("PR ")]
    assert pr == [
        {
            "op": "create",
            "key": pr[0]["key"],
            "parent": STAT,
            "name": "PR (dbt): open fields · fct_iready_lessons",
            "notes": pr[0]["notes"],
            "due_on": "2026-12-11",
        }
    ]
    assert {
        "op": "move",
        "task": "R3",
        "parent": f"new:{pr[0]['key']}",
        "name": "Lessons passed",
    } in actions


def test_new_pr_with_only_cube_work_is_a_cube_pr(mig):
    table = {
        "gid": "T4",
        "name": "dim_assessments",
        "notes": "Work: Add fields",
        "subtasks": [row("R4", "Discipline", [STAT], tags=("dimension", "needs-cube"))],
    }
    actions = mig.plan(DASHES, [table], {d["gid"]: [] for d in DASHES}, None)
    assert [
        c["name"] for c in ops(actions, "create") if c["name"].startswith("PR ")
    ] == ["PR (Cube): open fields · dim_assessments"]


def test_a_later_dashboard_gets_a_confirm_item_for_shared_open_work(mig):
    table = {
        "gid": "T5",
        "name": "dim_student_enrollments",
        "notes": "",
        "subtasks": [
            row("R5", "Magoosh", [STAT, DDI], tags=("dimension", "needs-data"))
        ],
    }
    actions = mig.plan(DASHES, [table], {d["gid"]: [] for d in DASHES}, None)
    creates = ops(actions, "create")
    pr = [c for c in creates if c["name"].startswith("PR ")][0]
    assert pr["parent"] == DDI
    confirm = [c for c in creates if c["name"].startswith("Confirm")]
    assert confirm == [
        {
            "op": "create",
            "key": confirm[0]["key"],
            "parent": STAT,
            "name": "Confirm dim_student_enrollments shipped with DDI Suite",
            "notes": confirm[0]["notes"],
            "due_on": "2026-12-01",
        }
    ]
    assert {
        "op": "block",
        "task": f"new:{confirm[0]['key']}",
        "deps": [f"new:{pr['key']}"],
    } in actions


def test_stages_close_and_an_emptied_table_closes(mig):
    table = {
        "gid": "T6",
        "name": "fct_sight_words",
        "notes": "",
        "subtasks": [
            row("R6", "Sight word", [LIT]),
            stage("S6", "cube: sight_words"),
            stage("S7", "view: sight_words_view", done=True),
        ],
    }
    actions = mig.plan(DASHES, [table], {d["gid"]: [] for d in DASHES}, None)
    closed = [a["task"] for a in ops(actions, "close")]
    assert "S6" in closed and "S7" not in closed
    assert "T6" in closed


def test_a_table_with_a_work_item_left_stays_open(mig):
    item = {
        "gid": "W1",
        "name": "Document cube context issues",
        "completed": False,
        "notes": "",
        "tags": [],
        "dependencies": [],
    }
    table = {
        "gid": "T7",
        "name": "fct_assessment_scores_student_scoped",
        "notes": "",
        "subtasks": [row("R7", "Scale score", [DDI]), item],
    }
    actions = mig.plan(DASHES, [table], {d["gid"]: [] for d in DASHES}, None)
    assert "T7" not in [a["task"] for a in ops(actions, "close")]
    assert any(
        "Document cube context issues" in a["text"] for a in ops(actions, "report")
    )


def test_scope_leaves_rows_owned_outside_it(mig):
    table = {
        "gid": "T8",
        "name": "dim_students",
        "notes": "",
        "subtasks": [row("R8", "Student name", [DDI, STAT], done=True)],
    }
    actions = mig.plan(DASHES, [table], {d["gid"]: [] for d in DASHES}, {STAT})
    assert not ops(actions, "move")
    assert "T8" not in [a["task"] for a in ops(actions, "close")]


def test_existing_holder_and_confirm_are_reused(mig):
    table = {
        "gid": "T9",
        "name": "dim_student_enrollments",
        "notes": "",
        "subtasks": [
            row("R9", "SIPPS", [DDI], done=True),
            row("R10", "Magoosh", [STAT, DDI], tags=("dimension", "needs-data")),
        ],
    }
    children = {d["gid"]: [] for d in DASHES} | {
        DDI: [
            {"gid": "H1", "name": "Already in Cube"},
            {
                "gid": "P9",
                "name": "PR (dbt): DDI student flags · dim_student_enrollments",
            },
        ],
        STAT: [
            {
                "gid": "C1",
                "name": "Confirm dim_student_enrollments shipped with DDI Suite",
            }
        ],
    }
    actions = mig.plan(DASHES, [table], children, None)
    assert {"op": "move", "task": "R9", "parent": "H1", "name": "SIPPS"} in actions
    assert {"op": "move", "task": "R10", "parent": "P9", "name": "Magoosh"} in actions
    assert not [
        c
        for c in ops(actions, "create")
        if c["name"] in ("Already in Cube",) and c["parent"] == DDI
    ]
    assert not [c for c in ops(actions, "create") if c["name"].startswith("Confirm")]


def test_a_section_run_ignores_tables_it_does_not_touch(mig):
    item = {
        "gid": "W2",
        "name": "Rules: weekly behavior rollups",
        "completed": False,
        "notes": "",
        "tags": [],
        "dependencies": [],
    }
    table = {
        "gid": "T10",
        "name": "fct_behavior_points",
        "notes": "",
        "subtasks": [
            row("R11", "Points", [DDI]),
            stage("S10", "cube: behavior_points"),
            item,
        ],
    }
    actions = mig.plan(DASHES, [table], {d["gid"]: [] for d in DASHES}, {STAT})
    assert not ops(actions, "report")
    assert not ops(actions, "close")


def test_stages_stay_open_while_rows_remain_on_the_table(mig):
    table = {
        "gid": "T11",
        "name": "fct_assessment_scores_enrollment_scoped",
        "notes": "",
        "subtasks": [
            row("R12", "Lexile", [STAT]),
            row("R13", "Scale score", [DDI], done=True),
            stage("S11", "cube: assessment_expectations_enrollment_scoped"),
        ],
    }
    actions = mig.plan(DASHES, [table], {d["gid"]: [] for d in DASHES}, {STAT})
    assert "S11" not in [a["task"] for a in ops(actions, "close")]
    assert "T11" not in [a["task"] for a in ops(actions, "close")]


def test_a_deferred_row_goes_to_the_deferred_holder(mig):
    deferred = row("R14", "MTSS enrollment", [LIT], tags=("dimension", "needs-data"))
    deferred["notes"] += "\nDeferred: no current-year MTSS data."
    table = {
        "gid": "T12",
        "name": "dim_student_enrollments",
        "notes": "",
        "subtasks": [deferred],
    }
    actions = mig.plan(DASHES, [table], {d["gid"]: [] for d in DASHES}, None)
    holder = [
        c
        for c in ops(actions, "create")
        if c["parent"] == LIT and c["name"] == "Deferred"
    ][0]
    assert {
        "op": "move",
        "task": "R14",
        "parent": f"new:{holder['key']}",
        "name": "MTSS enrollment",
    } in actions
    assert not [c for c in ops(actions, "create") if c["name"].startswith("PR ")]


def test_an_open_row_prefers_the_cube_pr_when_both_name_the_table(mig):
    table = {
        "gid": "T13",
        "name": "fct_sight_words",
        "notes": "",
        "subtasks": [row("R15", "Quiz number", [LIT])],
    }
    children = {d["gid"]: [] for d in DASHES} | {
        LIT: [
            {"gid": "PD", "name": "PR (dbt): sight-words mart · fct_sight_words"},
            {
                "gid": "PC",
                "name": "PR (Cube): sight-words cube and view · fct_sight_words",
            },
        ]
    }
    actions = mig.plan(DASHES, [table], children, None)
    assert {
        "op": "move",
        "task": "R15",
        "parent": "PC",
        "name": "Quiz number",
    } in actions


def test_a_pr_matches_only_the_tables_after_its_dot(mig):
    table = {
        "gid": "T14",
        "name": "dim_students",
        "notes": "",
        "subtasks": [row("R16", "Most recent grade level", [STAT])],
    }
    children = {d["gid"]: [] for d in DASHES} | {
        STAT: [
            {
                "gid": "PX",
                "name": "PR (dbt): student flags on dim_students_extra · dim_student_enrollments",
            },
            {
                "gid": "PY",
                "name": "PR (dbt): grade fields · dim_student_enrollments, dim_students",
            },
        ]
    }
    actions = mig.plan(DASHES, [table], children, None)
    assert {
        "op": "move",
        "task": "R16",
        "parent": "PY",
        "name": "Most recent grade level",
    } in actions


def test_a_completed_pr_is_never_a_match(mig):
    table = {
        "gid": "T15",
        "name": "dim_assessments",
        "notes": "",
        "subtasks": [row("R17", "Discipline", [STAT])],
    }
    children = {d["gid"]: [] for d in DASHES} | {
        STAT: [
            {
                "gid": "PZ",
                "name": "PR (dbt): band sets · dim_assessments",
                "completed": True,
            },
        ]
    }
    actions = mig.plan(DASHES, [table], children, None)
    assert not [a for a in ops(actions, "move") if a["parent"] == "PZ"]
    assert [
        c
        for c in ops(actions, "create")
        if c["name"] == "PR (Cube): open fields · dim_assessments"
    ]
