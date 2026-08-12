"""Build a de-identified demographics workbook for the Quill pilot roster.

The roster export keys students by Quill's own platform user ID, not by any
KIPP identifier, so the delivered workbook carries no KIPP identifier at all.
The mapping back to real students is written to a separate local key file that
is never committed and never transmitted.

See docs/reference/quill-seta-ed-demographics-extract.md.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

OUTPUT_COLUMNS: tuple[str, ...] = (
    "quill_student_id",
    "classroom_code",
    "teacher_code",
    "race_ethnicity",
    "gender",
    "meal_status",
    "iep_status",
    "mll_status",
    "demographics_source",
)

# Mirrors rpt_gsheets__csgf_enrollment so the network keeps one convention.
RACE_LABELS: dict[str, str] = {
    "A": "Asian",
    "B": "BL-AA",
    "H": "Hispanic or Latino",
    "I": "AI-AN",
    "M": "DTS",
    "N": "DTS",
    "P": "NH-OPI",
    "T": "2+ races",
    "W": "White",
    "Y": "DTS",
}
UNKNOWN_RACE = "DTS"

GENDER_LABELS: dict[str, str] = {"F": "Female", "M": "Male", "X": "Non-Binary"}

MEAL_LABELS: dict[str, str] = {
    "F": "Free",
    "FDC": "Free",
    "R": "Reduced",
    "P": "Paid",
}

IEP_LABELS: frozenset[str] = frozenset({"Has IEP", "No IEP"})
MLL_LABELS: frozenset[str] = frozenset({"ML", "Not ML"})

NOT_MATCHED = "not matched"
_SOURCE_PATTERN = re.compile(r"^SY\d{2}-\d{2}( \(fallback\))?$")
_CLASSROOM_CODE_PATTERN = re.compile(r"^C\d{2}$")
_TEACHER_CODE_PATTERN = re.compile(r"^T\d+$")


@dataclass(frozen=True)
class RosterRow:
    """One student-classroom pair as exported from the Quill platform."""

    quill_student_id: int
    student_email: str
    classroom_name: str
    teacher_name: str


@dataclass(frozen=True)
class Demographics:
    """One student's warehouse record for a single academic year."""

    academic_year: int
    student_number: int
    race_ethnicity: str
    gender: str
    meal_status: str
    iep_status: str
    mll_status: str


def school_year_label(academic_year: int) -> str:
    """2025 -> 'SY25-26'."""
    return f"SY{academic_year % 100:02d}-{(academic_year + 1) % 100:02d}"


def label_race(code: str | None) -> str:
    if code is None or code == "":
        return ""
    return RACE_LABELS.get(code.strip().upper(), UNKNOWN_RACE)


def label_gender(code: str | None) -> str:
    if code is None or code == "":
        return ""
    return GENDER_LABELS.get(code.strip().upper(), "")


def label_meal(code: str | None) -> str:
    if code is None or code == "":
        return ""
    return MEAL_LABELS.get(code.strip().upper(), "")


def assign_codes(
    names: Iterable[str],
    existing: Mapping[str, str],
    prefix: str,
    width: int,
) -> dict[str, str]:
    """Assign codes in order of first appearance, reusing prior assignments.

    Order of first appearance rather than alphabetical order: this script is
    public, and an alphabetical rule would let anyone who knows the real
    classroom or teacher names derive the mapping.
    """
    codes = dict(existing)
    used = [
        int(code[len(prefix) :])
        for code in codes.values()
        if code[len(prefix) :].isdigit()
    ]
    next_index = max(used, default=0) + 1

    for name in names:
        if name in codes:
            continue

        codes[name] = f"{prefix}{next_index:0{width}d}"
        next_index += 1

    return codes


def build_output_rows(
    roster: Sequence[RosterRow],
    demographics: Mapping[str, Demographics],
    pilot_year: int,
    classroom_codes: Mapping[str, str],
    teacher_codes: Mapping[str, str],
) -> list[dict[str, object]]:
    """One output row per roster row, carrying no identifier but the Quill ID."""
    rows: list[dict[str, object]] = []

    for entry in roster:
        record = demographics.get(entry.student_email)

        if record is None:
            source = NOT_MATCHED
        elif record.academic_year == pilot_year:
            source = school_year_label(record.academic_year)
        else:
            source = f"{school_year_label(record.academic_year)} (fallback)"

        rows.append(
            {
                "quill_student_id": entry.quill_student_id,
                "classroom_code": classroom_codes.get(entry.classroom_name, ""),
                "teacher_code": teacher_codes.get(entry.teacher_name, ""),
                "race_ethnicity": label_race(record.race_ethnicity if record else None),
                "gender": label_gender(record.gender if record else None),
                "meal_status": label_meal(record.meal_status if record else None),
                "iep_status": record.iep_status if record else "",
                "mll_status": record.mll_status if record else "",
                "demographics_source": source,
            }
        )

    return rows


def build_key_records(
    roster: Sequence[RosterRow],
    demographics: Mapping[str, Demographics],
    classroom_codes: Mapping[str, str],
    teacher_codes: Mapping[str, str],
) -> list[dict[str, object]]:
    """The re-identification key the agreement requires the supplier to retain."""
    records: list[dict[str, object]] = []

    for entry in roster:
        record = demographics.get(entry.student_email)

        records.append(
            {
                "quill_student_id": entry.quill_student_id,
                "student_email": entry.student_email,
                "student_number": record.student_number if record else None,
                "classroom_name": entry.classroom_name,
                "teacher_name": entry.teacher_name,
                "classroom_code": classroom_codes.get(entry.classroom_name, ""),
                "teacher_code": teacher_codes.get(entry.teacher_name, ""),
            }
        )

    return records


def validate_rows(
    rows: Sequence[Mapping[str, object]], roster: Sequence[RosterRow]
) -> None:
    """Whitelist every delivered cell. Raises ValueError on the first problem.

    Whitelisting rather than scanning for known names: a blacklist false-fires
    on surnames that collide with labels ('Free', 'Male') and silently misses
    anything not on the list.
    """
    if len(rows) != len(roster):
        raise ValueError(f"row count {len(rows)} does not match roster {len(roster)}")

    allowed_ids = {entry.quill_student_id for entry in roster}
    allowed: dict[str, frozenset[str]] = {
        "race_ethnicity": frozenset(RACE_LABELS.values()) | {""},
        "gender": frozenset(GENDER_LABELS.values()) | {""},
        "meal_status": frozenset(MEAL_LABELS.values()) | {""},
        "iep_status": IEP_LABELS | {""},
        "mll_status": MLL_LABELS | {""},
    }

    for index, row in enumerate(rows):
        if tuple(row) != OUTPUT_COLUMNS:
            raise ValueError(f"row {index} columns are {tuple(row)}")

        if row["quill_student_id"] not in allowed_ids:
            raise ValueError(f"row {index} quill_student_id is not on the roster")

        classroom_code = str(row["classroom_code"])
        if not _CLASSROOM_CODE_PATTERN.match(classroom_code):
            raise ValueError(
                f"row {index} classroom_code {classroom_code!r} is not a code"
            )

        teacher_code = str(row["teacher_code"])
        if not _TEACHER_CODE_PATTERN.match(teacher_code):
            raise ValueError(f"row {index} teacher_code {teacher_code!r} is not a code")

        for column, vocabulary in allowed.items():
            value = str(row[column])
            if value not in vocabulary:
                raise ValueError(f"row {index} {column} disallowed value {value!r}")

        source = str(row["demographics_source"])
        if source != NOT_MATCHED and not _SOURCE_PATTERN.match(source):
            raise ValueError(f"row {index} demographics_source {source!r}")
