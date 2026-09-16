"""Dataclasses shared by adapters, rules, and outputs.

A StudentRecord starts as what an adapter fetched and gains classification,
rank, bucket, and reason as it moves through the rules. Rules return new
records rather than mutating, so a test can compare before and after.
"""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class StudentRecord:
    region: str
    student_number: int
    school: str
    school_id: int
    grade_level: int
    subject: str
    is_tested: bool
    projected_level: int | None
    projected_score: float | None
    stretch_level: int | None
    assessment: str
    is_proficient: bool = False
    is_approaching: bool = False
    is_below: bool = False
    rank: int | None = None
    bucket: str | None = None
    bucket4_outcome: str | None = None  # "below" | "untested"
    reason: str = ""

    def with_(self, **changes) -> StudentRecord:
        return replace(self, **changes)

    @property
    def group_key(self) -> tuple[str, str, str, int]:
        """Partition key for ranking and goals: region, school, subject, grade.

        Region leads the key because school names are not unique across
        regions: a Newark and a Camden school can share a name and must still
        get their own goal row and their own Bucket 2 ranking.
        """
        return (self.region, self.school, self.subject, self.grade_level)


@dataclass(frozen=True)
class SchoolGoal:
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
    target: float
    bubble_parameter: float | None
    n_to_move: int
    goal: float

    @property
    def group_key(self) -> tuple[str, str, str, int]:
        return (self.region, self.school, self.subject, self.grade_level)
