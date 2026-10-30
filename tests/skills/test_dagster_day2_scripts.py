from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

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


def _run_category(start: float, end: float, max_runtime: str) -> str:
    run = {
        "runId": "r",
        "startTime": start,
        "endTime": end,
        "tags": [{"key": "dagster/max_runtime", "value": max_runtime}],
    }
    events = [{"__typename": "RunFailureEvent", "message": "", "error": None}]
    return asyncio.run(dc.fetch_failure_detail(FakeGQL(events), run))["category"]


def test_run_at_its_cap_is_max_runtime():
    assert _run_category(0.0, 603.0, "600") == "Max runtime"


def test_run_under_its_cap_keeps_its_category():
    assert _run_category(0.0, 300.0, "600") == "Unclassified"


RUN_ID = "e9e0067b-b503-4919-8ab2-33811557d6f0"


def test_attribute_run_pod_from_name():
    pod = f"dagster-run-{RUN_ID}-abcde"
    assert dc._attribute_pod_event(pod, {RUN_ID}, set()) == (RUN_ID, "FAILURE")


def test_attribute_step_pod_from_audit_labels():
    pod = "dagster-step-0efa5203795199117135e174e58a0c27-8bnk6"
    assert dc._attribute_pod_event(pod, set(), {RUN_ID}, {pod: RUN_ID}) == (
        RUN_ID,
        "SUCCESS",
    )
    assert dc._attribute_pod_event(pod, set(), {RUN_ID}) == (None, "UNKNOWN")


def test_logging_read_follows_page_tokens(monkeypatch):
    pages = [
        {"entries": [{"n": 1}], "nextPageToken": "t1"},
        {"entries": [{"n": 2}]},
    ]
    sent: list[dict] = []

    class Resp:
        status_code = 200

        def __init__(self, body: dict) -> None:
            self._body = body

        def json(self) -> dict:
            return self._body

    def fake_post(_url, headers, json, timeout):
        sent.append(json)
        return Resp(pages[len(sent) - 1])

    monkeypatch.setattr(dc, "gcp_token", lambda: "t")
    monkeypatch.setattr(dc.httpx, "post", fake_post)
    monkeypatch.setattr(dc, "sleep", lambda _s: None)
    assert dc.logging_read("q", "a", "b") == [{"n": 1}, {"n": 2}]
    assert "pageToken" not in sent[0] and sent[1]["pageToken"] == "t1"


def test_alerts_bucket_window_prior_day_and_older(monkeypatch):
    pages = [
        {
            "alerts": [
                {"name": "in", "state": "CLOSED", "openTime": "2026-10-29T22:00:00Z"},
                {
                    "name": "prior",
                    "state": "CLOSED",
                    "openTime": "2026-10-28T22:00:00Z",
                },
            ],
            "nextPageToken": "t1",
        },
        {
            "alerts": [
                {"name": "old", "state": "CLOSED", "openTime": "2026-10-20T00:00:00Z"},
                {"name": "stuck", "state": "OPEN", "openTime": "2026-10-01T00:00:00Z"},
            ]
        },
    ]
    sent: list[dict] = []

    class Resp:
        status_code = 200

        def __init__(self, body: dict) -> None:
            self._body = body

        def json(self) -> dict:
            return self._body

    def fake_get(_url, headers, params, timeout):
        sent.append(params)
        return Resp(pages[len(sent) - 1])

    monkeypatch.setattr(dc, "gcp_token", lambda: "t")
    monkeypatch.setattr(dc.httpx, "get", fake_get)
    got = dc.step_11_alerts("2026-10-29T21:00:00Z")
    assert [a["name"] for a in got["alerts"]] == ["in", "stuck"]
    assert [a["name"] for a in got["priorDay"]] == ["prior"]
    assert sent[1]["pageToken"] == "t1"


def test_logging_read_retries_quota_429(monkeypatch):
    codes = [429, 429, 200]
    waits: list[int] = []

    class Resp:
        def __init__(self, code: int) -> None:
            self.status_code = code
            self.text = ""

        def json(self) -> dict:
            return {"entries": [{"ok": True}]}

    monkeypatch.setattr(dc, "gcp_token", lambda: "t")
    monkeypatch.setattr(dc.httpx, "post", lambda *_a, **_k: Resp(codes.pop(0)))
    monkeypatch.setattr(dc, "sleep", waits.append)
    assert dc.logging_read("q", "a", "b") == [{"ok": True}]
    assert waits == [0, 20, 40]


def test_logging_read_raises_after_four_429s(monkeypatch):
    class Resp:
        status_code = 429
        text = "quota"

    monkeypatch.setattr(dc, "gcp_token", lambda: "t")
    monkeypatch.setattr(dc.httpx, "post", lambda *_a, **_k: Resp())
    monkeypatch.setattr(dc, "sleep", lambda _s: None)
    with pytest.raises(RuntimeError):
        dc.logging_read("q", "a", "b")


def test_correlate_preempting_event():
    ev = {"podName": "p", "reason": "Preempting", "timestamp": "2026-10-29T04:00:05Z"}
    hit = dc._correlate_pod_event(["p"], "2026-10-29T04:00:00Z", [ev])
    assert hit is not None and hit["reason"] == "Preempting"


def test_exception_line_takes_newest_entry(monkeypatch):
    newest_first = [
        {"textPayload": "ValueError: newer"},
        {"textPayload": "KeyError: older"},
    ]
    monkeypatch.setattr(dc, "logging_read", lambda *_a, **_k: newest_first)
    assert dc._resolve_exception_line("p", "2026-10-29T04:00:00Z") == (
        "ValueError: newer"
    )


def test_to_et():
    assert dc.to_et(1793246580.0) == "2026-10-29 00:03:00 EDT"
    assert dc.to_et(None) is None
