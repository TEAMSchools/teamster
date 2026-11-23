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


def test_a_done_row_goes_with_its_deleted_table(mig):
    table = {
        "gid": "T1",
        "name": "dim_regions",
        "notes": "",
        "subtasks": [row("R1", "Region", [STAT, DDI], done=True)],
    }
    actions = mig.plan(DASHES, [table], {d["gid"]: [] for d in DASHES}, None)
    assert not ops(actions, "create")
    assert not ops(actions, "move")
    assert [a["task"] for a in ops(actions, "delete")] == ["T1"]


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


def test_shared_open_work_gets_no_confirm_item(mig):
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
    assert [(c["parent"], c["name"]) for c in creates] == [
        (DDI, "PR (dbt): open fields · dim_student_enrollments")
    ]
    assert not ops(actions, "block")


def test_stages_go_and_an_emptied_table_is_deleted(mig):
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
    assert [a["task"] for a in ops(actions, "delete")] == ["T6"]


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
    assert "T7" not in [a["task"] for a in ops(actions, "delete")]
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
    assert "T8" not in [a["task"] for a in ops(actions, "delete")]


def test_an_existing_pr_is_reused_and_nothing_is_created(mig):
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
            {
                "gid": "P9",
                "name": "PR (dbt): DDI student flags · dim_student_enrollments",
            },
        ],
    }
    actions = mig.plan(DASHES, [table], children, None)
    assert ops(actions, "move") == [
        {"op": "move", "task": "R10", "parent": "P9", "name": "Magoosh"}
    ]
    assert not ops(actions, "create")


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
    assert not ops(actions, "delete")


def empty_table(gid, name, section, subtasks=()):
    return {
        "gid": gid,
        "name": name,
        "notes": "",
        "memberships": [{"section": {"name": section}}],
        "subtasks": list(subtasks),
    }


def test_an_empty_table_is_deleted_when_no_row_moves_off_it(mig):
    table = empty_table(
        "T20",
        "fct_assessment_growth",
        "1 · Assessments",
        [stage("S20", "cube: growth", done=True)],
    )
    actions = mig.plan(DASHES, [table], {d["gid"]: [] for d in DASHES}, None)
    assert [a["task"] for a in ops(actions, "delete")] == ["T20"]


def test_an_empty_table_with_an_open_stage_is_reported_not_deleted(mig):
    table = empty_table(
        "T21",
        "dim_college_assessment_goals",
        "1 · Assessments",
        [stage("S21", "cube: college_assessment_goals")],
    )
    actions = mig.plan(DASHES, [table], {d["gid"]: [] for d in DASHES}, None)
    assert not ops(actions, "delete")
    assert any(
        "cube: college_assessment_goals" in a["text"] for a in ops(actions, "report")
    )


def test_a_section_run_deletes_only_its_own_empty_tables(mig):
    mine = empty_table("T22", "fct_assessment_growth", "1 · Assessments")
    other = empty_table("T23", "fct_behavior_points", "1 · Behavior")
    actions = mig.plan(
        DASHES,
        [mine, other],
        {d["gid"]: [] for d in DASHES},
        {STAT},
        section="1 · Assessments",
    )
    assert [a["task"] for a in ops(actions, "delete")] == ["T22"]


def test_stages_stay_open_while_rows_remain_on_the_table(mig):
    table = {
        "gid": "T11",
        "name": "fct_assessment_scores_enrollment_scoped",
        "notes": "",
        "subtasks": [
            row("R12", "Lexile", [STAT]),
            row("R13", "Scale score", [DDI]),
            stage("S11", "cube: assessment_expectations_enrollment_scoped"),
        ],
    }
    actions = mig.plan(DASHES, [table], {d["gid"]: [] for d in DASHES}, {STAT})
    assert "S11" not in [a["task"] for a in ops(actions, "delete")]
    assert "T11" not in [a["task"] for a in ops(actions, "delete")]


def test_a_deferred_row_moves_under_its_dashboard(mig):
    deferred = row("R14", "MTSS enrollment", [LIT], tags=("dimension", "needs-data"))
    deferred["notes"] += "\nDeferred: no current-year MTSS data."
    table = {
        "gid": "T12",
        "name": "dim_student_enrollments",
        "notes": "",
        "subtasks": [deferred],
    }
    actions = mig.plan(DASHES, [table], {d["gid"]: [] for d in DASHES}, None)
    assert {
        "op": "move",
        "task": "R14",
        "parent": LIT,
        "name": "MTSS enrollment",
    } in actions
    assert not ops(actions, "create")


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


def test_a_table_holding_a_synced_task_is_reported_not_deleted(mig):
    synced = row("W9", "#4176 | feat(dbt): head of school", [], done=True)
    table = empty_table("T30", "dim_locations", "1 · Assessments", [synced])
    actions = mig.plan(DASHES, [table], {d["gid"]: [] for d in DASHES}, None)
    assert not ops(actions, "delete")
    assert any("#4176" in a["text"] for a in ops(actions, "report"))
