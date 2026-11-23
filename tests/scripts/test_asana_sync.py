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
