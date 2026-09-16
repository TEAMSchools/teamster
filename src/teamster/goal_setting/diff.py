"""Compare a proposal to the prior run for the same group and year.

Manifest depth always works because manifests are committed. Student depth
needs the prior run's student_buckets.csv, which lives only on the operator's
disk.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from teamster.goal_setting.records import StudentRecord

GOAL_FIELDS = ("bubble_parameter", "n_to_move", "goal")


@dataclass
class DiffReport:
    verdict: str
    goal_changes: list[dict] = field(default_factory=list)
    count_changes: list[dict] = field(default_factory=list)
    transitions: list[dict] | None = None
    roster_churn: dict | None = None
    n_reclassified: int = 0
    depth: str = "manifest"

    def as_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "depth": self.depth,
            "n_reclassified": self.n_reclassified,
            "goal_changes": self.goal_changes,
            "count_changes": self.count_changes,
            "transitions": self.transitions,
            "roster_churn": self.roster_churn,
        }

    def render(self) -> str:
        if self.verdict == "no prior run":
            return "diff: no prior run for this group and year"
        lines = [f"diff vs prior run ({self.depth} depth)"]
        if self.goal_changes:
            lines.append("goal changes: region | school | gr | field | old | new")
            for c in self.goal_changes:
                for f in GOAL_FIELDS:
                    if c["old"][f] != c["new"][f]:
                        lines.append(
                            f"  {c['region']} | {c['school']} | {c['grade_level']} | {f} | {c['old'][f]} | {c['new'][f]}"
                        )
        if self.count_changes:
            lines.append(
                "bucket count changes: region | school | gr | bucket | old | new"
            )
            for c in self.count_changes:
                tag = c["bucket"] + (
                    f" ({c['bucket4_outcome']})" if c["bucket4_outcome"] else ""
                )
                lines.append(
                    f"  {c['region']} | {c['school']} | {c['grade_level']} | {tag} | {c['old']} | {c['new']}"
                )
        if self.transitions is not None and self.roster_churn is not None:
            lines.append(
                f"roster churn: {self.roster_churn['new']} new, {self.roster_churn['gone']} gone"
            )
            if self.transitions:
                lines.append("transitions: region | school | gr | from | to | n")
                for t in self.transitions:
                    lines.append(
                        f"  {t['region']} | {t['school']} | {t['grade_level']} | {t['from']} | {t['to']} | {t['n']}"
                    )
        verdict = (
            self.verdict.upper() if self.verdict == "reclassifies" else self.verdict
        )
        suffix = (
            f" {self.n_reclassified} students already proposed"
            if self.verdict == "reclassifies"
            else ""
        )
        lines.append(f"verdict: {verdict}{suffix}")
        return "\n".join(lines)


def load_prior_manifest(path: Path) -> dict | None:
    return json.loads(path.read_text()) if path.exists() else None


def _goal_key(g: dict) -> tuple:
    return (g["region"], g["school"], g["grade_level"], g["subject"])


def _count_key(c: dict) -> tuple:
    return (
        c["region"],
        c["school"],
        c["grade_level"],
        c["subject"],
        c["bucket"],
        c["bucket4_outcome"],
    )


def diff_manifests(prior: dict | None, current: dict) -> DiffReport:
    if prior is None:
        return DiffReport(verdict="no prior run")
    rep = DiffReport(verdict="no change")

    old_goals = {_goal_key(g): g for g in prior["school_goals"]}
    for g in current["school_goals"]:
        o = old_goals.get(_goal_key(g))
        if o is None or any(o[f] != g[f] for f in GOAL_FIELDS):
            rep.goal_changes.append(
                {
                    "region": g["region"],
                    "school": g["school"],
                    "grade_level": g["grade_level"],
                    "subject": g["subject"],
                    "old": {f: (o or {}).get(f) for f in GOAL_FIELDS},
                    "new": {f: g[f] for f in GOAL_FIELDS},
                }
            )

    old_counts = {_count_key(c): c["n"] for c in prior["bucket_counts"]}
    new_counts = {_count_key(c): c["n"] for c in current["bucket_counts"]}
    for key in sorted(
        set(old_counts) | set(new_counts), key=lambda k: tuple(str(x) for x in k)
    ):
        o, n = old_counts.get(key, 0), new_counts.get(key, 0)
        if o != n:
            rep.count_changes.append(
                {
                    "region": key[0],
                    "school": key[1],
                    "grade_level": key[2],
                    "subject": key[3],
                    "bucket": key[4],
                    "bucket4_outcome": key[5],
                    "old": o,
                    "new": n,
                }
            )

    if rep.goal_changes or rep.count_changes:
        rep.verdict = "changed counts"
    return rep


def add_student_depth(
    rep: DiffReport, prior_rows: list[dict], current: list[StudentRecord]
) -> DiffReport:
    rep.depth = "student"
    prior = {
        (r["region"], int(r["student_number"]), r["subject"]): r["bucket"]
        for r in prior_rows
    }
    now = {(r.region, r.student_number, r.subject): r for r in current}
    new = len(set(now) - set(prior))
    gone = len(set(prior) - set(now))
    acc: dict[tuple, int] = {}
    for key, r in now.items():
        old = prior.get(key)
        if old is not None and old != r.bucket:
            k = (r.region, r.school, r.grade_level, r.subject, old, r.bucket)
            acc[k] = acc.get(k, 0) + 1
    rep.transitions = [
        {
            "region": k[0],
            "school": k[1],
            "grade_level": k[2],
            "subject": k[3],
            "from": k[4],
            "to": k[5],
            "n": n,
        }
        for k, n in sorted(acc.items())
    ]
    rep.roster_churn = {"new": new, "gone": gone}
    rep.n_reclassified = sum(acc.values())
    if rep.n_reclassified:
        rep.verdict = "reclassifies"
    elif new or gone:
        rep.verdict = "additive only"
    elif not rep.goal_changes and not rep.count_changes:
        rep.verdict = "no change"
    return rep
