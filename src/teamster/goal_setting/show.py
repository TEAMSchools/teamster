"""Replay one student's explanation from a saved run folder."""

from __future__ import annotations

import csv
from pathlib import Path


def explain(run_dir: Path, student_number: int, region: str | None = None) -> list[str]:
    path = run_dir / "explain.csv"
    if not path.exists():
        return [f"{path} not found; is {run_dir} a run folder?"]
    with path.open() as fh:
        rows = [
            r
            for r in csv.DictReader(fh)
            if r["student_number"] == str(student_number)
            and (region is None or r["region"] == region)
        ]
    if not rows:
        return [f"student {student_number} is not in this run"]
    return [
        f"{r['region']} {r['subject']}: {r['bucket']} because {r['reason']}"
        for r in rows
    ]
