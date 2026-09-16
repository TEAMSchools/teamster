"""Bucket 2: the approaching students a school must move to reach its goal."""

from __future__ import annotations

from teamster.goal_setting.records import SchoolGoal, StudentRecord

_NO_PREVIOUS_ROW = object()
"""Sentinel for "no row has been ranked yet".

None is a real projected_score, so seeding prev_score with None made the first
row of a group tie with a null-scored predecessor that does not exist.
"""


def _fmt(score: float | None) -> str:
    return "untested" if score is None else f"{score:g}"


def top_approaching_to_move(
    records: list[StudentRecord], goals: list[SchoolGoal], ties: str
) -> list[StudentRecord]:
    to_move = {g.group_key: g.n_to_move for g in goals}
    by_group: dict[tuple[str, str, str, int], list[StudentRecord]] = {}
    for r in records:
        if r.is_approaching:
            by_group.setdefault(r.group_key, []).append(r)

    # (group_key, student_number) -> (rank, reason). group_key leads with
    # region, so the identity is region plus student number, never student
    # number alone: regions issue student numbers independently.
    # (rank, reason, admissible). A row with no projected score is ranked so
    # the operator can see it, but never admitted: there is no score to put it
    # above the cutoff, and admitting it would hand a Bucket 2 seat to a
    # missing measurement.
    ranked: dict[tuple[tuple[str, str, str, int], int], tuple[int, str, bool]] = {}
    for key, group in by_group.items():
        n = to_move.get(key, 0)
        ordered = sorted(
            group, key=lambda r: (-(r.projected_score or 0), r.student_number)
        )
        prev_score, prev_rank = _NO_PREVIOUS_ROW, 0
        for i, r in enumerate(ordered, start=1):
            if ties == "admit" and r.projected_score == prev_score:
                rank = prev_rank
            else:
                rank = i
            prev_score, prev_rank = r.projected_score, rank
            reason = (
                f"approaching, projected {_fmt(r.projected_score)}, "
                f"rank {rank} of {n} to move"
            )
            admissible = r.projected_score is not None
            if not admissible:
                reason += "; not ranked: no projected score"
            ranked[(r.group_key, r.student_number)] = (rank, reason, admissible)

    out = []
    for r in records:
        ranked_key = (r.group_key, r.student_number)
        if ranked_key in ranked and r.is_approaching:
            rank, reason, admissible = ranked[ranked_key]
            admitted = admissible and rank <= to_move.get(r.group_key, 0)
            out.append(
                r.with_(
                    rank=rank, reason=reason, bucket="Bucket 2" if admitted else None
                )
            )
        else:
            out.append(r)
    return out


def none(
    records: list[StudentRecord], goals: list[SchoolGoal], ties: str
) -> list[StudentRecord]:
    return records
