"""Read production schema once, into a committed file.

This is the only module that touches production. Everything downstream reads
the committed snapshot at the pinned revision, so no build depends on what
production looks like right now.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SNAPSHOT_PATH = Path("src/cube/sandbox/schema_snapshot.json")


def render(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tables: dict[str, dict[str, Any]] = {}
    for row in rows:
        tables.setdefault(row["table_name"], {})[row["column_name"]] = {
            "type": row["data_type"],
            "nullable": row["is_nullable"] == "YES",
        }
    return {"tables": {t: dict(sorted(c.items())) for t, c in sorted(tables.items())}}


def load(path: Path = SNAPSHOT_PATH) -> dict[str, Any]:
    return json.loads(path.read_text())


def main() -> int:
    from google.cloud import bigquery

    from teamster.cube_sandbox import model

    tables = sorted(model.table_set(Path("src/cube")))
    client = bigquery.Client(project="teamster-332318")
    rows = [
        dict(r)
        for r in client.query(
            "SELECT table_name, column_name, data_type, is_nullable "
            "FROM `teamster-332318.kipptaf_marts.INFORMATION_SCHEMA.COLUMNS` "
            "WHERE table_name IN UNNEST(@tables)",
            job_config=bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ArrayQueryParameter("tables", "STRING", tables)
                ]
            ),
        ).result()
    ]
    out = render(rows)
    found = set(out["tables"])
    missing = set(tables) - found
    if missing:
        raise SystemExit(
            f"model references tables absent from production: {sorted(missing)}"
        )
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {SNAPSHOT_PATH}: {len(found)} tables")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
