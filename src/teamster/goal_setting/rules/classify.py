"""Proficient / approaching / below from the projected level."""

from __future__ import annotations

from teamster.goal_setting.config import Levels
from teamster.goal_setting.records import StudentRecord


def classify(records: list[StudentRecord], levels: Levels) -> list[StudentRecord]:
    out = []
    for r in records:
        if not r.is_tested or r.projected_level is None:
            out.append(
                r.with_(is_proficient=False, is_approaching=False, is_below=False)
            )
            continue
        proficient = r.projected_level in levels.proficient
        approaching = r.projected_level in levels.approaching
        out.append(
            r.with_(
                is_proficient=proficient,
                is_approaching=approaching,
                is_below=not proficient and not approaching,
            )
        )
    return out
