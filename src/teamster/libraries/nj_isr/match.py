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
        matched_on: "both", "last name", or "birth date" for a match, else "".
        candidates: Every distinct student considered, by student number. Empty
            only for "no_candidate".
    """

    student: Student | None
    reason: str
    matched_on: str = ""
    candidates: tuple[Student, ...] = ()


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


_PARTIAL_LEVELS = ("last name", "birth date")
_NAME_SEPARATORS = re.compile(r"[\s\-.]+")


def _name_tokens(name: str) -> list[str]:
    decomposed = unicodedata.normalize("NFKD", name)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    cleaned = stripped.casefold().replace("'", "").replace("’", "")
    return [t for t in _NAME_SEPARATORS.split(cleaned) if t]


def _last_name_parts(ps_last_name: str) -> set[str]:
    return {
        part
        for part in _name_tokens(ps_last_name)
        if sum(c.isalpha() for c in part) >= 2
    }


def last_name_matches(printed_name: str, ps_last_name: str) -> bool:
    """Whether a PowerSchool last name appears in the printed name.

    Accents, case, and apostrophes are ignored. A multi-part last name matches
    when any one part of 2 or more letters is among the printed words. The
    student's PowerSchool first name is never compared.
    """
    return not _last_name_parts(ps_last_name).isdisjoint(_name_tokens(printed_name))


def surname_matches(printed_name: str, ps_last_name: str) -> bool:
    """Whether a PowerSchool last-name part is the printed name's final word.

    Stricter than `last_name_matches`: a printed first or middle name equal
    to the PowerSchool last name does not count.
    """
    printed = _name_tokens(printed_name)
    return bool(printed) and printed[-1] in _last_name_parts(ps_last_name)


def matched_on(record: Record, student: Student) -> str:
    """Which printed details agree with PowerSchool.

    Returns:
        "both" when the last name (`last_name_matches`) and birth date agree.
        "last name" when only the surname agrees, judged by the stricter
        `surname_matches`, because without the birth date a sibling or a
        student whose first name is another's surname could pass. "birth date"
        when only that agrees, and "" when neither does. A report with no
        printed birth date never agrees on birth date.
    """
    dob_agrees = record.printed_dob is not None and record.printed_dob == student.dob

    if dob_agrees and last_name_matches(record.printed_name, student.last_name):
        return "both"
    if not dob_agrees and surname_matches(record.printed_name, student.last_name):
        return "last name"
    if dob_agrees:
        return "birth date"
    return ""


def confirm(record: Record, student: Student) -> bool:
    """Whether the printed birth date and last name both agree with PowerSchool."""
    return matched_on(record, student) == "both"


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
    exactly 1 known student. A candidate is confirmed when the printed last
    name or birth date agrees with PowerSchool (see `matched_on`); agreeing on
    both is a full match and on only 1 is a partial match.

    When the two sources name different students, a single full match wins.
    With no full match, a single partial match wins. Anything else is a
    source conflict.
    """
    found = (
        _sole_candidate(crosswalk, record.state_id, students),
        _sole_candidate(by_state_id, record.state_id, students),
    )
    distinct = {s.student_number: s for s in found if s is not None}
    candidates = tuple(distinct[number] for number in sorted(distinct))

    if not candidates:
        return Resolution(None, "no_candidate")

    levels = {s.student_number: matched_on(record, s) for s in candidates}
    full = [s for s in candidates if levels[s.student_number] == "both"]
    partial = [s for s in candidates if levels[s.student_number] in _PARTIAL_LEVELS]

    winner: Student | None = None
    if len(candidates) == 1:
        winner = candidates[0] if levels[candidates[0].student_number] else None
    elif len(full) == 1:
        winner = full[0]
    elif not full and len(partial) == 1:
        winner = partial[0]

    if winner is not None:
        return Resolution(
            winner,
            "matched",
            matched_on=levels[winner.student_number],
            candidates=candidates,
        )

    reason = "failed_confirmation" if len(candidates) == 1 else "source_conflict"
    return Resolution(None, reason, candidates=candidates)


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
