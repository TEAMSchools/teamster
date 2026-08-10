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
import sys
from types import ModuleType

SCHEDULES_PATH = "src/teamster/code_locations/kippmiami/dlt/focus/schedules.py"


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
    assert schedule.tags == {"dagster/max_runtime": "3600"}


def test_schedule_targets_every_configured_table() -> None:
    module = _load_schedules_module()
    schedule = module.focus_dlt_daily_asset_job_schedule

    selected_keys = schedule.target.resolvable_to_job.selection.operands

    assert len(selected_keys) == 77
