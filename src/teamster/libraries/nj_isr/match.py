import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from teamster.libraries.nj_isr.models import Record

TRANSFER_FOLDER = "Transfer Out & Unmatched"


@dataclass(frozen=True)
class Enrollment:
    region: str
    schoolid: int
    school_name: str


@dataclass(frozen=True)
class Student:
    student_number: int
    last_name: str
    first_name: str
    dob: date | None
    current: Enrollment | None
    last_spring_school: str | None


@dataclass(frozen=True)
class Resolution:
    """Outcome of matching a record to a student.

    Attributes:
        student: The confirmed student, None unless reason is "matched".
        reason: "matched", "no_candidate", "failed_confirmation", or
            "source_conflict".
    """

    student: Student | None
    reason: str


@dataclass(frozen=True)
class Placement:
    """Where a record's pages are filed.

    Attributes:
        record: The record being filed.
        resolution: How the record was matched.
        region: Region of the destination folder.
        schoolid: PowerSchool schoolid, None for the region's transfer folder.
        where: School name, or TRANSFER_FOLDER.
    """

    record: Record
    resolution: Resolution
    region: str
    schoolid: int | None
    where: str


_NAME_SEPARATORS = re.compile(r"[\s\-.]+")


def _name_tokens(name: str) -> list[str]:
    decomposed = unicodedata.normalize("NFKD", name)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    cleaned = stripped.casefold().replace("'", "").replace("’", "")
    return [t for t in _NAME_SEPARATORS.split(cleaned) if t]


def last_name_matches(printed_name: str, ps_last_name: str) -> bool:
    """Whether a PowerSchool last name appears in the printed name.

    Accents, case, and apostrophes are ignored. A multi-part last name matches
    when any one part of 2 or more letters is among the printed words. The
    student's PowerSchool first name is never compared.
    """
    printed = set(_name_tokens(printed_name))
    return any(
        sum(c.isalpha() for c in part) >= 2 and part in printed
        for part in _name_tokens(ps_last_name)
    )


def confirm(record: Record, student: Student) -> bool:
    """Whether the printed birth date and last name both agree with PowerSchool."""
    return (
        record.printed_dob is not None
        and record.printed_dob == student.dob
        and last_name_matches(record.printed_name, student.last_name)
    )


def _sole_candidate(
    numbers: Mapping[str, set[int]], state_id: str, students: Mapping[int, Student]
) -> Student | None:
    found = numbers.get(state_id, set())
    if len(found) != 1:
        return None
    return students.get(next(iter(found)))


def resolve(
    record: Record,
    crosswalk: Mapping[str, set[int]],
    by_state_id: Mapping[str, set[int]],
    students: Mapping[int, Student],
) -> Resolution:
    """Match a record to a PowerSchool student and confirm the match.

    The state ID is looked up in the state testing crosswalk and in
    PowerSchool's own state ID field. A source only counts when it names
    exactly 1 known student. When the two sources name different students, the
    one that passes confirmation wins, and a tie or no pass is a source
    conflict.
    """
    from_crosswalk = _sole_candidate(crosswalk, record.state_id, students)
    from_state_id = _sole_candidate(by_state_id, record.state_id, students)

    if from_crosswalk is None and from_state_id is None:
        return Resolution(None, "no_candidate")

    if (
        from_crosswalk is not None
        and from_state_id is not None
        and from_crosswalk.student_number != from_state_id.student_number
    ):
        passing = [s for s in (from_crosswalk, from_state_id) if confirm(record, s)]
        if len(passing) == 1:
            return Resolution(passing[0], "matched")
        return Resolution(None, "source_conflict")

    candidate = from_crosswalk if from_crosswalk is not None else from_state_id
    if candidate is not None and confirm(record, candidate):
        return Resolution(candidate, "matched")
    return Resolution(None, "failed_confirmation")


def place(record: Record, resolution: Resolution, testing_region: str) -> Placement:
    """Choose the destination folder for a resolved record.

    A matched student currently enrolled goes to that school's folder, in the
    region where the student is enrolled. Everyone else goes to the transfer
    folder of the region that administered the test.
    """
    student = resolution.student
    if student is not None and student.current is not None:
        current = student.current
        return Placement(
            record, resolution, current.region, current.schoolid, current.school_name
        )
    return Placement(record, resolution, testing_region, None, TRANSFER_FOLDER)
