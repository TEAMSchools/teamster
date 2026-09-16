"""Bucket 2: the approaching students a school must move to reach its goal."""

from __future__ import annotations

from teamster.goal_setting.records import SchoolGoal, StudentRecord


def _fmt(score: float | None) -> str:
    return "untested" if score is None else f"{score:g}"


def top_approaching_to_move(
    records: list[StudentRecord], goals: list[SchoolGoal], ties: str
) -> list[StudentRecord]:
    to_move = {g.group_key: g.n_to_move for g in goals}
    by_group: dict[tuple[str, str, int], list[StudentRecord]] = {}
    for r in records:
        if r.is_approaching:
            by_group.setdefault(r.group_key, []).append(r)

    ranked: dict[int, tuple[int, str]] = {}  # student_number -> (rank, reason)
    for key, group in by_group.items():
        n = to_move.get(key, 0)
        ordered = sorted(
            group, key=lambda r: (-(r.projected_score or 0), r.student_number)
        )
        prev_score, prev_rank = None, 0
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
            ranked[r.student_number] = (rank, reason)

    out = []
    for r in records:
        if r.student_number in ranked and r.is_approaching:
            rank, reason = ranked[r.student_number]
            admitted = rank <= to_move.get(r.group_key, 0)
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
