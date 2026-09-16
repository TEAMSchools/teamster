"""Throwaway: official idioms I may have skipped for list_runs / get_run_logs."""

from __future__ import annotations

import json
import os
from collections import Counter

import httpx

URL = "https://mcp.agent.dagster.cloud/mcp"
RUN = "140a55b5-8841-474f-bced-d1aa2cde9ffd"


def _call(client, headers, method, params, rid):
    r = client.post(
        URL,
        headers=headers,
        json={"jsonrpc": "2.0", "id": rid, "method": method, "params": params},
    )
    body = r.text
    if "\ndata: " in body or body.startswith("event:"):
        for line in body.splitlines():
            if line.startswith("data: "):
                body = line[6:]
                break
    return json.loads(body), r.headers.get("mcp-session-id")


def _tool(client, headers, name, args, rid):
    res, _ = _call(
        client, headers, "tools/call", {"name": name, "arguments": args}, rid
    )
    content = res.get("result", {}).get("content", [{}])
    txt = content[0].get("text", "") if content else ""
    if res.get("result", {}).get("isError"):
        return {"__error__": txt[:500]}
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        return {"__raw__": txt[:600]}


def test_idioms() -> None:
    headers = {
        "Authorization": f"Bearer {os.environ['DAGSTER_CLOUD_API_TOKEN']}",
        "Dagster-Cloud-Organization": "kipptaf",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    with httpx.Client(timeout=180) as client:
        _, sid = _call(
            client,
            headers,
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "probe", "version": "0"},
            },
            1,
        )
        if sid:
            headers["Mcp-Session-Id"] = sid
        client.post(
            URL,
            headers=headers,
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        )

        # 1. Do alerts carry the failure detail?
        alerts = _tool(
            client,
            headers,
            "get_run_alert_notifications",
            {"run_id": RUN, "limit": 10, "deployment_name": "prod"},
            2,
        )
        print("ALERTS>>>", json.dumps(alerts)[:2000])

        # 2. Does job_name discriminate? Sample 100 recent runs.
        runs = _tool(
            client, headers, "list_runs", {"limit": 100, "deployment_name": "prod"}, 3
        )
        names = Counter(r.get("job_name") for r in runs.get("items", []))
        print("JOB_NAME_SPREAD>>>", json.dumps(names.most_common(8)))
        print("JOB_NAME_DISTINCT>>>", len(names), "of", sum(names.values()))

        # 3. Are the asset keys recoverable from log page 1?
        logs = _tool(
            client,
            headers,
            "get_run_logs",
            {"run_id": RUN, "limit": 100, "deployment_name": "prod"},
            4,
        )
        planned = [
            e
            for e in logs.get("items", [])
            if e.get("event_type") == "ASSET_MATERIALIZATION_PLANNED"
        ]
        print("PLANNED_ON_PAGE1>>>", len(planned))
        print(
            "STEP_KEYS_ON_PAGE1>>>",
            json.dumps(
                sorted(
                    {
                        e.get("step_key")
                        for e in logs.get("items", [])
                        if e.get("step_key")
                    }
                )
            ),
        )
