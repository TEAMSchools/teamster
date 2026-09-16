"""Every file a run writes, in one call, after invariants have passed."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from teamster.goal_setting.config import Crosswalk
from teamster.goal_setting.pipeline import Proposal

ILLUMINATE_SUBJECT = {"Math": "Mathematics", "Reading": "Text Study"}
PROGRAM_BUCKETS = ("Bucket 1", "Bucket 2", "Bucket 3")


def _write_csv(path: Path, rows: list[dict], columns: list[str]) -> Path:
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return path


def school_goal_rows(p: Proposal) -> list[dict]:
    return [
        {
            "Academic_Year": p.academic_year,
            "School_ID": g.school_id,
            "Grade_Level": g.grade_level,
            "Illuminate_Subject_Area": ILLUMINATE_SUBJECT[g.subject],
            "School_Goal": f"{g.goal:.2f}",
            "Grade_Band_Goal": f"{g.target:.2f}",
        }
        for g in sorted(p.goals, key=lambda g: (g.region, g.school, g.grade_level))
    ]


def program_rows(p: Proposal, xw: Crosswalk) -> list[dict]:
    enter = date(p.academic_year, 7, 1).isoformat()
    exit_ = date(p.academic_year + 1, 6, 30).isoformat()
    rows = []
    for r in sorted(
        p.records, key=lambda r: (r.region, r.school, r.grade_level, r.student_number)
    ):
        if r.bucket in PROGRAM_BUCKETS:
            rows.append(
                {
                    "region": r.region,
                    "student_number": r.student_number,
                    "programid": xw.program_id(r.region, r.subject, r.bucket),
                    "enter_date": enter,
                    "exit_date": exit_,
                }
            )
    return rows


def write_run(out_dir: Path, p: Proposal, manifest: dict, xw: Crosswalk) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    student_rows = [
        asdict(r)
        for r in sorted(
            p.records,
            key=lambda r: (
                r.region,
                r.school,
                r.grade_level,
                r.bucket or "",
                r.student_number,
            ),
        )
    ]
    student_cols = list(student_rows[0]) if student_rows else []
    written = [
        _write_csv(
            out_dir / "school_goals.csv",
            school_goal_rows(p),
            [
                "Academic_Year",
                "School_ID",
                "Grade_Level",
                "Illuminate_Subject_Area",
                "School_Goal",
                "Grade_Band_Goal",
            ],
        ),
        _write_csv(
            out_dir / "ps_programs.csv",
            program_rows(p, xw),
            ["region", "student_number", "programid", "enter_date", "exit_date"],
        ),
        _write_csv(out_dir / "student_buckets.csv", student_rows, student_cols),
        _write_csv(
            out_dir / "explain.csv",
            student_rows,
            ["region", "student_number", "subject", "bucket", "reason"],
        ),
    ]
    mpath = out_dir / "manifest.json"
    mpath.write_text(json.dumps(manifest, indent=2) + "\n")
    written.append(mpath)
    return written


def summary_tables(p: Proposal) -> str:
    lines = [
        "region | school | gr | roster | tested | untested | prof | appr | bp | "
        "to_move | target | goal | B1 | B2 | B3 | B4"
    ]
    by_key: dict[tuple, dict[str, int]] = {}
    for r in p.records:
        d = by_key.setdefault(
            r.group_key, {"B1": 0, "B2": 0, "B3": 0, "B4": 0, "untested": 0}
        )
        d["B" + (r.bucket or "")[-1]] += 1
        d["untested"] += int(r.bucket4_outcome == "untested")
    for g in sorted(p.goals, key=lambda g: (g.region, g.school, g.grade_level)):
        d = by_key.get(g.group_key, {})
        bp = "" if g.bubble_parameter is None else f"{g.bubble_parameter:.2f}"
        lines.append(
            f"{g.region} | {g.school} | {g.grade_level} | {g.n_roster} | {g.n_tested} | "
            f"{d.get('untested', 0)} | "
            f"{g.n_proficient} | {g.n_approaching} | {bp} | {g.n_to_move} | {g.target:.2f} | "
            f"{g.goal:.2f} | "
            f"{d.get('B1', 0)} | {d.get('B2', 0)} | {d.get('B3', 0)} | {d.get('B4', 0)}"
        )
    lines.append("")
    lines.append("region | gr | tested | prof + to_move | implied | target")
    acc: dict[tuple[str, int], list[int]] = {}
    for g in p.goals:
        t = acc.setdefault((g.region, g.grade_level), [0, 0])
        t[0] += g.n_tested
        t[1] += g.n_proficient + g.n_to_move
    for (region, grade), (tested, num) in sorted(acc.items()):
        implied = 0 if tested == 0 else num / tested
        lines.append(
            f"{region} | {grade} | {tested} | {num} | {implied:.3f} | "
            f"{p.targets.get((region, grade), float('nan')):.2f}"
        )
    if p.gate.warnings:
        lines += ["", "gate warnings:"] + [f"  {w}" for w in p.gate.warnings]
    return "\n".join(lines)
