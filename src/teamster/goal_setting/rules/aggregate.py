"""Counts per school, subject, and grade. The input to school goals."""

from __future__ import annotations

from dataclasses import dataclass

from teamster.goal_setting.records import StudentRecord


@dataclass(frozen=True)
class SchoolCounts:
    region: str
    school: str
    school_id: int
    grade_level: int
    subject: str
    n_roster: int
    n_tested: int
    n_proficient: int
    n_approaching: int
    n_below: int

    @property
    def group_key(self) -> tuple[str, str, int]:
        return (self.school, self.subject, self.grade_level)


def count_by_school(records: list[StudentRecord]) -> list[SchoolCounts]:
    acc: dict[tuple[str, str, int], dict] = {}
    for r in records:
        a = acc.setdefault(
            r.group_key,
            dict(
                region=r.region,
                school=r.school,
                school_id=r.school_id,
                grade_level=r.grade_level,
                subject=r.subject,
                n_roster=0,
                n_tested=0,
                n_proficient=0,
                n_approaching=0,
                n_below=0,
            ),
        )
        a["n_roster"] += 1
        a["n_tested"] += int(r.is_tested)
        a["n_proficient"] += int(r.is_proficient)
        a["n_approaching"] += int(r.is_approaching)
        a["n_below"] += int(r.is_below)
    return [SchoolCounts(**a) for a in acc.values()]
