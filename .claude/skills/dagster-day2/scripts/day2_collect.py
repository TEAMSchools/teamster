# /// script
# requires-python = ">=3.13"
# dependencies = ["httpx>=0.27"]
# ///
"""Day-2 ops data collector — replaces Phase 1 of the /dagster-day2 skill.

Issues 15 queries against Dagster Cloud GraphQL, GCP REST APIs (Service Health,
Error Reporting, Cloud Monitoring), and `gcloud logging read`. Writes a single
artifact to .claude/scratch/day2.json keyed by step.

Authentication mirrors scripts/dagster-mcp-launch.sh: reads the 1Password
service-account token from /etc/secret-volume/.op-token, exchanges it for a
scoped Dagster Cloud API token via `op read`, then POSTs to
https://kipptaf.dagster.cloud/prod/graphql. GCP calls reuse the codespace's
`gcloud auth print-access-token`.

Usage:
    uv run scripts/day2_collect.py                  # default: 5pm ET prev biz day → now
    uv run scripts/day2_collect.py --hours 24
    uv run scripts/day2_collect.py --since 2026-04-27
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx

ORG = "kipptaf"
DEPLOYMENT = "prod"
GRAPHQL_URL = f"https://{ORG}.dagster.cloud/{DEPLOYMENT}/graphql"
OUTPUT_PATH = Path(".claude/scratch/day2.json")

# Classification rules — applied in order, first match wins.
CATEGORY_RULES: list[tuple[str, list[str]]] = [
    (
        "Preemption/Interrupt",
        [
            "DagsterExecutionInterruptedError",
            "Step execution terminated by interrupt",
            "received SIGTERM",
        ],
    ),
    ("Node OOM/eviction", ["low on resource: memory", "exit code 137", "Evicted"]),
    (
        "Scheduling failure",
        ["FailedScheduling", "Insufficient cpu", "Insufficient memory"],
    ),
    ("K8s API failure", ["DagsterK8sUnrecoverableAPIError"]),
    ("Backoff limit", ["BackoffLimitExceeded"]),
    ("Step preempt-hang", ["Exiting to prevent re-running"]),
    (
        "Network/SSH",
        [
            "paramiko.",
            "socket.timeout",
            "OSError: [Errno",
            "SSH tunnel failed",
            "port 22",
            "port 5484",
        ],
    ),
    ("Connection failure", ["grpc.", "gRPC Error code: UNAVAILABLE"]),
    ("Infra timeout", ["run worker failed", "Run timed out due to taking longer"]),
]


def classify(message: str) -> str:
    for category, signals in CATEGORY_RULES:
        if any(s in message for s in signals):
            return category
    return "Unclassified"


def get_token() -> str:
    if env := os.environ.get("DAGSTER_CLOUD_API_TOKEN"):
        return env
    op_token = Path("/etc/secret-volume/.op-token").read_text().strip()
    # trunk-ignore(bandit/B105): sentinel string written by postStart.sh after token scrub, not a credential
    if not op_token or op_token == "revoked-after-injection":
        sys.exit("OP token unavailable — rebuild Codespace to re-provision")
    # trunk-ignore(bandit/B603,bandit/B607): trusted CLI on PATH, fixed argv
    result = subprocess.run(
        ["op", "read", "op://Data Team/Dagster Cloud Agent/credential"],
        env={**os.environ, "OP_SERVICE_ACCOUNT_TOKEN": op_token},
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def compute_window(args: argparse.Namespace) -> tuple[float, str, str]:
    """Returns (epoch_start, utc_start_iso, utc_end_iso)."""
    et = ZoneInfo("America/New_York")
    now_utc = datetime.now(UTC)
    if args.hours:
        start = now_utc - timedelta(hours=args.hours)
    elif args.since:
        date = datetime.strptime(args.since, "%Y-%m-%d").date()
        start = datetime.combine(date, time(17, 0), tzinfo=et).astimezone(UTC)
    else:
        # Default: 5pm ET previous business day.
        today_et = now_utc.astimezone(et).date()
        offset = {0: 3, 6: 2}.get(today_et.weekday(), 1)  # Mon→Fri, Sun→Fri
        prev = today_et - timedelta(days=offset)
        start = datetime.combine(prev, time(17, 0), tzinfo=et).astimezone(UTC)
    return (
        start.timestamp(),
        start.isoformat().replace("+00:00", "Z"),
        now_utc.isoformat().replace("+00:00", "Z"),
    )


class GraphQL:
    def __init__(self, token: str) -> None:
        self.client = httpx.AsyncClient(
            base_url=GRAPHQL_URL,
            headers={
                "Dagster-Cloud-Api-Token": token,
                "Content-Type": "application/json",
            },
            timeout=60.0,
        )

    async def query(
        self, query: str, variables: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        resp = await self.client.post(
            "", json={"query": query, "variables": variables or {}}
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:500]}")
        body = resp.json()
        if "errors" in body:
            raise RuntimeError(f"GraphQL errors: {json.dumps(body['errors'])[:1000]}")
        return body["data"]

    async def aclose(self) -> None:
        await self.client.aclose()


# ─── Step 1: Failed runs ──────────────────────────────────────────────────

RUNS_QUERY = """
query Runs($filter: RunsFilter!, $cursor: String, $limit: Int!) {
  runsOrError(filter: $filter, cursor: $cursor, limit: $limit) {
    __typename
    ... on Runs {
      results {
        runId
        status
        jobName
        startTime
        endTime
        creationTime
        tags { key value }
      }
    }
    ... on PythonError { message }
  }
}
"""

RUN_EVENTS_QUERY = """
query RunEvents($runId: ID!) {
  logsForRun(runId: $runId, limit: 500) {
    __typename
    ... on EventConnection {
      events {
        __typename
        ... on MessageEvent { message }
        ... on RunFailureEvent { error { message className } }
        ... on ExecutionStepFailureEvent { error { message className } }
      }
    }
    ... on PythonError { message }
  }
}
"""


async def paginate_runs(
    gql: GraphQL, status: str, after_epoch: float, limit: int = 100
) -> list[dict]:
    runs: list[dict] = []
    cursor: str | None = None
    while True:
        data = await gql.query(
            RUNS_QUERY,
            {
                "filter": {"statuses": [status], "createdAfter": after_epoch},
                "cursor": cursor,
                "limit": limit,
            },
        )
        results = data["runsOrError"]["results"]
        runs.extend(results)
        if len(results) < limit:
            break
        cursor = results[-1]["runId"]
    # Dedupe by runId (boundary overlap).
    seen: set[str] = set()
    return [r for r in runs if not (r["runId"] in seen or seen.add(r["runId"]))]


ENGINE_KEYWORDS = (
    "terminat",
    "SIGTERM",
    "preempt",
    "BackoffLimit",
    "OOM",
    "Evicted",
    "interrupt",
    "Deleting Kubernetes job",
    "Exiting to prevent re-running",
)


async def fetch_failure_detail(gql: GraphQL, run: dict) -> dict:
    data = await gql.query(RUN_EVENTS_QUERY, {"runId": run["runId"]})
    conn = data.get("logsForRun") or {}
    events = conn.get("events") or []
    run_failure_msg = ""
    error_class = ""
    error_detail = ""
    engine_match = ""
    for ev in events:
        t = ev.get("__typename")
        msg = ev.get("message") or ""
        err = ev.get("error") or {}
        if t == "RunFailureEvent":
            run_failure_msg = msg
            error_class = (err.get("className") or "") or error_class
        elif t == "ExecutionStepFailureEvent":
            error_class = error_class or (err.get("className") or "")
            error_detail = error_detail or (err.get("message") or "")
        elif (
            t == "EngineEvent"
            and not engine_match
            and any(k in msg for k in ENGINE_KEYWORDS)
        ):
            engine_match = msg
    tags = {t["key"]: t["value"] for t in run.get("tags", [])}
    haystack = " ".join([run_failure_msg, error_class, error_detail, engine_match])
    category = classify(haystack)
    if category == "Unclassified" and error_detail:
        # Step-level Python exception with no infra signals → user code error.
        category = "Code error"
    return {
        "runId": run["runId"],
        "jobName": run.get("jobName"),
        "codeLocation": tags.get("dagster/code_location"),
        "startTime": run.get("startTime"),
        "endTime": run.get("endTime"),
        "willRetry": tags.get("dagster/will_retry"),
        "autoRetryRunId": tags.get("dagster/auto_retry_run_id"),
        "runFailureMessage": run_failure_msg,
        "errorClass": error_class,
        "errorDetail": error_detail,
        "engineEventMatch": engine_match,
        "category": category,
    }


async def step_01_failed_runs(gql: GraphQL, after_epoch: float) -> dict:
    failures, successes, canceled = await asyncio.gather(
        paginate_runs(gql, "FAILURE", after_epoch),
        paginate_runs(gql, "SUCCESS", after_epoch),
        paginate_runs(gql, "CANCELED", after_epoch),
    )
    failure_details = await asyncio.gather(
        *(fetch_failure_detail(gql, r) for r in failures)
    )
    return {
        "failureCount": len(failures),
        "successCount": len(successes),
        "canceledCount": len(canceled),
        "failures": failure_details,
        "successRunIds": [r["runId"] for r in successes],
    }


# ─── Step 7: Agent health ─────────────────────────────────────────────────

AGENTS_QUERY = """
query Agents {
  agents {
    id
    status
    lastHeartbeatTime
    errors { error { message } timestamp }
  }
}
"""


async def step_07_agents(gql: GraphQL, after_epoch: float) -> dict:
    data = await gql.query(AGENTS_QUERY)
    agents = []
    for a in data["agents"]:
        errs = [
            {
                "timestamp": e["timestamp"],
                "message": (e["error"]["message"] or "")[:300],
            }
            for e in (a.get("errors") or [])
            if e["timestamp"] >= after_epoch
        ]
        agents.append(
            {
                "id": a["id"],
                "status": a["status"],
                "lastHeartbeatTime": a["lastHeartbeatTime"],
                "errors": errs,
            }
        )
    return {"agents": agents, "agentCount": len(agents)}


# ─── Step 9: Daemon health ────────────────────────────────────────────────

DAEMONS_QUERY = """
query DaemonHealth {
  instance {
    daemonHealth {
      allDaemonStatuses { daemonType healthy }
    }
  }
}
"""


async def step_09_daemons(gql: GraphQL) -> dict:
    data = await gql.query(DAEMONS_QUERY)
    daemons = data["instance"]["daemonHealth"]["allDaemonStatuses"]
    return {"daemons": daemons, "allHealthy": all(d["healthy"] for d in daemons)}


# ─── Step 14: Queued/stuck runs ───────────────────────────────────────────


async def step_14_queued(gql: GraphQL, after_epoch: float) -> dict:
    now = datetime.now(UTC).timestamp()
    runs: list[dict] = []
    for status in ("QUEUED", "NOT_STARTED", "MANAGED", "STARTING"):
        runs.extend(await paginate_runs(gql, status, after_epoch, limit=20))
    out = []
    for r in runs:
        age = now - (r.get("creationTime") or now)
        out.append(
            {
                "runId": r["runId"],
                "status": r["status"],
                "jobName": r.get("jobName"),
                "creationTime": r.get("creationTime"),
                "ageSeconds": int(age),
                "stuck": age > 900,
            }
        )
    return {"runs": out, "stuckCount": sum(1 for r in out if r["stuck"])}


# ─── Step 15: Backfills ───────────────────────────────────────────────────

BACKFILLS_QUERY = """
query Backfills($status: BulkActionStatus!, $limit: Int!) {
  partitionBackfillsOrError(status: $status, limit: $limit) {
    __typename
    ... on PartitionBackfills {
      results { id status numPartitions timestamp error { message } }
    }
    ... on PythonError { message }
  }
}
"""


async def step_15_backfills(gql: GraphQL, after_epoch: float) -> dict:
    out: dict[str, list] = {}
    for status in ("REQUESTED", "FAILED"):
        data = await gql.query(BACKFILLS_QUERY, {"status": status, "limit": 10})
        results = data["partitionBackfillsOrError"].get("results", [])
        out[status.lower()] = [
            r for r in results if (r.get("timestamp") or 0) >= after_epoch
        ]
    return out


# ─── Step 16: Failed asset checks ─────────────────────────────────────────

ASSET_CHECKS_DISCOVERY_QUERY = """
query AssetChecksDiscovery {
  assetNodes {
    assetChecksOrError {
      __typename
      ... on AssetChecks {
        checks { name assetKey { path } }
      }
    }
  }
}
"""

ASSET_CHECK_LATEST_QUERY = """
query AssetCheckLatest($assetKey: AssetKeyInput!, $checkName: String!) {
  assetCheckExecutions(
    assetKey: $assetKey
    checkName: $checkName
    limit: 1
  ) {
    runId
    status
    timestamp
    evaluation {
      severity
      description
      metadataEntries {
        label
        ... on TextMetadataEntry { text }
        ... on JsonMetadataEntry { jsonString }
        ... on IntMetadataEntry { intValue }
        ... on FloatMetadataEntry { floatValue }
      }
    }
  }
}
"""


def _summarize_check_metadata(entries: list[dict] | None) -> str:
    """Squash metadata entries into a short string for the report."""
    if not entries:
        return ""
    parts: list[str] = []
    for m in entries:
        label = m.get("label") or ""
        val = (
            m.get("text")
            or m.get("jsonString")
            or m.get("intValue")
            or m.get("floatValue")
        )
        if val is None or val == "":
            continue
        parts.append(f"{label}={str(val)[:200]}")
    return "; ".join(parts)[:600]


async def step_16_asset_checks(gql: GraphQL, after_epoch: float) -> dict:
    """Surface asset checks whose latest execution is FAILED.

    Buckets by severity (ERROR vs WARN) and timing (inWindow vs stale).
    `avro_schema_valid` checks fall under WARN severity by design.
    """
    discovery = await gql.query(ASSET_CHECKS_DISCOVERY_QUERY)
    seen: set[tuple[tuple[str, ...], str]] = set()
    pairs: list[tuple[tuple[str, ...], str]] = []
    for node in discovery.get("assetNodes") or []:
        ck = node.get("assetChecksOrError") or {}
        if ck.get("__typename") != "AssetChecks":
            continue
        for c in ck.get("checks") or []:
            key = (tuple(c["assetKey"]["path"]), c["name"])
            if key in seen:
                continue
            seen.add(key)
            pairs.append(key)

    sem = asyncio.Semaphore(20)

    async def fetch(asset_path: tuple[str, ...], check_name: str) -> dict | None:
        async with sem:
            d = await gql.query(
                ASSET_CHECK_LATEST_QUERY,
                {"assetKey": {"path": list(asset_path)}, "checkName": check_name},
            )
        execs = d.get("assetCheckExecutions") or []
        if not execs:
            return None
        ex = execs[0]
        status = ex.get("status")
        if status not in ("FAILED", "EXECUTION_FAILED"):
            return None
        ev = ex.get("evaluation") or {}
        return {
            "asset": "/".join(asset_path),
            "check": check_name,
            "status": status,
            "severity": ev.get("severity") or "UNKNOWN",
            "timestamp": ex.get("timestamp"),
            "runId": ex.get("runId"),
            "description": ev.get("description"),
            "metadata": _summarize_check_metadata(ev.get("metadataEntries")),
        }

    results = await asyncio.gather(*(fetch(p, n) for p, n in pairs))
    buckets: dict[str, list[dict]] = {
        "inWindow_error": [],
        "inWindow_warn": [],
        "stale_error": [],
        "stale_warn": [],
    }
    for r in results:
        if r is None:
            continue
        in_window = (r["timestamp"] or 0) >= after_epoch
        # EXECUTION_FAILED has no evaluation/severity — bucket as error so it
        # surfaces alongside check-evaluation ERRORs rather than getting buried
        # in WARN noise. WARN-severity FAILED is the documented avro_schema_valid
        # path; anything else (including UNKNOWN) is treated as error.
        is_warn = r["status"] == "FAILED" and r["severity"] == "WARN"
        bucket = (
            f"{'inWindow' if in_window else 'stale'}_{'warn' if is_warn else 'error'}"
        )
        buckets[bucket].append(r)
    return {
        "totalChecks": len(pairs),
        "failedCount": sum(len(b) for b in buckets.values()),
        **buckets,
    }


# ─── Step 17: Degraded assets (latestRun.status = FAILURE) ────────────────

ASSETS_LATEST_QUERY = """
query AssetsLatest($keys: [AssetKeyInput!]!) {
  assetsLatestInfo(assetKeys: $keys) {
    assetKey { path }
    latestRun { runId status endTime }
  }
}
"""


async def step_17_degraded_assets(gql: GraphQL, _after_epoch: float) -> dict:
    """Assets whose latest run failed.

    Caveat: dbt failures are run-level, not step-level, so an asset can be
    flagged here even though its own materialization step succeeded mid-run.
    Use this list as a starting point and verify per-asset.
    """
    nodes = (await gql.query(ASSETS_QUERY)).get("assetNodes") or []
    keys = [{"path": n["assetKey"]["path"]} for n in nodes]

    degraded: list[dict] = []
    chunk = 200
    for i in range(0, len(keys), chunk):
        batch = keys[i : i + chunk]
        data = await gql.query(ASSETS_LATEST_QUERY, {"keys": batch})
        for info in data.get("assetsLatestInfo") or []:
            latest = info.get("latestRun") or {}
            if latest.get("status") != "FAILURE":
                continue
            degraded.append(
                {
                    "asset": "/".join(info["assetKey"]["path"]),
                    "latestRunId": latest.get("runId"),
                    "latestRunEndTime": latest.get("endTime"),
                }
            )

    by_run: dict[str, list[str]] = {}
    for d in degraded:
        by_run.setdefault(d["latestRunId"] or "", []).append(d["asset"])
    return {
        "totalAssets": len(keys),
        "degradedCount": len(degraded),
        "degraded": degraded,
        "byRun": [
            {
                "runId": rid,
                "endTime": next(
                    (
                        d["latestRunEndTime"]
                        for d in degraded
                        if d["latestRunId"] == rid
                    ),
                    None,
                ),
                "count": len(assets),
                "assets": assets,
            }
            for rid, assets in sorted(by_run.items(), key=lambda x: -len(x[1]))
        ],
    }


# ─── Step 2: Retry verification ───────────────────────────────────────────

RUNS_BY_ID_QUERY = """
query RunsById($runIds: [String!]!) {
  runsOrError(filter: {runIds: $runIds}, limit: 100) {
    ... on Runs { results { runId status startTime endTime } }
  }
}
"""

TERMINAL_EVENT_QUERY = """
query Terminal($runId: ID!) {
  logsForRun(runId: $runId, limit: 500) {
    ... on EventConnection {
      events { __typename ... on MessageEvent { message } }
    }
  }
}
"""


async def _terminal_status(gql: GraphQL, run_id: str) -> str:
    data = await gql.query(TERMINAL_EVENT_QUERY, {"runId": run_id})
    events = (data.get("logsForRun") or {}).get("events") or []
    for ev in reversed(events):
        if ev["__typename"] == "RunSuccessEvent":
            return "SUCCESS"
        if ev["__typename"] == "RunFailureEvent":
            return "FAILURE"
    return "UNKNOWN"


async def step_02_retries(gql: GraphQL, step_01: dict) -> dict:
    pairs = [
        (f["runId"], f["autoRetryRunId"])
        for f in step_01.get("failures", [])
        if f.get("autoRetryRunId")
    ]
    if not pairs:
        return {"retries": []}
    retry_ids = [c for _, c in pairs]
    data = await gql.query(RUNS_BY_ID_QUERY, {"runIds": retry_ids})
    by_id = {r["runId"]: r for r in data["runsOrError"]["results"]}
    statuses = await asyncio.gather(*(_terminal_status(gql, c) for _, c in pairs))
    return {
        "retries": [
            {
                "parentRunId": p,
                "retryRunId": c,
                "retryStatus": s
                if s != "UNKNOWN"
                else by_id.get(c, {}).get("status", "UNKNOWN"),
            }
            for (p, c), s in zip(pairs, statuses, strict=True)
        ],
    }


# ─── Workspace (shared by 3, 5, 6) ────────────────────────────────────────

WORKSPACE_QUERY = """
query Workspace {
  workspaceOrError {
    ... on Workspace {
      locationEntries {
        name
        loadStatus
        locationOrLoadError {
          __typename
          ... on RepositoryLocation {
            repositories {
              name
              sensors { name sensorType sensorState { status } }
              schedules { name scheduleState { status } }
            }
          }
          ... on PythonError { message }
        }
      }
    }
  }
}
"""


async def fetch_workspace(gql: GraphQL) -> list[dict]:
    data = await gql.query(WORKSPACE_QUERY)
    return data["workspaceOrError"]["locationEntries"]


# ─── Step 3: Sensor tick failures ─────────────────────────────────────────

TICKS_QUERY = """
query Ticks($selector: InstigationSelector!, $afterTs: Float, $statuses: [InstigationTickStatus!]) {
  instigationStateOrError(instigationSelector: $selector) {
    ... on InstigationState {
      ticks(afterTimestamp: $afterTs, statuses: $statuses, limit: 100) {
        id timestamp status error { message errorChain { error { message } } }
      }
    }
    ... on PythonError { message }
  }
}
"""


def _first_chain_message(err: dict) -> str:
    """Return the first errorChain entry's message — the actual root cause.

    The top-level `error.message` on a sensor/schedule tick is a generic
    `SensorExecutionError` / `ScheduleExecutionError` boundary message. The
    underlying cause (e.g. `oracledb DPY-4024 call timeout`) lives in
    `error.errorChain[0].error.message`.
    """
    chain = err.get("errorChain") or []
    if not chain:
        return ""
    return (chain[0].get("error") or {}).get("message") or ""


async def _ticks(
    gql: GraphQL, loc: str, repo: str, name: str, after_epoch: float
) -> list[dict]:
    data = await gql.query(
        TICKS_QUERY,
        {
            "selector": {
                "repositoryLocationName": loc,
                "repositoryName": repo,
                "name": name,
            },
            "afterTs": after_epoch,
            "statuses": ["FAILURE"],
        },
    )
    state = data.get("instigationStateOrError") or {}
    return state.get("ticks") or []


async def step_03_sensor_ticks(
    gql: GraphQL, after_epoch: float, locations: list[dict]
) -> dict:
    pairs: list[tuple[str, str, str]] = []
    for loc in locations:
        if loc["loadStatus"] != "LOADED":
            continue
        body = loc.get("locationOrLoadError") or {}
        if body.get("__typename") != "RepositoryLocation":
            continue
        for repo in body.get("repositories", []):
            for s in repo.get("sensors", []):
                if (s.get("sensorState") or {}).get("status") == "RUNNING":
                    pairs.append((loc["name"], repo["name"], s["name"]))

    tick_lists = await asyncio.gather(
        *(_ticks(gql, lo, r, n, after_epoch) for lo, r, n in pairs)
    )

    out: dict[str, dict] = {}
    for (loc, _repo, name), ticks in zip(pairs, tick_lists, strict=True):
        if not ticks:
            continue
        out.setdefault(loc, {})[name] = {
            "failureCount": len(ticks),
            "ticks": [
                {
                    "tickId": t.get("id"),
                    "timestamp": t.get("timestamp"),
                    "error": ((t.get("error") or {}).get("message") or "")[:300],
                    "errorChainTop": _first_chain_message(t.get("error") or {})[:300],
                }
                for t in ticks
            ],
        }
    return out


# ─── Step 5: Location load failures ───────────────────────────────────────

LOCATION_HISTORY_QUERY = """
query LocHistory($name: String!) {
  locationStatusesOrError {
    ... on WorkspaceLocationStatusEntries {
      entries { name loadStatus updateTimestamp permissions { permission } }
    }
  }
}
"""


async def step_05_load_failures(gql: GraphQL, locations: list[dict]) -> dict:
    failures = []
    for loc in locations:
        if loc["loadStatus"] == "LOADED":
            continue
        body = loc.get("locationOrLoadError") or {}
        err = ""
        if body.get("__typename") == "PythonError":
            err = (body.get("message") or "")[:500]
        failures.append(
            {"locationName": loc["name"], "loadStatus": loc["loadStatus"], "error": err}
        )
    return {"loadFailures": failures}


# ─── Step 6: Schedule tick failures ───────────────────────────────────────


async def step_06_schedule_ticks(
    gql: GraphQL, after_epoch: float, locations: list[dict]
) -> dict:
    pairs: list[tuple[str, str, str]] = []
    for loc in locations:
        if loc["loadStatus"] != "LOADED":
            continue
        body = loc.get("locationOrLoadError") or {}
        if body.get("__typename") != "RepositoryLocation":
            continue
        for repo in body.get("repositories", []):
            for s in repo.get("schedules", []):
                if (s.get("scheduleState") or {}).get("status") == "RUNNING":
                    pairs.append((loc["name"], repo["name"], s["name"]))

    tick_lists = await asyncio.gather(
        *(_ticks(gql, lo, r, n, after_epoch) for lo, r, n in pairs)
    )
    out: dict[str, list] = {}
    for (loc, _repo, name), ticks in zip(pairs, tick_lists, strict=True):
        if not ticks:
            continue
        out[f"{loc}/{name}"] = [
            {
                "tickId": t.get("id"),
                "timestamp": t.get("timestamp"),
                "error": ((t.get("error") or {}).get("message") or "")[:300],
                "errorChainTop": _first_chain_message(t.get("error") or {})[:300],
            }
            for t in ticks
        ]
    return {"scheduleTickFailures": out}


# ─── Step 4: Freshness ────────────────────────────────────────────────────

ASSETS_QUERY = """
query AssetsWithFreshness {
  assetNodes {
    assetKey { path }
    freshnessPolicy { __typename }
  }
}
"""

ASSET_HEALTH_QUERY = """
query AssetHealth($keys: [AssetKeyInput!]!) {
  assetsOrError(assetKeys: $keys) {
    ... on AssetConnection {
      nodes {
        key { path }
        latestMaterializationByPartition(partitions: null) { timestamp }
      }
    }
  }
}
"""


async def step_04_freshness(gql: GraphQL, _after_epoch: float) -> dict:
    data = await gql.query(ASSETS_QUERY)
    nodes = data.get("assetNodes") or []
    flagged = [n for n in nodes if n.get("freshnessPolicy")]
    return {"flaggedAssets": flagged, "policyCount": len(flagged)}


# ─── GCP helpers ──────────────────────────────────────────────────────────

PROJECT_ID = "teamster-332318"


def gcloud_logging_read(
    query: str, utc_start: str, utc_end: str, limit: int = 100
) -> list[dict]:
    full = f'({query}) AND timestamp >= "{utc_start}" AND timestamp <= "{utc_end}"'
    # trunk-ignore(bandit/B603,bandit/B607): trusted CLI on PATH, fixed argv shape
    result = subprocess.run(
        [
            "gcloud",
            "logging",
            "read",
            full,
            f"--project={PROJECT_ID}",
            f"--limit={limit}",
            "--format=json",
            "--order=desc",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout or "[]")


def gcloud_token() -> str:
    # trunk-ignore(bandit/B603,bandit/B607): trusted CLI on PATH, fixed argv
    return subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


# ─── Step 8: Agent pod churn ──────────────────────────────────────────────


def step_08_agent_pod_churn(utc_start: str, utc_end: str, agents: dict) -> dict:
    if all(
        a["status"] == "RUNNING" and not a["errors"] for a in agents.get("agents", [])
    ):
        return {"events": [], "skipped": True, "reason": "all agents healthy"}
    query = (
        'resource.type="k8s_cluster" '
        'AND log_name=~"logs/events" '
        'AND resource.labels.cluster_name="autopilot-cluster-dagster-hybrid-1" '
        'AND jsonPayload.involvedObject.namespace="dagster-cloud" '
        'AND jsonPayload.involvedObject.name:"user-cloud-dagster-cloud-agent-agent" '
        'AND jsonPayload.reason="SuccessfulCreate"'
    )
    entries = gcloud_logging_read(query, utc_start, utc_end)
    return {
        "events": [
            {
                "timestamp": e["timestamp"],
                "podName": e.get("jsonPayload", {})
                .get("involvedObject", {})
                .get("name"),
                "message": e.get("jsonPayload", {}).get("message"),
            }
            for e in entries
        ],
    }


# ─── Step 10: GKE critical events ─────────────────────────────────────────


DAGSTER_RUN_POD_RE = re.compile(
    r"^dagster-run-([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})-"
)


def _attribute_pod_event(
    pod_name: str | None, failed_ids: set[str], success_ids: set[str]
) -> tuple[str | None, str]:
    if not pod_name:
        return None, "UNKNOWN"
    m = DAGSTER_RUN_POD_RE.match(pod_name)
    if not m:
        return None, "UNKNOWN"
    run_id = m.group(1)
    if run_id in success_ids:
        return run_id, "SUCCESS"
    if run_id in failed_ids:
        return run_id, "FAILURE"
    return run_id, "UNKNOWN"


def step_10_gke_events(utc_start: str, utc_end: str, step_01: dict) -> dict:
    cluster_query = (
        'resource.type="k8s_cluster" '
        'AND log_name=~"logs/events" '
        'AND resource.labels.cluster_name="autopilot-cluster-dagster-hybrid-1" '
        'AND jsonPayload.involvedObject.namespace="dagster-cloud" '
        'AND jsonPayload.reason=("ScaleUpFailed" OR "BackoffLimitExceeded" '
        'OR "NodeNotReady" OR "FailedCreate" OR "FailedScheduling")'
    )
    pod_query = (
        'resource.type="k8s_pod" '
        'AND resource.labels.cluster_name="autopilot-cluster-dagster-hybrid-1" '
        'AND resource.labels.namespace_name="dagster-cloud" '
        'AND jsonPayload.reason=("Preempted" OR "Evicted" OR "OOMKilling" '
        'OR "Preempting" OR "BackOff")'
    )
    cluster = gcloud_logging_read(cluster_query, utc_start, utc_end)
    pod = gcloud_logging_read(pod_query, utc_start, utc_end)
    failed_ids = {f.get("runId") for f in step_01.get("failures", []) if f.get("runId")}
    success_ids = set(step_01.get("successRunIds", []) or [])
    pod_events = []
    for e in pod:
        pod_name = e.get("resource", {}).get("labels", {}).get("pod_name")
        run_id, run_status = _attribute_pod_event(pod_name, failed_ids, success_ids)
        pod_events.append(
            {
                "timestamp": e["timestamp"],
                "podName": pod_name,
                "reason": e.get("jsonPayload", {}).get("reason"),
                "message": e.get("jsonPayload", {}).get("message"),
                "runId": run_id,
                "runStatus": run_status,
            }
        )
    return {
        "clusterEvents": [
            {
                "timestamp": e["timestamp"],
                "reason": e.get("jsonPayload", {}).get("reason"),
                "object": e.get("jsonPayload", {})
                .get("involvedObject", {})
                .get("name"),
                "message": e.get("jsonPayload", {}).get("message"),
            }
            for e in cluster
        ],
        "podEvents": pod_events,
    }


# ─── Step 11: Service-health alerts ───────────────────────────────────────


def step_11_alerts(utc_start: str) -> dict:
    """GCP Service Health events: open at any time, or starting in window."""
    token = gcloud_token()
    url = f"https://servicehealth.googleapis.com/v1/projects/{PROJECT_ID}/locations/global/events"
    resp = httpx.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        params={"pageSize": 50},
        timeout=30.0,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"service-health HTTP {resp.status_code}: {resp.text[:300]}")
    events = resp.json().get("events", [])
    out = []
    for e in events:
        in_window = (e.get("startTime") or "") >= utc_start
        if not (in_window or e.get("state") == "ACTIVE"):
            continue
        impacts = e.get("eventImpacts") or []
        products = sorted(
            {
                name
                for i in impacts
                if (name := (i.get("product") or {}).get("productName"))
            }
        )
        locations = sorted(
            {
                name
                for i in impacts
                if (name := (i.get("location") or {}).get("locationName"))
            }
        )
        out.append(
            {
                "name": e.get("name"),
                "state": e.get("state"),
                "title": e.get("title"),
                "openTime": e.get("startTime"),
                "closeTime": e.get("endTime"),
                "category": e.get("category"),
                "relevance": e.get("relevance"),
                "impactedProducts": products,
                "impactedLocations": locations,
            }
        )
    return {"alerts": out}


# ─── Step 12: Error groups ────────────────────────────────────────────────


EXCEPTION_LINE_RE = re.compile(
    r"^([A-Za-z_][\w\.]*(?:Error|Exception|Interrupt|Warning))(?::|$)"
)
SIGTERM_EXC_CLASSES = {
    "DagsterExecutionInterruptedError",
    "KeyboardInterrupt",
    "SystemExit",
}


def _resolve_exception_line(pod_name: str, last_seen: str) -> str | None:
    """Find the bottom-of-traceback exception class on the affected pod ±2s."""
    if not pod_name or not last_seen:
        return None
    try:
        ts = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
    except ValueError:
        return None
    start = (ts - timedelta(seconds=2)).isoformat().replace("+00:00", "Z")
    end = (ts + timedelta(seconds=2)).isoformat().replace("+00:00", "Z")
    try:
        entries = gcloud_logging_read(
            f'resource.labels.pod_name="{pod_name}" severity>=ERROR',
            start,
            end,
            limit=100,
        )
    except subprocess.CalledProcessError:
        return None
    candidates: list[str] = []
    for e in entries:
        text = e.get("textPayload") or e.get("jsonPayload", {}).get("message") or ""
        for line in text.splitlines():
            stripped = line.strip()
            if EXCEPTION_LINE_RE.match(stripped):
                candidates.append(stripped[:300])
    return candidates[-1] if candidates else None


def _correlate_pod_event(
    pod_names: list[str], last_seen: str, pod_events: list[dict]
) -> dict | None:
    """Find a Preempted/Evicted/OOMKilling event on the same pod within ±10s."""
    if not pod_names or not last_seen or not pod_events:
        return None
    try:
        ts = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
    except ValueError:
        return None
    target_pods = set(pod_names)
    benign_reasons = {"Preempted", "Evicted", "OOMKilling"}
    for ev in pod_events:
        if ev.get("podName") not in target_pods:
            continue
        if ev.get("reason") not in benign_reasons:
            continue
        try:
            ev_ts = datetime.fromisoformat(ev["timestamp"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        if abs((ev_ts - ts).total_seconds()) <= 10:
            return {
                "reason": ev.get("reason"),
                "timestamp": ev.get("timestamp"),
                "podName": ev.get("podName"),
            }
    return None


def step_12_error_groups(utc_start: str, step_10: dict) -> dict:
    token = gcloud_token()
    url = f"https://clouderrorreporting.googleapis.com/v1beta1/projects/{PROJECT_ID}/groupStats"
    params = {
        "timeRange.period": "PERIOD_30_DAYS",
        "order": "LAST_SEEN_DESC",
        "pageSize": 25,
    }
    out: list[dict] = []
    page_token: str | None = None
    while True:
        if page_token:
            params["pageToken"] = page_token
        resp = httpx.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=30.0,
        )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"error-reporting HTTP {resp.status_code}: {resp.text[:300]}"
            )
        data = resp.json()
        for g in data.get("errorGroupStats", []):
            affected = [
                {
                    "service": (s.get("service") or ""),
                    "version": (s.get("version") or ""),
                }
                for s in (g.get("affectedServices") or [])
            ]
            out.append(
                {
                    "groupId": g.get("group", {}).get("groupId"),
                    "count": g.get("count"),
                    "firstSeenTime": g.get("firstSeenTime"),
                    "lastSeenTime": g.get("lastSeenTime"),
                    "resolutionStatus": g.get("group", {}).get(
                        "resolutionStatus", "OPEN"
                    ),
                    "exception": (g.get("representative", {}).get("message") or "")[
                        :300
                    ],
                    "affectedServices": affected,
                }
            )
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    pod_events = step_10.get("podEvents", []) or []
    events_url = f"https://clouderrorreporting.googleapis.com/v1beta1/projects/{PROJECT_ID}/events"
    for g in out:
        if g.get("resolutionStatus") != "OPEN":
            continue
        ev_resp = httpx.get(
            events_url,
            headers={"Authorization": f"Bearer {token}"},
            params={
                "groupId": g["groupId"],
                "pageSize": 1,
                "timeRange.period": "PERIOD_30_DAYS",
            },
            timeout=30.0,
        )
        recent_pod = ""
        recent_ts = g.get("lastSeenTime", "")
        if ev_resp.status_code < 400:
            events = ev_resp.json().get("errorEvents", []) or []
            if events:
                recent_pod = (events[0].get("serviceContext") or {}).get(
                    "version"
                ) or ""
                recent_ts = events[0].get("eventTime") or recent_ts
        g["mostRecentPod"] = recent_pod
        g["mostRecentEventTime"] = recent_ts
        g["exceptionLine"] = _resolve_exception_line(recent_pod, recent_ts)
        g["correlatedPodEvent"] = _correlate_pod_event(
            [recent_pod] if recent_pod else [], recent_ts, pod_events
        )
        exc = g.get("exceptionLine") or ""
        exc_class = exc.split(":")[0].split(".")[-1] if exc else ""
        if exc_class in SIGTERM_EXC_CLASSES:
            g["category"] = "sigterm_during_import"
        elif g["correlatedPodEvent"]:
            g["category"] = "preemption_artifact"
        else:
            g["category"] = "unclassified"
    in_window = [
        g
        for g in out
        if (g.get("lastSeenTime") or "") >= utc_start
        and g.get("resolutionStatus") == "OPEN"
    ]
    stale_open = [
        g
        for g in out
        if (g.get("lastSeenTime") or "") < utc_start
        and g.get("resolutionStatus") == "OPEN"
    ]
    return {"groups": out, "buckets": {"inWindow": in_window, "staleOpen": stale_open}}


# ─── Step 13: OOM drill-down ──────────────────────────────────────────────


def step_13_oom_metrics(step_01: dict, _utc_end: str) -> dict:
    oom_runs = [
        f
        for f in step_01.get("failures", [])
        if f.get("category") == "Node OOM/eviction"
    ]
    if not oom_runs:
        return {"skipped": True, "reason": "no OOM/eviction failures"}
    token = gcloud_token()
    url = f"https://monitoring.googleapis.com/v3/projects/{PROJECT_ID}/timeSeries"
    out = []
    for run in oom_runs:
        start_iso = (
            datetime.fromtimestamp(run["startTime"] - 300, tz=UTC)
            .isoformat()
            .replace("+00:00", "Z")
        )
        end_iso = (
            datetime.fromtimestamp(
                (run.get("endTime") or run["startTime"]) + 300, tz=UTC
            )
            .isoformat()
            .replace("+00:00", "Z")
        )
        params = {
            "filter": f'metric.type="kubernetes.io/container/memory/used_bytes" AND resource.labels.pod_name=starts_with("dagster-run-{run["runId"]}")',
            "interval.startTime": start_iso,
            "interval.endTime": end_iso,
            "aggregation.alignmentPeriod": "60s",
            "aggregation.perSeriesAligner": "ALIGN_MAX",
        }
        resp = httpx.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=30.0,
        )
        if resp.status_code >= 400:
            out.append({"runId": run["runId"], "error": f"HTTP {resp.status_code}"})
            continue
        series = resp.json().get("timeSeries", [])
        peaks = [
            max(
                (
                    float(
                        p["value"].get("int64Value")
                        or p["value"].get("doubleValue")
                        or 0
                    )
                    for p in s.get("points", [])
                ),
                default=0,
            )
            for s in series
        ]
        out.append({"runId": run["runId"], "peakBytes": max(peaks, default=0)})
    return {"oomRuns": out}


# ─── Driver ───────────────────────────────────────────────────────────────


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=int)
    parser.add_argument("--since", help="YYYY-MM-DD; window starts 5pm ET that date")
    args = parser.parse_args()

    epoch, utc_start, utc_end = compute_window(args)
    print(f"Window: {utc_start} → {utc_end} (epoch {epoch:.0f})", file=sys.stderr)

    artifact: dict[str, Any] = {
        "window": {"epoch": epoch, "utc_start": utc_start, "utc_end": utc_end},
    }

    async def run_step(name: str, coro: Any) -> None:
        try:
            artifact[name] = await coro
            print(f"  {name}: ok", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001
            artifact[name] = {"error": f"{type(exc).__name__}: {exc}"}
            print(f"  {name}: FAILED — {exc}", file=sys.stderr)

    def run_sync(name: str, fn: Any, *args: Any) -> None:
        try:
            artifact[name] = fn(*args)
            print(f"  {name}: ok", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001
            artifact[name] = {"error": f"{type(exc).__name__}: {exc}"}
            print(f"  {name}: FAILED — {exc}", file=sys.stderr)

    gql = GraphQL(get_token())
    try:
        # Phase A — independent Dagster GraphQL queries in parallel.
        await asyncio.gather(
            run_step("step_01_failed_runs", step_01_failed_runs(gql, epoch)),
            run_step("step_07_agents", step_07_agents(gql, epoch)),
            run_step("step_09_daemons", step_09_daemons(gql)),
            run_step("step_14_queued_runs", step_14_queued(gql, epoch)),
            run_step("step_15_backfills", step_15_backfills(gql, epoch)),
            run_step("step_04_freshness", step_04_freshness(gql, epoch)),
            run_step("step_16_asset_checks", step_16_asset_checks(gql, epoch)),
            run_step("step_17_degraded_assets", step_17_degraded_assets(gql, epoch)),
        )
        # Workspace once for steps 3, 5, 6.
        try:
            locations = await fetch_workspace(gql)
        except Exception as exc:  # noqa: BLE001
            print(f"  workspace fetch FAILED — {exc}", file=sys.stderr)
            locations = []
        # Phase B — depends on step 1 (retries) + workspace (3, 5, 6).
        s1 = artifact.get("step_01_failed_runs", {})
        await asyncio.gather(
            run_step(
                "step_02_retries", step_02_retries(gql, s1 if "error" not in s1 else {})
            ),
            run_step(
                "step_03_sensor_ticks", step_03_sensor_ticks(gql, epoch, locations)
            ),
            run_step("step_05_load_failures", step_05_load_failures(gql, locations)),
            run_step(
                "step_06_schedule_ticks", step_06_schedule_ticks(gql, epoch, locations)
            ),
        )
    finally:
        await gql.aclose()

    # GCP-side steps (sync, gcloud subprocess + REST).
    s7 = artifact.get("step_07_agents", {})
    run_sync(
        "step_08_agent_pod_churn",
        step_08_agent_pod_churn,
        utc_start,
        utc_end,
        s7 if "error" not in s7 else {"agents": []},
    )
    run_sync(
        "step_10_gke_events",
        step_10_gke_events,
        utc_start,
        utc_end,
        s1 if "error" not in s1 else {"failures": [], "successRunIds": []},
    )
    run_sync("step_11_alerts", step_11_alerts, utc_start)
    s10 = artifact.get("step_10_gke_events", {})
    run_sync(
        "step_12_error_groups",
        step_12_error_groups,
        utc_start,
        s10 if "error" not in s10 else {"podEvents": []},
    )
    run_sync(
        "step_13_oom_metrics",
        step_13_oom_metrics,
        s1 if "error" not in s1 else {"failures": []},
        utc_end,
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(artifact, indent=2, default=str))
    print(f"Wrote {OUTPUT_PATH}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
