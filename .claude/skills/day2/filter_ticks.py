"""Filter get_tick_history output to ticks within a time window.

Usage: python3 .claude/skills/day2/filter_ticks.py <file_path> <epoch>

Reads the saved MCP tool result JSON, filters ticks to those at or after
<epoch>, truncates error messages to 300 chars, and prints compact JSON.
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

    parsed = json.loads(data["result"])
    ticks = parsed["ticks"] if isinstance(parsed, dict) else parsed
    location = parsed.get("name", "") if isinstance(parsed, dict) else ""
    out = [
        {
            "tickId": t["tickId"],
            "timestamp": t["timestamp"],
            "location": location,
            "status": t.get("status", ""),
            "error": t.get("error", {}).get("message", str(t.get("error", "")))[:300],
        }
        for t in ticks
        if t.get("timestamp", 0) >= epoch
    ]
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    main()
