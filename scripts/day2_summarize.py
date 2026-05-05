# /// script
# requires-python = ">=3.13"
# ///
"""Summarize the Phase-1 artifact written by `scripts/day2_collect.py`.

Prints per-step counts and an error gate so Phase 2 of the /dagster-day2 skill
can quickly verify which steps have data before reading the full JSON. Intended
to be the first thing run after `day2_collect.py`.

Usage:
    uv run scripts/day2_summarize.py                          # default path
    uv run scripts/day2_summarize.py path/to/day2.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

DEFAULT_PATH = Path(".claude/scratch/day2.json")


def _len(obj: object) -> int | str:
    if isinstance(obj, list):
        return len(obj)
    if isinstance(obj, dict):
        return len(obj)
    return "?"


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PATH
    if not path.exists():
        print(f"ERROR: {path} not found. Run scripts/day2_collect.py first.")
        return 1

    data = json.loads(path.read_text())
    window = data.get("window", {})
    print(f"Window: {window.get('utc_start')} → {window.get('utc_end')}")
    print(f"File:   {path}")
    print()

    errored: list[str] = []
    for key in sorted(k for k in data if k.startswith("step_")):
        payload = data[key]
        if isinstance(payload, dict) and "error" in payload:
            errored.append(key)

    s1 = data.get("step_01_failed_runs", {})
    s2 = data.get("step_02_retries", {})
    s3 = data.get("step_03_sensor_ticks", {})
    s4 = data.get("step_04_freshness", {})
    s5 = data.get("step_05_load_failures", {})
    s6 = data.get("step_06_schedule_ticks", {})
    s7 = data.get("step_07_agents", {})
    s8 = data.get("step_08_agent_pod_churn", {})
    s9 = data.get("step_09_daemons", {})
    s10 = data.get("step_10_gke_events", {})
    s11 = data.get("step_11_alerts", {})
    s12 = data.get("step_12_error_groups", {})
    s13 = data.get("step_13_oom_metrics", {})
    s14 = data.get("step_14_queued_runs", {})
    s15 = data.get("step_15_backfills", {})

    sensor_fail_total = sum(
        sensor.get("failureCount", 0)
        for loc in s3.values()
        if isinstance(loc, dict)
        for sensor in loc.values()
        if isinstance(sensor, dict)
    )
    sched_fail_total = sum(len(v) for v in s6.get("scheduleTickFailures", {}).values())

    print(
        f"step_01 runs:        fail={s1.get('failureCount')} success={s1.get('successCount')} canceled={s1.get('canceledCount')}"
    )
    print(f"step_02 retries:     {_len(s2.get('retries'))}")
    print(
        f"step_03 sensor:      {sensor_fail_total} tick failures across {_len(s3)} locations"
    )
    print(
        f"step_04 freshness:   {_len(s4.get('flaggedAssets'))} flagged ({s4.get('policyCount')} policies)"
    )
    print(f"step_05 load fail:   {_len(s5.get('loadFailures'))}")
    print(f"step_06 schedule:    {sched_fail_total} tick failures")
    print(f"step_07 agents:      {s7.get('agentCount')} agents")
    print(
        f"step_08 churn:       {_len(s8.get('events'))} events (skipped={s8.get('skipped', False)})"
    )
    print(f"step_09 daemons:     allHealthy={s9.get('allHealthy')}")
    print(
        f"step_10 gke:         cluster={_len(s10.get('clusterEvents'))} pod={_len(s10.get('podEvents'))}"
    )
    print(f"step_11 alerts:      {_len(s11.get('alerts'))}")
    buckets = s12.get("buckets", {})
    print(
        f"step_12 errgroups:   {_len(s12.get('groups'))} total, inWindow={_len(buckets.get('inWindow'))}, staleOpen={_len(buckets.get('staleOpen'))}"
    )
    print(
        f"step_13 oom:         {_len(s13.get('oomRuns'))} (skipped={s13.get('skipped', False)})"
    )
    print(f"step_14 queued:      stuck={s14.get('stuckCount')}")
    print(
        f"step_15 backfills:   requested={_len(s15.get('requested'))} failed={_len(s15.get('failed'))}"
    )
    print()
    if errored:
        print(
            f"ERROR GATE: {len(errored)} step(s) errored — re-run collector before drawing conclusions:"
        )
        for k in errored:
            print(f"  - {k}: {data[k].get('error')}")
        return 2
    print("ERROR GATE: all steps OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
