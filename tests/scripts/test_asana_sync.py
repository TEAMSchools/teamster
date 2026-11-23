from __future__ import annotations

import importlib.util
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
