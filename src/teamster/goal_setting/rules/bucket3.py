"""Bucket 3 strategies. Each takes records after Bucket 2 has been assigned."""

from __future__ import annotations

from teamster.goal_setting.config import Levels
from teamster.goal_setting.records import StudentRecord


def _unplaced_tested(r: StudentRecord) -> bool:
    return r.is_tested and r.bucket is None and not r.is_proficient


def _is_stretch_reacher(r: StudentRecord, levels: Levels) -> bool:
    return r.stretch_level is not None and r.stretch_level in levels.proficient


def remaining_approaching(
    records: list[StudentRecord], levels: Levels
) -> list[StudentRecord]:
    out = []
    for r in records:
        if _unplaced_tested(r) and r.is_approaching:
            base = r.reason or f"projected level {r.projected_level}"
            out.append(
                r.with_(bucket="Bucket 3", reason=f"{base}; remaining approaching")
            )
        else:
            out.append(r)
    return out


def stretch_reachers(
    records: list[StudentRecord], levels: Levels
) -> list[StudentRecord]:
    out = []
    for r in records:
        if _unplaced_tested(r) and _is_stretch_reacher(r, levels):
            base = r.reason or f"projected level {r.projected_level}"
            out.append(
                r.with_(
                    bucket="Bucket 3",
                    reason=f"{base}; reaches level {r.stretch_level} with stretch growth",
                )
            )
        else:
            out.append(r)
    return out


def remaining_approaching_or_stretch(
    records: list[StudentRecord], levels: Levels
) -> list[StudentRecord]:
    return stretch_reachers(remaining_approaching(records, levels), levels)


def none(records: list[StudentRecord], levels: Levels) -> list[StudentRecord]:
    return records
