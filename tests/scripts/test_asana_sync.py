from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts/asana_sync.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("asana_sync", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["asana_sync"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mod(monkeypatch, tmp_path):
    # No token and no validation file: importing must still do nothing.
    monkeypatch.delenv("ASANA_PAT", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    return _load()


def test_import_has_no_side_effects(mod):
    assert callable(mod.main)


def test_missing_validation_file_means_no_verdicts(mod, tmp_path):
    assert mod.load_validation(str(tmp_path / "latest.json")) is None


def test_validation_file_rows_are_read(mod, tmp_path):
    path = tmp_path / "latest.json"
    path.write_text('{"rows": {"123": {"verdict": "pass"}}}')
    assert mod.load_validation(str(path)) == {"123": {"verdict": "pass"}}


def test_dashboard_gids_reads_the_tag(mod):
    tasks = [
        {"gid": "1", "tags": [{"name": "dashboard"}]},
        {"gid": "2", "tags": []},
        {"gid": "3", "tags": [{"name": "Dashboard"}, {"name": "x"}]},
    ]
    assert mod.dashboard_gids(tasks) == ["1", "3"]


def test_row_kind_from_tags(mod):
    assert mod.row_kind({"tags": [{"name": "measure"}]}) == "measure"
    assert mod.row_kind({"tags": [{"name": "needs-data"}, {"name": "dimension"}]}) == (
        "dimension"
    )
    assert mod.row_kind({"tags": []}) is None


def test_want_status_table_rules(mod):
    mart = {"kind": "mart", "completed": False}
    view = {"kind": "view", "completed": False}
    assert (
        mod.want_status(live=False, stage_blockers=[mart, view], needs_line=None)
        == "needs-data"
    )
    assert (
        mod.want_status(live=False, stage_blockers=[view], needs_line=None)
        == "needs-cube"
    )
    assert (
        mod.want_status(live=False, stage_blockers=[], needs_line="data")
        == "needs-data"
    )
    assert mod.want_status(live=True, stage_blockers=[mart], needs_line=None) is None
    assert mod.want_status(live=False, stage_blockers=[], needs_line=None) is None


def test_want_status_ignores_done_blockers(mod):
    done_mart = {"kind": "mart", "completed": True}
    assert (
        mod.want_status(live=False, stage_blockers=[done_mart], needs_line="cube")
        == "needs-cube"
    )


def _tags(*names):
    return [{"name": n} for n in names]


def test_pr_type_from_bracket(mod):
    assert mod.pr_type("PR SW1 (dbt): fct_sight_words") == "dbt"
    assert mod.pr_type("PR SW2 (Cube): sight_words cube and sight_words_view") == "cube"


def test_pr_type_from_synced_name(mod):
    assert mod.pr_type("#6461 | feat(cube): build Literacy Dashboard in Cube") == "cube"
    assert (
        mod.pr_type("#6394 | feat(dbt,cube): make assessment tagging checks possible")
        == "dbt"
    )
    assert mod.pr_type("Validate Literacy Dashboard in Cube") is None
    assert mod.pr_type("Already in Cube") is None


def test_rows_under_finds_both_depths(mod):
    dash = {"gid": "D"}
    direct = {"gid": "m1", "name": "% Proficient", "tags": _tags("measure")}
    pr = {"gid": "P", "name": "PR L1 (Cube): percentile", "tags": []}
    work = {"gid": "w", "name": "PM design: answer", "tags": []}
    dim = {"gid": "d1", "name": "national_percentile", "tags": _tags("dimension")}
    rows, untagged = mod.rows_under(dash, [direct, pr, work], {"P": [dim]})
    assert rows == [(direct, None), (dim, pr)]
    assert untagged == []


def test_rows_under_skips_table_tasks(mod):
    table = {"gid": "T", "name": "fct_sight_words", "tags": []}
    row = {"gid": "r", "name": "Sight word", "tags": _tags("dimension")}
    rows, untagged = mod.rows_under({"gid": "D"}, [table], {"T": [row]})
    assert rows == [] and untagged == []


def test_untagged_row_under_dashboard_is_reported(mod):
    pr = {"gid": "P", "name": "PR SW2 (Cube): sight_words cube", "tags": []}
    holder = {"gid": "H", "name": "Already in Cube", "tags": []}
    a = {"gid": "a", "name": "quiz number", "tags": []}
    b = {"gid": "b", "name": "value group", "tags": []}
    rows, untagged = mod.rows_under({"gid": "D"}, [pr, holder], {"P": [a], "H": [b]})
    assert rows == []
    assert untagged == [a, b]


def test_open_dbt_blocker_is_needs_data(mod):
    parent = {"name": "PR PM4 (Cube): PM cubes", "completed": False}
    dbt = {"name": "PR PM1 to PM3 (dbt): DIBELS PM facts", "completed": False}
    done_dbt = dict(dbt, completed=True)
    assert (
        mod.want_status_pr(live=False, parent=parent, parent_blockers=[dbt])
        == "needs-data"
    )
    assert (
        mod.want_status_pr(live=False, parent=parent, parent_blockers=[done_dbt])
        == "needs-cube"
    )
    assert (
        mod.want_status_pr(live=False, parent=parent, parent_blockers=[])
        == "needs-cube"
    )


def test_open_dbt_parent_is_needs_data(mod):
    parent = {"name": "PR SW1 (dbt): fct_sight_words", "completed": False}
    assert (
        mod.want_status_pr(live=False, parent=parent, parent_blockers=[])
        == "needs-data"
    )


def test_merged_parent_not_live_is_needs_cube(mod):
    parent = {"name": "PR L1 (Cube): national_percentile", "completed": True}
    assert (
        mod.want_status_pr(live=False, parent=parent, parent_blockers=[])
        == "needs-cube"
    )


def test_live_row_and_holders_have_no_status(mod):
    parent = {"name": "PR L1 (Cube): national_percentile", "completed": False}
    assert mod.want_status_pr(live=True, parent=parent, parent_blockers=[]) is None
    for holder in ("Already in Cube", "Deferred"):
        h = {"name": holder, "completed": False}
        assert mod.want_status_pr(live=False, parent=h, parent_blockers=[]) is None


# ---------------------------------------------------------------- main() with git and Asana stubbed
D = "1213823922716082"
PR = "9000000000000001"
ROW = "9000000000000002"
VIEW_YML = (
    "views:\n  - name: v\n    cubes:\n"
    "      - join_path: student_assessment_scores\n        includes:\n"
    "          - pct_proficient\n"
)
CUBE_YML = (
    "cubes:\n  - name: student_assessment_scores\n    measures:\n"
    "      - name: pct_proficient\n"
)


def _stub_main(mod, monkeypatch, *, views=True, row_done=False):
    writes = []

    def git(*args):
        if args[0] == "ls-tree":
            if args[-1].endswith("views"):
                return "src/cube/model/views/v.yml\n" if views else ""
            return "src/cube/model/cubes/c.yml\n"
        if args[0] == "show":
            return VIEW_YML if args[1].endswith("v.yml") else CUBE_YML
        return ""

    row = {
        "gid": ROW,
        "name": "% Proficient",
        "completed": row_done,
        "notes": "Where it lives: pct_proficient",
        "tags": [{"name": "measure", "gid": mod.MEASURE_TAG}],
        "dependencies": [],
    }
    data = {
        f"/workspaces/{mod.WORKSPACE}/tags": [
            {"name": n, "gid": f"tag-{n}"}
            for n in ("needs-data", "needs-cube", "validated", "dimension")
        ],
        f"/projects/{mod.PROJECT}/tasks": [
            {"gid": D, "name": "Literacy Dashboard", "tags": [{"name": "dashboard"}]}
        ],
        f"/tasks/{D}/subtasks": [
            {
                "gid": PR,
                "name": "PR L1 (Cube): percentile",
                "completed": False,
                "notes": "",
                "tags": [],
                "num_subtasks": 1,
            }
        ],
        f"/tasks/{PR}/subtasks": [row],
    }
    monkeypatch.setattr(mod, "git", git)
    monkeypatch.setattr(mod, "get_all", lambda path, params: data.get(path, []))
    monkeypatch.setattr(mod, "write", lambda desc, *a: writes.append(desc))
    monkeypatch.setenv("ASANA_PAT", "test-token")
    return writes


def _latest(tmp_path, rows):
    d = tmp_path / "asana-sync" / "validation"
    d.mkdir(parents=True)
    (d / "latest.json").write_text(json.dumps({"rows": rows}))


def test_only_apply_guard_sees_nested_rows(mod, monkeypatch, tmp_path):
    _latest(tmp_path, {ROW: {"verdict": "pass"}})
    writes = _stub_main(mod, monkeypatch)
    assert mod.main(["--only", D, "--apply"]) == 0
    assert any("validated" in w for w in writes)


def test_only_apply_guard_stops_before_any_write(mod, monkeypatch, tmp_path):
    _latest(tmp_path, {"someone-else": {"verdict": "pass"}})
    writes = _stub_main(mod, monkeypatch)
    with pytest.raises(SystemExit, match="no verdict"):
        mod.main(["--only", D, "--apply"])
    assert writes == []


def test_empty_cube_read_stops_before_any_write(mod, monkeypatch):
    writes = _stub_main(mod, monkeypatch, views=False, row_done=True)
    with pytest.raises(SystemExit, match="no Cube view files"):
        mod.main(["--only", D])
    assert writes == []


def test_main_asks_for_no_umbrella_task(mod, monkeypatch):
    # table tasks are all top-level; a hard-coded parent task that is gone 404s the run
    _stub_main(mod, monkeypatch)
    seen = []
    inner = mod.get_all

    def get_all(path, params):
        seen.append(path)
        return inner(path, params)

    monkeypatch.setattr(mod, "get_all", get_all)
    assert mod.main(["--only", D]) == 0
    assert not [p for p in seen if p.startswith("/tasks/1219235117880911")]


def test_measure_row_on_a_table_keeps_its_measure_tag(mod, monkeypatch):
    writes = _stub_main(mod, monkeypatch)
    table = "9000000000000003"
    row = {
        "gid": "9000000000000004",
        "name": "% sight words mastered",
        "completed": False,
        "notes": f"Used by: https://app.asana.com/0/0/{D}/f",
        "tags": [{"name": "measure", "gid": mod.MEASURE_TAG}],
        "dependencies": [],
    }
    inner = mod.get_all

    def get_all(path, params):
        if path == f"/projects/{mod.PROJECT}/tasks":
            return inner(path, params) + [
                {"gid": table, "name": "fct_sight_words", "tags": []}
            ]
        if path == f"/tasks/{table}/subtasks":
            return [row]
        return inner(path, params)

    monkeypatch.setattr(mod, "get_all", get_all)
    assert mod.main(["--only", D]) == 0
    assert not [w for w in writes if "% sight words mastered" in w and "dimension" in w]


def test_dashboards_in_section(mod):
    tasks = [
        {
            "gid": "1",
            "tags": [{"name": "dashboard"}],
            "memberships": [{"section": {"name": "1 · Assessments"}}],
        },
        {
            "gid": "2",
            "tags": [{"name": "dashboard"}],
            "memberships": [{"section": {"name": "1 · Attendance"}}],
        },
        {
            "gid": "3",
            "tags": [],
            "memberships": [{"section": {"name": "1 · Assessments"}}],
        },
    ]
    assert mod.dashboards_in_section(tasks, "1 · Assessments") == ["1"]
    assert mod.dashboards_in_section(tasks, None) == ["1", "2"]


def test_untagged_row_with_used_by_under_pr_is_a_dimension(mod):
    pr = {"gid": "P", "name": "PR SW2 (Cube): sight_words cube", "tags": []}
    field = {
        "gid": "f",
        "name": "Quiz number",
        "tags": [],
        "notes": "Used by: https://app.asana.com/0/0/1213823922716082/f",
    }
    loose = {"gid": "x", "name": "check the sheet", "tags": [], "notes": ""}
    rows, untagged = mod.rows_under({"gid": "D"}, [pr], {"P": [field, loose]})
    assert rows == [(field, pr)]
    assert untagged == [loose]


def _with_table(mod, monkeypatch, writes_list):
    table = "9000000000000005"
    dim = {
        "gid": "9000000000000006",
        "name": "Region",
        "completed": True,
        "notes": f"Used by: https://app.asana.com/0/0/{D}/f\nWhere it lives: pct_proficient",
        "tags": [{"name": "dimension", "gid": "tag-dimension"}],
        "dependencies": [],
    }
    inner = mod.get_all

    def get_all(path, params):
        if path == f"/projects/{mod.PROJECT}/tasks":
            return inner(path, params) + [
                {"gid": table, "name": "dim_regions", "tags": []}
            ]
        if path == f"/tasks/{table}/subtasks":
            return [dim]
        return inner(path, params)

    monkeypatch.setattr(mod, "get_all", get_all)
    return table


def test_no_dashboard_gets_table_blocker_links(mod, monkeypatch):
    writes = _stub_main(mod, monkeypatch)
    _with_table(mod, monkeypatch, writes)
    inner = mod.get_all

    def get_all(path, params):
        if path == f"/tasks/{D}/subtasks":
            return []  # a dashboard with no PR tasks
        return inner(path, params)

    monkeypatch.setattr(mod, "get_all", get_all)
    assert mod.main(["--only", D]) == 0
    assert not [w for w in writes if "block it" in w]


def test_section_limits_the_run(mod, monkeypatch):
    _stub_main(mod, monkeypatch)
    inner = mod.get_all
    other = "9000000000000009"

    def get_all(path, params):
        if path == f"/projects/{mod.PROJECT}/tasks":
            return [
                {
                    "gid": D,
                    "name": "Literacy Dashboard",
                    "tags": [{"name": "dashboard"}],
                    "memberships": [{"section": {"name": "1 · Assessments"}}],
                },
                {
                    "gid": other,
                    "name": "Attendance Dashboard",
                    "tags": [{"name": "dashboard"}],
                    "memberships": [{"section": {"name": "1 · Attendance"}}],
                },
            ]
        if path == f"/tasks/{other}/subtasks":
            raise AssertionError("read a dashboard outside the section")
        return inner(path, params)

    monkeypatch.setattr(mod, "get_all", get_all)
    assert mod.main(["--section", "1 · Assessments"]) == 0


def test_work_items_under_a_pr_are_not_reported_as_rows(mod, monkeypatch, capsys):
    _stub_main(mod, monkeypatch)
    inner = mod.get_all
    item = {
        "gid": "9000000000000010",
        "name": "#4393 | feat(dbt): an earlier PR",
        "completed": True,
        "notes": "",
        "tags": [],
        "dependencies": [],
    }

    def get_all(path, params):
        if path == f"/tasks/{PR}/subtasks":
            return inner(path, params) + [item]
        return inner(path, params)

    monkeypatch.setattr(mod, "get_all", get_all)
    assert mod.main(["--only", D]) == 0
    assert "Rows with no kind tag" not in capsys.readouterr().out


def test_main_tags_an_untagged_used_by_row_under_a_pr(mod, monkeypatch):
    writes = _stub_main(mod, monkeypatch)
    inner = mod.get_all
    field = {
        "gid": "9000000000000011",
        "name": "Quiz number",
        "completed": False,
        "notes": f"Used by: https://app.asana.com/0/0/{D}/f",
        "tags": [],
        "dependencies": [],
    }

    def get_all(path, params):
        if path == f"/tasks/{PR}/subtasks":
            return inner(path, params) + [field]
        return inner(path, params)

    monkeypatch.setattr(mod, "get_all", get_all)
    assert mod.main(["--only", D]) == 0
    assert "[dimension] Quiz number: add 'dimension' tag" in writes
