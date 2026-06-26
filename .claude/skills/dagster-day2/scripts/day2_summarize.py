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
    uv run scripts/day2_summarize.py --details                # gate + details
"""

from __future__ import annotations

import argparse
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=DEFAULT_PATH,
        help="Path to day2.json (default: .claude/scratch/day2.json)",
    )
    parser.add_argument(
        "--details",
        action="store_true",
        help="After the gate, dump failure/retry/GKE/error-group details.",
    )
    args = parser.parse_args()
    path: Path = args.path
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
    s16 = data.get("step_16_asset_checks", {})
    s17 = data.get("step_17_degraded_assets", {})

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
    print(
        f"step_16 checks:      total={s16.get('totalChecks')} failed={s16.get('failedCount')}"
        f"  (inWindow err={_len(s16.get('inWindow_error'))} warn={_len(s16.get('inWindow_warn'))};"
        f" stale err={_len(s16.get('stale_error'))} warn={_len(s16.get('stale_warn'))})"
    )
    print(
        f"step_17 degraded:    total={s17.get('totalAssets')} degraded={s17.get('degradedCount')}"
        f"  across {_len(s17.get('byRun'))} failing runs"
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

    if args.details:
        _print_details(data)
    return 0


def _trunc(s: object, n: int = 200) -> str:
    text = "" if s is None else str(s)
    return text if len(text) <= n else text[: n - 1] + "…"


def _print_details(data: dict) -> None:
    print()
    print("=" * 72)
    print("DETAILS")
    print("=" * 72)

    failures = data.get("step_01_failed_runs", {}).get("failures", [])
    print(f"\n[step_01] failures ({len(failures)}):")
    for f in failures:
        run_id = f.get("runId") or "?"
        print(
            f"  {run_id} job={f.get('jobName')} loc={f.get('locationName')} "
            f"cat={f.get('category')} start={f.get('startTime')} end={f.get('endTime')}"
        )
        msg = f.get("runFailureMessage")
        if msg:
            print(f"    msg: {_trunc(msg)}")

    retries = data.get("step_02_retries", {}).get("retries", [])
    print(f"\n[step_02] retries ({len(retries)}):")
    for r in retries:
        parent = r.get("parentRunId") or "?"
        retry = r.get("retryRunId") or "?"
        print(f"  parent={parent} retry={retry} status={r.get('retryStatus')}")

    sensor = data.get("step_03_sensor_ticks", {})
    print("\n[step_03] sensor tick failures:")
    for loc, sensors in sensor.items():
        if not isinstance(sensors, dict):
            continue
        for name, info in sensors.items():
            if not isinstance(info, dict):
                continue
            count = info.get("failureCount", 0)
            if count:
                print(f"  {loc}/{name}: {count} failures")

    sched = data.get("step_06_schedule_ticks", {}).get("scheduleTickFailures", {})
    if sched:
        print("\n[step_06] schedule tick failures:")
        for key, ticks in sched.items():
            print(f"  {key}: {len(ticks)} failures")

    cluster = data.get("step_10_gke_events", {}).get("clusterEvents", [])
    pods = data.get("step_10_gke_events", {}).get("podEvents", [])
    print(f"\n[step_10] GKE cluster events ({len(cluster)}), pod events ({len(pods)}):")
    for e in cluster:
        print(f"  cluster: {_trunc(e, 240)}")
    for e in pods:
        print(f"  pod:     {_trunc(e, 240)}")

    alerts = data.get("step_11_alerts", {}).get("alerts", [])
    if alerts:
        print(f"\n[step_11] alerts ({len(alerts)}):")
        for a in alerts:
            print(f"  {_trunc(a, 240)}")

    s12 = data.get("step_12_error_groups", {})
    buckets = s12.get("buckets", {})
    in_window = buckets.get("inWindow", []) or []
    stale_open = buckets.get("staleOpen", []) or []
    print(
        f"\n[step_12] error groups: inWindow={len(in_window)}, staleOpen={len(stale_open)}"
    )
    for label, groups in (("inWindow", in_window), ("staleOpen", stale_open)):
        for g in groups:
            if not isinstance(g, dict):
                continue
            print(
                f"  [{label}] count={g.get('count')} "
                f"first={g.get('firstSeenTime')} last={g.get('lastSeenTime')} "
                f"cat={g.get('category')}"
            )
            print(f"    exception:     {_trunc(g.get('exception'), 180)}")
            print(f"    exceptionLine: {_trunc(g.get('exceptionLine'), 180)}")
            cpe = g.get("correlatedPodEvent")
            if cpe:
                print(f"    correlatedPodEvent: {_trunc(cpe, 180)}")

    queued = data.get("step_14_queued_runs", {}).get("runs", [])
    if queued:
        print(f"\n[step_14] queued/stuck runs ({len(queued)}):")
        for r in queued:
            print(f"  {_trunc(r, 240)}")

    s15 = data.get("step_15_backfills", {})
    requested = s15.get("requested", []) or []
    failed = s15.get("failed", []) or []
    if requested or failed:
        print(
            f"\n[step_15] backfills: requested={len(requested)}, failed={len(failed)}"
        )
        for b in failed:
            print(f"  failed: {_trunc(b, 240)}")

    s16 = data.get("step_16_asset_checks", {})
    if isinstance(s16, dict) and "error" not in s16:
        total = (
            len(s16.get("inWindow_error") or [])
            + len(s16.get("inWindow_warn") or [])
            + len(s16.get("stale_error") or [])
            + len(s16.get("stale_warn") or [])
        )
        if total:
            print(f"\n[step_16] failed asset checks ({total}):")
            for label in (
                "inWindow_error",
                "inWindow_warn",
                "stale_error",
                "stale_warn",
            ):
                items = s16.get(label) or []
                if not items:
                    continue
                print(f"  [{label}] ({len(items)}):")
                for x in items:
                    print(
                        f"    {x.get('asset')}/{_trunc(x.get('check'), 80)}"
                        f"  status={x.get('status')} sev={x.get('severity')} ts={x.get('timestamp')}"
                    )
                    md = x.get("metadata")
                    if md:
                        print(f"      meta: {_trunc(md, 240)}")

    s17 = data.get("step_17_degraded_assets", {})
    if isinstance(s17, dict) and "error" not in s17:
        by_run = s17.get("byRun") or []
        if by_run:
            print(
                f"\n[step_17] degraded assets ({s17.get('degradedCount')}) "
                f"across {len(by_run)} failing runs:"
            )
            for entry in by_run:
                rid = entry.get("runId") or "?"
                print(
                    f"  run={rid} endTime={entry.get('endTime')} count={entry.get('count')}"
                )
                for a in (entry.get("assets") or [])[:5]:
                    print(f"    - {a}")
                if entry.get("count", 0) > 5:
                    print(f"    ... +{entry['count'] - 5} more")


if __name__ == "__main__":
    sys.exit(main())
