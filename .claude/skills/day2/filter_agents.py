"""Filter get_cloud_agents output for day-2 triage.

Usage: python3 .claude/skills/day2/filter_agents.py <file_path> <epoch>

Reads the saved MCP tool result JSON ({"result": "<JSON string>"}), filters
agent errors to those at or after <epoch>, and prints compact JSON.  All agents
are always returned (not just those with in-window errors) so Phase 2 can
assess fleet topology.
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
        out.append(
            {
                "id": a["id"],
                "status": a["status"],
                "lastHeartbeatTime": a.get("lastHeartbeatTime"),
                "hasInWindowErrors": len(errs) > 0,
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
