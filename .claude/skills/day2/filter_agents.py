"""Filter get_cloud_agents output to errors within a time window.

Usage: python3 .claude/skills/day2/filter_agents.py <file_path> <epoch>

Reads the saved MCP tool result JSON ({"result": "<JSON string>"}), filters
agent errors to those at or after <epoch>, and prints compact JSON with only
the fields needed for triage. Agents with no in-window errors are omitted.
"""

import json
import sys


def main() -> None:
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <file_path> <epoch>", file=sys.stderr)
        sys.exit(1)

    file_path = sys.argv[1]
    epoch = float(sys.argv[2])

    with open(file_path) as f:
        data = json.load(f)

    agents = json.loads(data["result"])
    out = []
    for a in agents:
        errs = [e for e in (a.get("errors") or []) if e.get("timestamp", 0) >= epoch]
        if not errs:
            continue
        out.append(
            {
                "id": a["id"],
                "status": a["status"],
                "lastHeartbeatTime": a.get("lastHeartbeatTime"),
                "errors": [
                    {
                        "timestamp": e["timestamp"],
                        "message": e.get("error", {}).get(
                            "message", str(e.get("error", ""))
                        )[:300],
                    }
                    for e in errs
                ],
                "codeServerStates": [
                    {
                        "locationName": cs.get("locationName"),
                        "status": cs.get("status"),
                        "error": cs.get("error"),
                    }
                    for cs in (a.get("codeServerStates") or [])
                ],
                "runWorkerStates": [
                    {
                        "runId": rw.get("runId"),
                        "status": rw.get("status"),
                        "message": rw.get("message"),
                    }
                    for rw in (a.get("runWorkerStates") or [])
                ],
            }
        )
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    main()
