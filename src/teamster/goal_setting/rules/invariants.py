"""Checks on an assembled proposal. Run before any file is written."""

from __future__ import annotations

from teamster.goal_setting.records import SchoolGoal, StudentRecord

ROLLUP_TOLERANCE = 0.01


class InvariantError(Exception):
    def __init__(self, failures: list[str]):
        self.failures = failures
        super().__init__("\n".join(failures))


def _where(r: StudentRecord | SchoolGoal) -> str:
    return f"{r.region} {r.school} grade {r.grade_level} {r.subject}"


def check(
    records: list[StudentRecord],
    goals: list[SchoolGoal],
    targets: dict[tuple[str, int], float],
    school_goal_strategy: str,
) -> None:
    failures: list[str] = []

    seen: dict[tuple[str, int, str], list[StudentRecord]] = {}
    for r in records:
        seen.setdefault((r.region, r.student_number, r.subject), []).append(r)
        if r.bucket is None:
            failures.append(f"{_where(r)}: a student has no bucket")
    for rows in seen.values():
        buckets = {x.bucket for x in rows}
        if len(rows) > 1:
            failures.append(
                f"{_where(rows[0])}: one student holds {len(buckets)} buckets "
                f"({', '.join(sorted(str(b) for b in buckets))}) across {len(rows)} rows"
            )

    goal_keys = {g.group_key for g in goals}
    for key in sorted({r.group_key for r in records}):
        if key not in goal_keys:
            sample = next(r for r in records if r.group_key == key)
            failures.append(f"{_where(sample)}: no goal row")

    if school_goal_strategy == "bubble_parameter":
        acc: dict[tuple[str, int], list[int]] = {}
        for g in goals:
            t = acc.setdefault((g.region, g.grade_level), [0, 0])
            t[0] += g.n_proficient + g.n_to_move
            t[1] += g.n_tested
        for (region, grade), (num, den) in acc.items():
            target = targets.get((region, grade))
            if target is None or den == 0:
                continue
            implied = num / den
            if implied < target - ROLLUP_TOLERANCE:
                failures.append(
                    f"{region} grade {grade}: region roll-up {implied:.3f} is below "
                    f"target {target:.2f}"
                )

    if failures:
        raise InvariantError(failures)
