from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

SKILL_SCRIPTS = (
    Path(__file__).resolve().parents[2] / ".claude/skills/dagster-day2/scripts"
)


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, SKILL_SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


dc = _load("day2_collect")

BQ_500 = (
    "Database Error in test x (models/x.yml)\n  500 An internal error occurred and "
    "the request could not be completed. This is usually caused by a transient "
    "issue. Error: 80324028; reason: internalError, message: An internal error"
)
HEALTH_CHECK = (
    "Step s failed health check: Discovered failed Kubernetes job "
    "dagster-step-abc for step s."
)


class FakeGQL:
    def __init__(self, events: list[dict]) -> None:
        self.events = events

    async def query(self, _query: str, _variables: dict) -> dict:
        return {"logsForRun": {"events": self.events}}


def _category(events: list[dict]) -> str:
    run = {"runId": "r", "tags": []}
    return asyncio.run(dc.fetch_failure_detail(FakeGQL(events), run))["category"]


def _step_failure(message: str, step_key: str = "s") -> dict:
    return {
        "__typename": "ExecutionStepFailureEvent",
        "stepKey": step_key,
        "error": {"message": message, "className": None},
    }


def test_classify_bigquery_transient():
    assert dc.classify(BQ_500) == "BigQuery transient"


def test_classify_preemption_wins_over_bigquery():
    assert (
        dc.classify(f"DagsterExecutionInterruptedError {BQ_500}")
        == "Preemption/Interrupt"
    )


def test_health_check_without_captured_logs_is_pre_start_kill():
    assert _category([_step_failure(HEALTH_CHECK)]) == "K8s pre-start kill"


def test_health_check_with_captured_logs_is_code_error():
    events = [
        {"__typename": "LogsCapturedEvent", "stepKeys": ["s"]},
        _step_failure(HEALTH_CHECK),
    ]
    assert _category(events) == "Code error"


def test_other_step_captured_logs_do_not_count():
    events = [
        {"__typename": "LogsCapturedEvent", "stepKeys": ["other"]},
        _step_failure(HEALTH_CHECK),
    ]
    assert _category(events) == "K8s pre-start kill"


def test_to_et():
    assert dc.to_et(1793246580.0) == "2026-10-29 00:03:00 EDT"
    assert dc.to_et(None) is None
