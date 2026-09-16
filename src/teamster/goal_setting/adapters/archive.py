"""Save fetched rows next to the run so a run can be replayed without the warehouse."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

from teamster.goal_setting.records import StudentRecord

INPUT_COLUMNS = [
    "region",
    "student_number",
    "school",
    "school_id",
    "grade_level",
    "subject",
    "is_tested",
    "projected_level",
    "projected_score",
    "stretch_level",
    "assessment",
]


class ArchiveMismatch(Exception):
    pass


def records_to_rows(records: list[StudentRecord]) -> list[dict]:
    return [{c: getattr(r, c) for c in INPUT_COLUMNS} for r in records]


def _opt_int(v: str) -> int | None:
    return None if v in ("", "None") else int(v)


def _opt_float(v: str) -> float | None:
    return None if v in ("", "None") else float(v)


def rows_to_records(rows: list[dict]) -> list[StudentRecord]:
    return [
        StudentRecord(
            region=r["region"],
            student_number=int(r["student_number"]),
            school=r["school"],
            school_id=int(r["school_id"]),
            grade_level=int(r["grade_level"]),
            subject=r["subject"],
            is_tested=str(r["is_tested"]) == "True",
            projected_level=_opt_int(str(r["projected_level"])),
            projected_score=_opt_float(str(r["projected_score"])),
            stretch_level=_opt_int(str(r["stretch_level"])),
            assessment=r["assessment"],
        )
        for r in rows
    ]


def _per_school(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    acc: dict[tuple, list[int]] = {}
    for r in rows:
        t = acc.setdefault((r["region"], r["school"], int(r["grade_level"])), [0, 0])
        t[0] += 1
        t[1] += int(str(r["is_tested"]) == "True")
    keys = sorted(acc)
    counts = [
        {"region": k[0], "school": k[1], "grade_level": k[2], "n": acc[k][0]}
        for k in keys
    ]
    shares = [
        {
            "region": k[0],
            "school": k[1],
            "grade_level": k[2],
            "share": round(acc[k][1] / acc[k][0], 3),
        }
        for k in keys
    ]
    return counts, shares


def write_input(rows: list[dict], path: Path) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=INPUT_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    counts, shares = _per_school(rows)
    return {
        "file": path.name,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "row_count": len(rows),
        "counts_by_school_grade": counts,
        "tested_share_by_school_grade": shares,
    }


def read_input(path: Path, expected_sha: str) -> list[dict]:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected_sha:
        raise ArchiveMismatch(
            f"{path}: sha256 {actual} does not match manifest {expected_sha}"
        )
    with path.open() as fh:
        return list(csv.DictReader(fh))
