"""kippmiami/dlt/focus/schedules.py is import-safe; assets.py and sensors.py are
not -- both resolve `FOCUS_DB` credentials eagerly at import (see
src/teamster/CLAUDE.md), and `dlt/focus/__init__.py` imports assets.py before
schedules.py, so even a plain `from ...schedules import x` pulls in the failing
credential resolution via the package chain. Loading the file directly (bypassing
`sys.modules`'s normal package-init cascade) sidesteps that.

This pins the schedule's identity and the `dagster/max_runtime` guard from
#4447, so a future edit can't silently orphan the Dagster+ schedule object (a
name change mints a NEW schedule and abandons its status/tick history) or drop
the runtime bound that keeps a hung 04:00 run from wedging the intraday sensor.
"""

import importlib.util
import pathlib
import sys
from types import ModuleType

import yaml

SCHEDULES_PATH = "src/teamster/code_locations/kippmiami/dlt/focus/schedules.py"
CONFIG_PATH = (
    pathlib.Path(__file__).parents[2]
    / "src/teamster/code_locations/kippmiami/dlt/focus/config/focus.yaml"
)


def _load_schedules_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "kippmiami_focus_schedules_standalone", SCHEDULES_PATH
    )
    assert spec is not None and spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    return module


def test_schedule_identity_and_runtime_bound() -> None:
    module = _load_schedules_module()
    schedule = module.focus_dlt_daily_asset_job_schedule

    assert schedule.name == "kippmiami__dlt__focus__daily_asset_job_schedule"
    assert schedule.cron_schedule == "0 4 * * *"
    assert schedule.tags == {"dagster/max_runtime": "900"}


def test_schedule_targets_only_count_only_tables() -> None:
    module = _load_schedules_module()
    schedule = module.focus_dlt_daily_asset_job_schedule

    config = yaml.safe_load(CONFIG_PATH.read_text())
    expected_table_names = {
        a["table_name"] for a in config["assets"] if a["cursor_column"] is None
    }
    expected_keys = {
        f"{module.asset_key_prefix}/{table_name}" for table_name in expected_table_names
    }

    # A config where every table gained a cursor would silently empty this
    # tier -- fail loudly instead of passing on an empty selection.
    assert expected_keys, "expected at least one count-only table in focus.yaml"

    selected_keys = {
        key.to_user_string()
        for operand in schedule.target.resolvable_to_job.selection.operands
        for key in operand.selected_keys
    }

    assert selected_keys == expected_keys
