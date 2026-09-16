"""The committed, non-PII record of a run."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from teamster.goal_setting.pipeline import Proposal


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bucket_counts(p: Proposal) -> list[dict]:
    acc: dict[tuple, int] = {}
    for r in p.records:
        key = (
            r.region,
            r.school,
            r.grade_level,
            r.subject,
            r.bucket,
            r.bucket4_outcome,
        )
        acc[key] = acc.get(key, 0) + 1
    return [
        dict(
            region=k[0],
            school=k[1],
            grade_level=k[2],
            subject=k[3],
            bucket=k[4],
            bucket4_outcome=k[5],
            n=n,
        )
        for k, n in sorted(acc.items(), key=lambda kv: tuple(str(x) for x in kv[0]))
    ]


def build(
    p: Proposal,
    rules_sha: str,
    crosswalk_sha: str,
    inputs: list[dict],
    diff: dict | None,
    force_stale: bool,
) -> dict:
    params = sorted(
        {(g.region, g.grade_level, g.bubble_parameter) for g in p.goals},
        key=lambda t: (t[0], t[1]),
    )
    return {
        "academic_year": p.academic_year,
        "group": p.group.name,
        "rollout_date": p.group.rollout_date.isoformat(),
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rules_sha": rules_sha,
        "crosswalk_sha": crosswalk_sha,
        "inputs": inputs,
        "gate_warnings": p.gate.warnings,
        "gate_errors": p.gate.errors,
        "gate_overridden": bool(p.gate.errors) and force_stale,
        "bubble_parameters": [
            {"region": r, "grade_level": g, "bubble_parameter": bp}
            for r, g, bp in params
        ],
        "school_goals": [
            {
                "region": g.region,
                "school": g.school,
                "school_id": g.school_id,
                "grade_level": g.grade_level,
                "subject": g.subject,
                "n_roster": g.n_roster,
                "n_tested": g.n_tested,
                "n_proficient": g.n_proficient,
                "n_approaching": g.n_approaching,
                "n_below": g.n_below,
                "target": g.target,
                "bubble_parameter": g.bubble_parameter,
                "n_to_move": g.n_to_move,
                "goal": g.goal,
            }
            for g in sorted(p.goals, key=lambda g: (g.region, g.school, g.grade_level))
        ],
        "bucket_counts": bucket_counts(p),
        "diff": diff,
    }
