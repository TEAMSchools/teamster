"""Fabricate the sandbox dataset.

Facts never invent a key: every foreign key is sampled from rows already
generated, which makes referential integrity hold by construction rather than
by a check afterwards.
"""

from __future__ import annotations

import argparse
import calendar
import datetime as dt
import decimal
import hashlib
import random
import unicodedata
from dataclasses import dataclass, replace
from functools import cache
from pathlib import Path
from typing import Any

import yaml

from teamster.cube_sandbox import avro, model, personas, snapshot
from teamster.cube_sandbox.personas import Persona

SPINE_HEAD = "dim_student_enrollments"
SPINE_TAIL = "dim_student_section_enrollments"

SANDBOX_DOMAIN = "ktaf-sandbox.invalid"
CUBE_ROOT = Path("src/cube")
NAMES_PATH = CUBE_ROOT / "sandbox" / "reserved_names.yml"
PERSONAS_PATH = CUBE_ROOT / "sandbox" / "personas.yml"
MANIFEST_PATH = CUBE_ROOT / "sandbox" / "coverage_manifest.yml"
DEFAULT_OUT = Path("build/cube_sandbox")
DEFAULT_SEED = 20260924

# Latin-extended letters NFKD leaves alone, because they are single code
# points rather than a base plus a combining mark. Without these, Søren folds
# to "sren" and Æsa to "sa" — the character is dropped rather than carried
# across, which is the same silent mangling the fold exists to avoid.
_TRANSLITERATIONS = str.maketrans(
    {
        "ø": "o",
        "Ø": "O",
        "æ": "ae",
        "Æ": "AE",
        "œ": "oe",
        "Œ": "OE",
        "ß": "ss",
        "ð": "d",
        "Ð": "D",
        "þ": "th",
        "Þ": "TH",
        "ł": "l",
        "Ł": "L",
        "đ": "d",
        "Đ": "D",
        "ı": "i",
        "ŋ": "n",
    }
)

MANIFEST_FLOOR = 50
DATE_SPINE_MAX = 20 * 366  # the real academic-year range, never to year 9999

# Measured 2026-09-24 and carried from the spec's scale table. The daily
# attendance fact was 12.6M in an earlier draft, so these move: re-measure
# against INFORMATION_SCHEMA before trusting them for a full build.
_PRODUCTION_ROWS = {
    "fct_student_attendance_enrollment_daily": 29_791_485,
    "fct_assessment_scores_enrollment_scoped": 15_080_518,
    "fct_student_attendance_enrollment_periods": 4_402_039,
    "dim_students": 31_297,
    "dim_staff_work_history": 30_116,
    "dim_staff_reporting_chain": 9_310,
}


def generation_order(tables: set[str], edges: set[tuple[str, str]]) -> list[str]:
    """Topological order, with the spine cycle broken at a known edge.

    An edge `(a, b)` reads "a depends on b", so b is generated first.

    `dim_student_enrollments` and `dim_student_section_enrollments` each
    declare a Cube join onto the other, so the join graph has a two-node
    cycle and no order satisfies both. The edge to drop is
    HEAD -> TAIL, the homeroom join: it is declared from the enrollment side,
    but its foreign key (`student_enrollment_key`) lives on the SECTION table,
    so the enrollment table needs no value from it and can go first. Dropping
    the other edge instead orders sections first, and then every section's
    `student_enrollment_key` has no generated stint to sample from — which
    loads cleanly and fails at query time, the exact failure this ordering
    exists to prevent.

    Only that one edge is special. Any other cycle raises, because it means
    the model grew a relationship nobody has decided how to break.
    """
    edges = {(a, b) for a, b in edges if not (a == SPINE_HEAD and b == SPINE_TAIL)}
    remaining, order = set(tables), []
    while remaining:
        ready = sorted(
            t for t in remaining if not any(a == t and b in remaining for a, b in edges)
        )
        if not ready:
            raise ValueError(f"unbroken dependency cycle among {sorted(remaining)}")
        order.extend(ready)
        remaining -= set(ready)
    return order


def resolve_spine(
    enrollments: list[dict[str, Any]],
    sections: list[dict[str, Any]],
    rng: random.Random,
    unresolved_share: float = 0.05,
) -> list[dict[str, Any]]:
    """Third pass of the cycle: mark one current homeroom section per stint.

    The spec describes this as filling a `homeroom_section_key` on the
    enrollment table. No such column exists in the pinned snapshot —
    `dim_student_enrollments` carries no reference to a section at all. The
    relationship is expressed the other way round: `student_school_enrollments`
    joins `student_homeroom_section` on
    `student_enrollment_key AND {...is_current_homeroom}`, so the flag that
    closes the cycle is `is_current_homeroom` on the SECTION rows. This fills
    that instead; the pass, and the hazard it guards, are unchanged.

    Leaving a slice of stints with no current homeroom is one of the
    manifest's required cells, not sloppiness. Leaving them ALL unset is the
    silent failure: the data loads, and the homeroom-teacher join simply
    matches nothing.

    That unresolved slice is written NULL, not FALSE. The dbt column is
    `(is_homeroom and homeroom_rank = 1)`, which is NULL whenever the rank
    does not resolve on a homeroom row; its YAML says "never null" but no
    dbt `not_null` test asserts it, so the manifest requires a null row —
    and a generator that writes FALSE everywhere makes that cell
    unsatisfiable by construction. Per the spec, a column that is never null
    in practice and carries no test is a missing test: the sandbox nulls it,
    and the fix belongs in dbt. A nullable boolean in a join predicate is
    also exactly what the kit must learn to handle, since NULL and FALSE
    both fail the join but behave differently under negation.
    """
    by_stint: dict[str, list[dict[str, Any]]] = {}
    for row in sections:
        row["is_current_homeroom"] = False
        if row.get("is_homeroom"):
            by_stint.setdefault(row["student_enrollment_key"], []).append(row)

    with_candidates = [
        stint for stint in enrollments if by_stint.get(stint["student_enrollment_key"])
    ]
    for position, stint in enumerate(with_candidates):
        candidates = by_stint[stint["student_enrollment_key"]]
        # The first stint is unresolved unconditionally. A bare
        # `unresolved_share` coin flip can come up empty on the tiny profile,
        # which would leave the required null cell unsatisfied at random —
        # a flaky gate teaches nothing.
        if position == 0 or rng.random() < unresolved_share:
            for row in candidates:
                row["is_current_homeroom"] = None
            continue
        # Exactly one, or none. The homeroom join is one_to_one, so a second
        # current homeroom on one stint fans the attendance views out.
        rng.choice(candidates)["is_current_homeroom"] = True

    return sections


@cache
def _names() -> dict[str, list[Any]]:
    return yaml.safe_load(NAMES_PATH.read_text())


def reserved_surnames() -> list[str]:
    return list(_names()["surnames"])


def reserved_given_names() -> list[dict[str, str]]:
    """The given-name entries, each carrying the character class it exercises."""
    return [
        entry if isinstance(entry, dict) else {"name": entry, "class": "plain"}
        for entry in _names()["given_names"]
    ]


def given_name_classes() -> set[str]:
    """Every character class the reserved given names cover.

    Coverage asserts each class is present in a generated dataset rather than
    trusting that a random sample happened to include the hard ones.
    """
    return {entry["class"] for entry in reserved_given_names()}


def fabricate_name(rng: random.Random) -> tuple[str, str]:
    """A realistic given name beside a coined surname.

    The surname carries the proof: nothing else uses these words, so the
    appearance of the name identifies the row as synthetic. The given name
    stays realistic, because that is where the character classes that break
    interfaces live.
    """
    given = rng.choice(reserved_given_names())["name"]
    return given, rng.choice(reserved_surnames())


def _fold(part: str) -> str:
    """One name part as an ASCII, mailbox-safe token.

    Never returns empty. 李, Ольга and أمينة carry no ASCII at all, and
    dropping their characters would leave an address like
    `.fennworth@ktaf-sandbox.invalid` — not a valid mailbox, and a
    realistic-looking identity that `resolveAccess` matches to nobody, which
    is the exact failure ASCII-folding exists to prevent. Those fall back to a
    short digest of the original: still deterministic, still unique per name,
    and visibly synthetic.
    """
    decomposed = unicodedata.normalize("NFKD", part.translate(_TRANSLITERATIONS))
    folded = "".join(c for c in decomposed if c.isascii() and c.isalnum()).lower()
    if folded:
        return folded
    return "x" + hashlib.blake2s(part.encode("utf-8"), digest_size=3).hexdigest()


def to_ascii_email(given: str, surname: str) -> str:
    return f"{_fold(given)}.{_fold(surname)}@{SANDBOX_DOMAIN}"


def birth_date_for_grade(grade: int, academic_year: int, rng: random.Random) -> dt.date:
    """Grade first, then a birth date inside that grade's plausible window.

    A deliberate minority falls off-cohort — retained, accelerated, late entry
    — because those students are real and are what a kit gets wrong.

    The day spans the real month, leap days included. Clamping to 1..28 would
    make a month-end birthday impossible, and month-end and leap-day birthdays
    are exactly what breaks naive age arithmetic.
    """
    typical_age = grade + 5
    offset = rng.choices([0, -1, 1], weights=[85, 8, 7])[0]
    year = academic_year - typical_age - offset
    month = rng.randint(1, 12)
    return dt.date(year, month, rng.randint(1, calendar.monthrange(year, month)[1]))


# Production's shape: four school regions of very different sizes, and a
# network office region that enrolls no students. Order matters — personas
# take their region from the first four by index, and the office is index 4.
_REGIONS: list[dict[str, str]] = [
    {"name": "Newark Region", "legal_entity": "Newark Sandbox Charter School"},
    {"name": "Miami Region", "legal_entity": "Miami Sandbox Charter School"},
    {"name": "Camden Region", "legal_entity": "Camden Sandbox Charter School"},
    {"name": "Paterson Region", "legal_entity": "Paterson Sandbox Charter School"},
    {"name": "Network Office", "legal_entity": "Sandbox Network Office Inc."},
]
_SCHOOL_REGIONS = 4
_OFFICE_REGION = 4
# Relative school counts for the four school regions, after production's.
_SCHOOL_REGION_WEIGHTS = [11, 6, 4, 2]
# Row 0 of dim_locations carries the planted orphan, so the office is row 1.
_OFFICE_LOCATION = 1

# Reference tables whose size is part of their meaning. A region count that
# scales with the profile turns "region scope" into "one school".
_FIXED_ROWS = {
    # The five named regions, one nameless region that carries the manifest's
    # null cells, and the final row every child is withheld from.
    "dim_regions": len(_REGIONS) + 2,
    "dim_locations": MANIFEST_FLOOR,
}


def weighted_cycle(weights: list[int], count: int) -> list[int]:
    """Indexes into `weights`, interleaved in proportion to them.

    Smooth weighted round-robin: deterministic, and the small buckets appear
    early instead of all at the end, so even a short run reaches every one.
    """
    current = [0] * len(weights)
    total = sum(weights)
    picks = []
    for _ in range(count):
        current = [c + w for c, w in zip(current, weights, strict=True)]
        best = max(range(len(weights)), key=lambda i: current[i])
        current[best] -= total
        picks.append(best)
    return picks


SCALES = ("tiny", "realistic", "full")

# The realistic profile: enough students and staff that charts, trends, region
# rollups and year-over-year comparisons behave like production, small enough
# to build and load on a laptop. The size knobs are the two counts; tests
# shrink them.
REALISTIC_STUDENTS_PER_YEAR = 800
REALISTIC_STAFF = 300
# Academic years TARGET_ACADEMIC_YEAR - (n - 1) through TARGET_ACADEMIC_YEAR,
# so a year-over-year screen has two prior years to compare against.
REALISTIC_YEARS = 3
# Share of students who leave each year, replaced by new entrants.
REALISTIC_ATTRITION = 0.09
# Of those leavers, the share who leave mid-year rather than after June.
REALISTIC_EARLY_EXIT_SHARE = 0.5
# Of the entrants above kindergarten, the share who arrive after day one.
REALISTIC_LATE_ENTRY_SHARE = 0.5
# Share of student-years split into two stints at two schools.
REALISTIC_TRANSFER_SHARE = 0.03
REALISTIC_SECTIONS_PER_STINT = 6
REALISTIC_SECTIONS_PER_SCHOOL = 12
REALISTIC_SCORES_PER_STINT = (3, 6)
# Every other table: reference data whose size carries no meaning.
REALISTIC_DEFAULT_ROWS = 200
_STAFF_TABLES = frozenset(
    {
        "dim_staff",
        "dim_staff_cube_access",
        "dim_staff_reporting_chain",
        "dim_staff_reporting_periods",
        "dim_staff_work_history",
    }
)


def row_target(table: str, scale: str) -> int:
    """Rows to generate for one table under a named profile.

    Under `realistic`, the student tables, the school calendar and the facts
    are sized by the enrollment plan instead (see `_Fabricator._count`); the
    value here is only the fallback for tables the plan does not shape.
    """
    if scale not in SCALES:
        raise ValueError(f"unknown scale {scale!r}")
    if table == "dim_dates":
        return DATE_SPINE_MAX
    if table in _FIXED_ROWS:
        return _FIXED_ROWS[table]
    if scale == "tiny":
        return MANIFEST_FLOOR
    if scale == "realistic":
        return REALISTIC_STAFF if table in _STAFF_TABLES else REALISTIC_DEFAULT_ROWS
    return _PRODUCTION_ROWS.get(table, MANIFEST_FLOOR * 100)


# --------------------------------------------------------------------------
# Invented-value primitives
# --------------------------------------------------------------------------

# Surrogate keys are 32 lowercase hex characters, the shape
# `dbt_utils.generate_surrogate_key` emits, so client code that validates the
# format works unchanged at repoint. The first four characters are fixed:
# that prefix IS the reserved range. A production md5 lands on it about once
# in 65,536, so a sandbox key is recognisable on sight and the two sets are
# disjoint in practice rather than by promise.
# Columns that must map one row to one parent. Without this the FK pass
# cycles the pool with a modulo and silently repeats a parent once the rows
# outnumber it. On dim_staff_cube_access that is not cosmetic: resolveAccess
# reads ONE row per staff member, so a second one makes which access a viewer
# resolves arbitrary, and the canaries then pass or fail on which row the
# warehouse happened to return.
UNIQUE_FK: set[tuple[str, str]] = {
    ("dim_staff_cube_access", "staff_key"),
}


KEY_NAMESPACE = "5adb"

# The 555-0100 through 555-0199 block, reserved for fiction.
PHONE_PREFIX = "555-01"

# Nine-digit identifiers starting at 9. PowerSchool and ADP allocate from the
# low ranges, so nothing here can collide with a real one.
RESERVED_ID_BASE = 900_000_000

DATE_SPINE_START = dt.date(2010, 7, 1)

# The academic year the facts sit in. Bounding the facts to one real year is
# what keeps a `tiny` dataset coherent: 50 attendance rows scattered over a
# twenty-year spine join nothing anyone would recognise as a school.
TARGET_ACADEMIC_YEAR = 2025

# BigQuery NUMERIC is DECIMAL(38, 9); a value carrying more than nine decimal
# places fails the Avro write rather than rounding silently.
_NUMERIC_QUANTUM = decimal.Decimal("0.000000001")


def surrogate_key(namespace: str, index: int) -> str:
    """A format-valid surrogate key from the reserved range."""
    digest = hashlib.blake2s(f"{namespace}:{index}".encode(), digest_size=14)
    return KEY_NAMESPACE + digest.hexdigest()


def reserved_identifier(index: int) -> int:
    return RESERVED_ID_BASE + index


def fabricate_phone(index: int) -> str:
    """A number in the block reserved for fiction, so it can never ring."""
    return f"({200 + index % 700}) {PHONE_PREFIX}{index % 100:02d}"


def spine_date(index: int) -> dt.date:
    return DATE_SPINE_START + dt.timedelta(days=index)


def academic_year_of(day: dt.date) -> int:
    """KTAF's academic year starts on 1 July."""
    return day.year if day.month >= 7 else day.year - 1


def iso_week_start(day: dt.date) -> dt.date:
    return day - dt.timedelta(days=day.weekday())


def school_week_start(day: dt.date) -> dt.date:
    """PowerSchool's school week: an ISO week truncated at the month boundary.

    This is the semantic hazard the sandbox exists to teach, reproduced rather
    than smoothed. About 14% of calendar days fall in a school week that does
    not start on the ISO Monday, so an ISO grouping over these rows compiles,
    runs, and returns a different — meaningless — breakdown, with no
    query-time guard anywhere.
    """
    monday = iso_week_start(day)
    return monday if monday.month == day.month else day.replace(day=1)


def school_week_end(day: dt.date) -> dt.date:
    start = school_week_start(day)
    month_end = day.replace(day=calendar.monthrange(day.year, day.month)[1])
    return min(start + dt.timedelta(days=4), month_end)


# --------------------------------------------------------------------------
# The realistic profile's calendar and enrollment plan
# --------------------------------------------------------------------------

# ES K-4, MS 5-8, HS 9-12, matching the bands dim_locations carries.
_GRADE_BANDS = ("ES", "MS", "HS")


def grade_band_of(grade: int) -> str:
    return "ES" if grade <= 4 else "MS" if grade <= 8 else "HS"


def _next_weekday(day: dt.date) -> dt.date:
    while day.weekday() >= 5:
        day += dt.timedelta(days=1)
    return day


def _previous_weekday(day: dt.date) -> dt.date:
    while day.weekday() >= 5:
        day -= dt.timedelta(days=1)
    return day


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> dt.date:
    """The nth `weekday` (Monday 0) of a month; n = -1 is the last one."""
    days = [
        dt.date(year, month, d)
        for d in range(1, calendar.monthrange(year, month)[1] + 1)
        if dt.date(year, month, d).weekday() == weekday
    ]
    return days[n if n < 0 else n - 1]


def calendar_span(academic_year: int) -> tuple[dt.date, dt.date]:
    """The days a school calendar row exists for, staff return to year end.

    Wider than the instruction span on both sides, so the calendar holds days
    no student attends — the parent side of the calendar-to-fact orphan pair.
    """
    return dt.date(academic_year, 8, 1), dt.date(academic_year + 1, 6, 30)


def instruction_span(academic_year: int) -> tuple[dt.date, dt.date]:
    """First and last student day: mid-August to mid-June."""
    return (
        _next_weekday(dt.date(academic_year, 8, 15)),
        _previous_weekday(dt.date(academic_year + 1, 6, 15)),
    )


@cache
def _holidays(academic_year: int) -> frozenset[dt.date]:
    """Weekdays inside the instruction span with no school."""
    fall, spring = academic_year, academic_year + 1
    thanksgiving = _nth_weekday(fall, 11, 3, 4)
    spring_break = iso_week_start(dt.date(spring, 4, 10))
    days = {
        _nth_weekday(fall, 9, 0, 1),  # Labor Day
        _nth_weekday(spring, 1, 0, 3),  # Martin Luther King Jr. Day
        _nth_weekday(spring, 2, 0, 3),  # Presidents' Day
        _nth_weekday(spring, 5, 0, -1),  # Memorial Day
    }
    days |= {thanksgiving - dt.timedelta(days=n) for n in range(4)}
    days.add(thanksgiving + dt.timedelta(days=1))
    winter = dt.date(fall, 12, 22)
    days |= {winter + dt.timedelta(days=n) for n in range(12)}
    days |= {spring_break + dt.timedelta(days=n) for n in range(5)}
    return frozenset(days)


def _days(first: dt.date, last: dt.date) -> list[dt.date]:
    """Every calendar day from first to last, inclusive."""
    return [first + dt.timedelta(days=n) for n in range((last - first).days + 1)]


def is_school_day(day: dt.date, academic_year: int) -> bool:
    first, last = instruction_span(academic_year)
    return (
        first <= day <= last
        and day.weekday() < 5
        and day not in _holidays(academic_year)
    )


def realistic_years() -> list[int]:
    return list(
        range(TARGET_ACADEMIC_YEAR - REALISTIC_YEARS + 1, TARGET_ACADEMIC_YEAR + 1)
    )


@dataclass
class PlannedStudent:
    """One student, fixed by the grade they had in the year they arrived."""

    grade: int
    year: int
    region: int
    status: str = "Active"


@dataclass(frozen=True)
class PlannedStint:
    """One enrollment stint, before a school is chosen for it.

    `transfer` marks the second leg of a mid-year move: it starts at a
    different school from the leg before it.
    """

    student: int
    year: int
    grade: int
    entry: dt.date
    exit: dt.date
    year_in_network: int
    transfer: bool = False


def plan_enrollments(
    students_per_year: int, rng: random.Random
) -> tuple[list[PlannedStudent], list[PlannedStint]]:
    """Who is enrolled, in which grade, between which dates, each year.

    Students carry forward: a returning student is one grade higher, twelfth
    graders graduate, and a share leaves each year. Kindergartners and
    entrants at assorted grades refill the roster to the same size, so most
    students span two or three consecutive years with a grade step each
    time — which is what a year-over-year screen needs to show anything.

    Schools are chosen later, once dim_locations exists; nothing here needs
    one.
    """
    years = realistic_years()
    students: list[PlannedStudent] = []
    stints: list[PlannedStint] = []

    def admit(grade: int, year: int) -> int:
        region = rng.choices(range(_SCHOOL_REGIONS), weights=_SCHOOL_REGION_WEIGHTS)
        students.append(PlannedStudent(grade, year, region[0]))
        return len(students) - 1

    # student -> (grade, year in network), in admission order
    active: dict[int, tuple[int, int]] = {}
    for index in range(students_per_year):
        grade = index % 13
        active[admit(grade, years[0])] = (grade, rng.randint(1, grade + 1))
    late: set[int] = set()
    entrant_grades = list(range(1, 12))
    # KIPP's middle and high schools start at grades 5 and 9, so most
    # entrants above kindergarten arrive there.
    entrant_weights = [3 if grade in (5, 9) else 1 for grade in entrant_grades]

    for year in years:
        first, last = instruction_span(year)
        ids = list(active)
        movable = [s for s in ids if active[s][0] < 12]
        leavers = set(
            rng.sample(
                movable,
                min(
                    len(movable), max(1, round(students_per_year * REALISTIC_ATTRITION))
                ),
            )
        )
        staying = [s for s in ids if s not in leavers]
        transfers = set(
            rng.sample(
                staying,
                min(
                    len(staying),
                    max(1, round(students_per_year * REALISTIC_TRANSFER_SHARE)),
                ),
            )
        )
        early: set[int] = set()
        for student in ids:
            grade, network_years = active[student]
            entry = first
            if student in late:
                entry = _next_weekday(first + dt.timedelta(days=rng.randint(5, 120)))
            exit_ = last
            if student in leavers and rng.random() < REALISTIC_EARLY_EXIT_SHARE:
                early.add(student)
                room = max(31, (last - entry).days - 10)
                exit_ = _previous_weekday(
                    entry + dt.timedelta(days=rng.randint(30, room))
                )
            leg = PlannedStint(student, year, grade, entry, exit_, network_years)
            if student in transfers and (exit_ - entry).days > 90:
                split = _previous_weekday(
                    entry
                    + dt.timedelta(days=rng.randint(40, (exit_ - entry).days - 40))
                )
                resume = _next_weekday(split + dt.timedelta(days=rng.randint(3, 10)))
                stints.append(replace(leg, exit=split))
                stints.append(replace(leg, entry=resume, transfer=True))
            else:
                stints.append(leg)

        final = year == years[-1]
        for student in ids:
            grade, _ = active[student]
            if grade == 12 and not final:
                students[student].status = "Graduated"
            elif student in leavers and (student in early or not final):
                students[student].status = "Transferred Out"
        if final:
            break

        carried = {
            student: (grade + 1, network_years + 1)
            for student, (grade, network_years) in active.items()
            if grade < 12 and student not in leavers
        }
        kindergarten = max(1, round(students_per_year / 13))
        for _ in range(kindergarten):
            carried[admit(0, year + 1)] = (0, 1)
        late = set()
        for _ in range(max(0, students_per_year - len(carried))):
            grade = rng.choices(entrant_grades, weights=entrant_weights)[0]
            student = admit(grade, year + 1)
            carried[student] = (grade, 1)
            if rng.random() < REALISTIC_LATE_ENTRY_SHARE:
                late.add(student)
        active = carried

    return students, stints


# --------------------------------------------------------------------------
# The contract, read from the committed manifest
# --------------------------------------------------------------------------


def load_cells(path: Path = MANIFEST_PATH) -> list[dict[str, Any]]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cells = doc.get("cells") or []
    if not cells:
        raise ValueError(f"{path} declares no cells")
    return cells


def required_nulls(cells: list[dict[str, Any]]) -> set[tuple[str, str]]:
    """Columns the manifest requires at least one null row for.

    The generator reads the manifest rather than re-deriving the three
    exemptions (dbt `not_null`, join and surrogate keys, `access_policy`
    columns) from the model a second time. The manifest IS the generator's
    specification, and a second derivation is a second thing to drift.
    """
    return {(c["table"], c["column"]) for c in cells if c["kind"] == "null"}


def required_orphans(cells: list[dict[str, Any]]) -> set[tuple[str, str]]:
    return {(c["table"], c["column"]) for c in cells if c["kind"] == "orphan"}


# `staff_pii_scope` values whose policy ANDs a remit. `access.buildGroups`
# emits no group for them unless allowed_abbreviations AND
# allowed_department_groups both resolve non-empty, so a persona declaring one
# needs a staff_location_scope and staff_department_scope wide enough to
# resolve — otherwise its declared ROWS canary silently becomes a BLOCKED one.
# `personas.yml` declares both columns, so this is a check on the declaration,
# never a substitute for it: the generator used to fill the pair in itself,
# which made the persona file's silence on them survivable and hid that the
# declared set was two columns short.
REMIT_PII_SCOPES = frozenset(
    {"all_in_scope", "teaching_staff", "reporting_chain_or_below_rank"}
)


def needs_remit(person: Persona) -> bool:
    return person.scopes.get("staff_pii_scope") in REMIT_PII_SCOPES


def declares_remit(person: Persona, scopes: dict[str, set[str]]) -> bool:
    """Whether both remit axes name a value access.js resolves non-empty.

    `scopes` is `model.scope_values`, so "none" and a typo are both rejected
    for the same reason: neither is a `case` label in the helper's switch,
    and the helper's `default` branch returns [].
    """
    return all(
        person.scopes.get(column) in scopes.get(column, set())
        for column in ("staff_location_scope", "staff_department_scope")
    )


# --------------------------------------------------------------------------
# References the Cube model does not declare as joins
# --------------------------------------------------------------------------

# `model.join_paths` sees only equalities inside a cube `joins:` block. These
# columns are real references the model reads another way — `cube.js` resolves
# identity through them, or a compound join uses them as its second term — and
# a generator that invented their values would load cleanly and resolve
# nobody. Child -> parent, same direction as a JoinPath.
_EXTRA_FOREIGN_KEYS: dict[tuple[str, str], tuple[str, str]] = {
    ("dim_school_calendars", "date_key"): ("dim_dates", "date_key"),
    ("dim_school_calendars", "location_key"): ("dim_locations", "location_key"),
    ("dim_course_sections", "location_key"): ("dim_locations", "location_key"),
    ("dim_terms", "location_key"): ("dim_locations", "location_key"),
    # resolveAccess reads the row by google_email and then joins staff_key
    # onwards; an access row pointing at no staff member resolves to a person
    # the directory has never heard of.
    ("dim_staff_cube_access", "staff_key"): ("dim_staff", "staff_key"),
    # computeAllowedAbbreviations matches these against the locations
    # universe. A legal_entity_region_key or abbreviation that matches no
    # location resolves to an empty remit, which is a silent default-deny.
    ("dim_staff_cube_access", "legal_entity_region_key"): (
        "dim_regions",
        "region_key",
    ),
    ("dim_staff_cube_access", "location_abbreviation"): (
        "dim_locations",
        "abbreviation",
    ),
    ("dim_staff_reporting_chain", "manager_staff_key"): ("dim_staff", "staff_key"),
    ("dim_staff_reporting_chain", "reportee_staff_key"): ("dim_staff", "staff_key"),
    ("dim_staff_reporting_periods", "staff_key"): ("dim_staff", "staff_key"),
    ("dim_staff_reporting_periods", "manager_staff_key"): ("dim_staff", "staff_key"),
    # The Cube join is declared the other way round (the enrollment is the
    # child operand), but the enrollment key is the enrollment grain's own
    # primary key, so the status table is what follows it.
    ("dim_student_enrollment_status", "student_enrollment_key"): (
        "dim_student_enrollments",
        "student_enrollment_key",
    ),
    ("fct_student_attendance_enrollment_daily", "location_key"): (
        "dim_locations",
        "location_key",
    ),
}

# One spelling per category, always. Production carries unreconciled spellings
# from two source systems in some of these columns; the sandbox does not
# reproduce that, because it is a data-quality defect whose fix is a dbt
# ticket rather than kit code. Anything absent here gets a closed four-value
# domain named after its own column — benign, ugly, and impossible to mistake
# for a real value.
_CATEGORICAL: dict[str, list[str]] = {
    "race": ["Black or African American", "Hispanic/Latino", "White", "Asian"],
    "gender_identity": ["F", "M", "X"],
    "grade_band": ["ES", "MS", "HS"],
    "city": ["Newark", "Camden", "Miami", "Paterson"],
    "state": ["NJ", "FL"],
    "timezone": ["America/New_York"],
    "attendance_category": ["Present", "Absent Excused", "Absent Unexcused", "Tardy"],
    "attendance_code": ["P", "AE", "AU", "T"],
    "ada_tier": ["Tier 1", "Tier 2", "Tier 3", "Tier 4"],
    "period_type": ["year", "month", "week"],
    "enrollment_status": ["Active", "Inactive", "Transferred Out", "Graduated"],
    "meal_eligibility": ["Free", "Reduced", "Paid"],
    "iep_classification": ["Specific Learning Disability", "Other Health Impairment"],
    "special_education_placement": ["General Education", "Resource Room"],
    "proficiency_level": ["Below", "Approaching", "Meets", "Exceeds"],
    "academic_subject": ["Mathematics", "English Language Arts", "Science"],
    "credit_type": ["MATH", "ENG", "SCI"],
    "semester": ["S1", "S2"],
    "worker_type": ["Regular", "Temporary"],
    "status_name": ["Active", "Leave", "Terminated"],
    "department_name": ["Instruction", "Operations", "Talent", "Finance"],
    "business_unit_name": ["KIPP TEAM", "KIPP Cooper Norcross", "KIPP Miami"],
    "entity": ["KTAF", "KIPP NJ", "KIPP Miami"],
    "department_group": ["Instruction", "Operations", "Network Support"],
    # access.js branches on job_function_code IN ('TEACH', 'TIR') for the
    # teaching_staff PII tier, so both have to exist beside something else.
    "job_function_code": ["TEACH", "TIR", "OPS", "LEAD"],
    "administration_period": ["Fall", "Winter", "Spring"],
    "test_type": ["Summative", "Interim", "Diagnostic"],
    "module_type": ["Unit", "Benchmark"],
    "response_type": ["Overall Score", "Standard", "Subscore"],
}

_CATEGORICAL_BY_TABLE: dict[tuple[str, str], list[str]] = {
    # Incomparable by construction, so a cross-scope average announces its own
    # error: SAT at 400-1600 beside ACT at 1-36 pools to a number nobody can
    # read as plausible. No assertion catches that one — a person noticing
    # does.
    ("dim_assessments", "scope"): ["SAT", "ACT", "Star Reading", "iReady"],
    ("dim_assessments", "category"): ["College Entrance", "Internal", "Screener"],
    ("dim_assessments", "type"): ["Practice", "Official"],
    ("dim_terms", "type"): ["Quarter", "Semester", "Year"],
    ("dim_locations", "campus"): ["Newark", "Camden", "Miami", "Paterson"],
}

# Scale-score ranges per assessment scope. See the note on `scope` above.
_SCALE_RANGES: dict[str, tuple[int, int]] = {
    "SAT": (400, 1600),
    "ACT": (1, 36),
    "Star Reading": (0, 1400),
    "iReady": (100, 800),
}


class _Fabricator:
    """One seeded run: every table, in dependency order, in memory.

    Three passes per table, in this order and for this reason:

    1. `_special_<table>` writes the values this table decides for itself —
       the declared personas, a real calendar row, a grade-consistent birth
       date. Whatever it returns is PINNED: the foreign-key pass leaves it
       alone, because a persona written verbatim must stay verbatim.
    2. The foreign-key pass fills every remaining reference from rows already
       generated. Facts never invent a key.
    3. `_after_<table>` reconciles what only becomes knowable once the keys
       are assigned — the spine's third pass, a fact's cumulative counters,
       a score's scale range.

    Null planting runs last, and only on a column the manifest requires a
    null for and that does not already carry one.
    """

    def __init__(
        self,
        snap: dict[str, Any],
        people: list[Persona],
        scale: str,
        seed: int,
        cells: list[dict[str, Any]],
        cube_root: Path,
    ) -> None:
        self.columns: dict[str, dict[str, Any]] = snap["tables"]
        self.people = people
        self.scale = scale
        self.realistic = scale == "realistic"
        self.seed = seed
        self._plan: tuple[list[PlannedStudent], list[PlannedStint]] | None = None
        self._school_rows: list[dict[str, Any]] | None = None
        self._school_choices: dict[tuple[str, int], list[dict[str, Any]]] = {}
        self._school_of: dict[tuple[int, str], dict[str, Any]] = {}
        self._periods: list[dict[str, Any]] | None = None
        self._scores_per_stint: list[int] | None = None
        self.null_required = required_nulls(cells)
        self.orphan_required = required_orphans(cells)
        # Checked against, never filled from: see `_special_dim_staff_cube_access`.
        self.scopes = model.scope_values(cube_root / "access.js")

        self.tables = set(self.columns)
        primary = model.primary_key_columns(cube_root)
        self.fk: dict[tuple[str, str], list[tuple[str, str]]] = {}
        for path in model.join_paths(cube_root):
            child, parent = path.child, path.parent
            # A column that is its own table's primary key is generated, not
            # sampled: `dim_student_enrollments.student_enrollment_key` is the
            # child operand of two joins while being the enrollment grain's
            # own key, and sampling it from either would duplicate the key and
            # invert the grain. Dropping those edges is also what breaks the
            # spine cycle, at the same place `generation_order` breaks it.
            if child in primary or child[0] == parent[0]:
                continue
            if child[0] in self.tables and parent[0] in self.tables:
                self.fk.setdefault(child, []).append(parent)
        for child, parent in _EXTRA_FOREIGN_KEYS.items():
            if child[0] in self.tables and parent[0] in self.tables:
                self.fk.setdefault(child, []).append(parent)

        edges = {(c[0], p[0]) for c, parents in self.fk.items() for p in parents}
        self.order = generation_order(self.tables, edges)
        self.rank = {table: i for i, table in enumerate(self.order)}
        self.fk = {
            child: [p for p in parents if self.rank[p[0]] < self.rank[child[0]]]
            for child, parents in self.fk.items()
        }
        self.fk = {child: parents for child, parents in self.fk.items() if parents}

        self.rows: dict[str, list[dict[str, Any]]] = {}
        self.pinned: dict[tuple[str, str], set[int]] = {}
        # Values no child may reference: a planted orphan, and the identity
        # that must resolve to nothing.
        self.excluded: set[Any] = set()
        self._pools: dict[tuple[str, str], list[Any]] = {}

        self.persona_key = {
            person.email: surrogate_key("persona", i) for i, person in enumerate(people)
        }
        self.chain_edges = [
            (self.persona_key[person.email], self.persona_key[reportee])
            for person in people
            for reportee in person.reportees
            if reportee in self.persona_key
        ]
        # Leading rows each table reserves for declared content. The row right
        # after them carries the planted orphan, and null planting starts
        # after that — so nothing the manifest or personas.yml declares is
        # overwritten by a mechanical pass.
        self.head = {
            "dim_staff": len(people) + 1,  # + the unresolvable identity
            "dim_staff_cube_access": len(people),
            "dim_staff_reporting_chain": len(self.chain_edges),
            "dim_staff_work_history": len(people),
        }
        self.student_cohort: dict[str, tuple[int, int]] = {}
        self._taken_emails: set[str] = set()

        # A persona declaring no reportee must resolve an EMPTY chain, and
        # filler reporting-chain rows sample their manager from the same
        # staff pool the personas sit in — so without this every persona
        # ends up with a chain, `hasChain false` never occurs, and
        # shaquille.oquinn's BLOCKED canary quietly becomes a ROWS one.
        # That branch (reporting_chain with an empty chain) is the one
        # production cannot reach, so nothing else would catch the loss.
        self.column_forbidden: dict[tuple[str, str], set[Any]] = {
            ("dim_staff_reporting_chain", "manager_staff_key"): {
                self.persona_key[person.email]
                for person in people
                if not person.reportees
            },
            # dim_staff_cube_access is one row per staff member, and a filler
            # row draws its staff_key from the dim_staff pool — which every
            # persona is also in. Left alone, a filler adopts a persona's key
            # and that persona ends up with TWO access rows: the declared one
            # and a mechanical one whose scope columns hold placeholder
            # strings like "staff_pii_scope-1".
            #
            # resolveAccess reads one row. Which one it gets is arbitrary, and
            # a placeholder matches no enum, so the persona resolves to no
            # groups and default-denies. Observed on sheryl.swoopes, whose
            # entire purpose is full access, and ororo.munroe.
            #
            # Nothing else catches it. The canaries pass or fail on which row
            # BigQuery happened to return, so the suite goes green on one run
            # and red on the next with no code change between them.
            ("dim_staff_cube_access", "staff_key"): {
                self.persona_key[person.email] for person in people
            },
        }
        # The network office enrolls no students, as in production. Its staff
        # are network-scoped on student data precisely because their own
        # location resolves to no school, so a student row there would
        # describe an organisation that does not exist.
        office = surrogate_key("dim_locations.location_key", _OFFICE_LOCATION)
        for table in (
            "dim_student_enrollments",
            "fct_student_attendance_enrollment_daily",
            "dim_course_sections",
            "dim_school_calendars",
            "dim_terms",
        ):
            self.column_forbidden[(table, "location_key")] = {office}

        self.unique_fk: set[tuple[str, str]] = UNIQUE_FK

    # -- plumbing ---------------------------------------------------------

    def _head(self, table: str) -> int:
        return self.head.get(table, 0)

    def _count(self, table: str) -> int:
        """Rows for one table: the profile's target, or the plan's size.

        Under `realistic` the student tables, the calendar and the facts are
        as long as the enrollment plan makes them. Each such table keeps one
        leading row for its planted orphans, as every table does, and the
        enrollment table one trailing row as well (see
        `_shape_realistic_enrollments`).
        """
        if self.realistic:
            sizer = getattr(self, f"_realistic_count_{table}", None)
            if sizer is not None:
                return sizer()
        return row_target(table, self.scale)

    def _pin(self, table: str, column: str, index: int) -> None:
        self.pinned.setdefault((table, column), set()).add(index)

    def _referenceable(self, table: str) -> list[dict[str, Any]]:
        """Parent rows a child may reference.

        The LAST row is withheld from every child, which is what satisfies
        the parent side of each join path's orphan pair: a parent row no
        child references. Withholding one row costs nothing and removes the
        need for a separate parent-orphan fixture per path.
        """
        rows = self.rows[table]
        return rows[:-1] if len(rows) > 1 else rows

    def _pool(self, table: str, column: str) -> list[Any]:
        cached = self._pools.get((table, column))
        if cached is not None:
            return cached
        pool = [
            row[column]
            for row in self._referenceable(table)
            if row.get(column) is not None and row[column] not in self.excluded
        ]
        self._pools[(table, column)] = pool
        return pool

    def _orphan_value(self, table: str, column: str) -> Any:
        """A value shaped like the real thing that matches no parent row."""
        kind = self.columns[table][column]["type"]
        if kind == "DATE":
            # Outside the spine entirely, so no dim_dates row can carry it —
            # and offset per column, because two columns sharing one orphan
            # date are not orphans of each other. That is how the fact's
            # date_key and the school calendar's date_key, each planted with
            # a single shared sentinel, both passed against dim_dates and
            # neither against the other.
            digest = hashlib.blake2s(
                f"{table}.{column}".encode(), digest_size=2
            ).digest()
            return DATE_SPINE_START - dt.timedelta(days=1 + int.from_bytes(digest))
        if column.endswith("_key"):
            return surrogate_key(f"orphan:{table}.{column}", 0)
        return f"orphan-{column}"

    # -- value generation -------------------------------------------------

    def _typed(self, table: str, column: str, index: int, rng: random.Random) -> Any:
        kind = self.columns[table][column]["type"]
        if kind == "STRING":
            if column.endswith("_key"):
                return surrogate_key(f"{table}.{column}", index)
            domain = _CATEGORICAL_BY_TABLE.get((table, column)) or _CATEGORICAL.get(
                column
            )
            if domain is None:
                domain = [f"{column}-{n}" for n in range(1, 5)]
            # Cycled, not sampled: every value in the domain is present in
            # every run, which is what "saturate every column" means.
            return domain[index % len(domain)]
        if kind == "INT64":
            return index + 1
        if kind == "BOOL":
            return index % 2 == 0
        if kind == "FLOAT64":
            return round(rng.uniform(0.0, 1.0), 4)
        if kind == "NUMERIC":
            return (
                decimal.Decimal(rng.randint(0, 100_000))
                .scaleb(-2)
                .quantize(_NUMERIC_QUANTUM)
            )
        if kind == "DATE":
            return self._target_year_date(index)
        if kind == "TIMESTAMP":
            day = self._target_year_date(index)
            return dt.datetime(day.year, day.month, day.day, tzinfo=dt.UTC)
        nested = avro.struct_fields(kind)
        if nested is not None:
            # An empty array is the overwhelmingly common production value and
            # is also the safe one: `unionAdditionalGrants` folds each element
            # into the viewer's allowed set, so a fabricated grant WIDENS
            # access. Filler staff get none, and a persona that needs one
            # declares it in personas.yml where the widening is readable.
            return []
        raise ValueError(f"{table}.{column}: no fabrication rule for {kind}")

    def _target_year_date(self, index: int) -> dt.date:
        start = dt.date(TARGET_ACADEMIC_YEAR, 7, 1)
        return start + dt.timedelta(days=index % 365)

    # -- the run ----------------------------------------------------------

    def build(self) -> dict[str, list[dict[str, Any]]]:
        for table in self.order:
            count = self._count(table)
            # trunk-ignore(bandit/B311): fabricating rows, not keys
            rng = random.Random(f"{self.seed}:{table}")
            rows = self._base_rows(table, count, rng)
            self._assign_foreign_keys(table, rows)
            after = getattr(self, f"_after_{table}", None)
            if after is not None:
                after(rows, rng)
            self._plant_nulls(table, rows)
            self.rows[table] = rows
        self._place_region_teachers()
        return self.rows

    def _place_region_teachers(self) -> None:
        """Give every region-scoped persona a teacher inside its region.

        The teaching_staff policy keeps a staff row only when its location is
        in the viewer's region AND that staff member is coded TEACH or TIR.
        Nothing else guarantees both land together, and without them the
        persona's ROWS canary has nothing to find. Runs after null planting so
        no later pass can undo it.
        """
        access = {row["staff_key"]: row for row in self.rows["dim_staff_cube_access"]}
        locations = {row["location_key"]: row for row in self.rows["dim_locations"]}
        history = self.rows["dim_staff_work_history"]
        persona_keys = set(self.persona_key.values())
        head = self._head("dim_staff_work_history")

        def teaches(row: dict[str, Any]) -> bool:
            staff = access.get(row["staff_key"])
            return (
                staff is not None
                and staff["department_group"] is not None
                and staff["job_function_code"] in ("TEACH", "TIR")
            )

        for index, person in enumerate(self.people):
            if person.scopes.get("staff_location_scope") != "region":
                continue
            school = self._persona_school(index)
            region_key = school["region_key"]
            if any(
                teaches(row)
                and (loc := locations.get(row["work_location_key"]))
                and loc["region_key"] == region_key
                for row in history
            ):
                continue
            # Move one filler teacher. Skip the reserved rows and anyone whose
            # location is the null the manifest asked for.
            for row in history[head + 1 :]:
                if (
                    row["staff_key"] not in persona_keys
                    and row["staff_key"] not in self.excluded
                    and row["work_location_key"] is not None
                    and teaches(row)
                ):
                    row["work_location_key"] = school["location_key"]
                    break
            else:
                raise ValueError(
                    f"no filler teacher to place in {person.email}'s region"
                )

    def _base_rows(
        self, table: str, count: int, rng: random.Random
    ) -> list[dict[str, Any]]:
        special = getattr(self, f"_special_{table}", None)
        rows = []
        for index in range(count):
            declared = special(index, rng) if special is not None else {}
            row: dict[str, Any] = {}
            for column in self.columns[table]:
                if column in declared:
                    row[column] = declared[column]
                    self._pin(table, column, index)
                else:
                    row[column] = self._typed(table, column, index, rng)
            rows.append(row)
        return rows

    def _assign_foreign_keys(self, table: str, rows: list[dict[str, Any]]) -> None:
        for column in self.columns[table]:
            sources = self.fk.get((table, column))
            if not sources:
                continue
            # The latest-generated parent is the most constrained one: a
            # school calendar's date already came from dim_dates, so drawing
            # the fact's date from the calendar satisfies both join paths at
            # once, where drawing it from dim_dates would satisfy only one.
            parent = max(sources, key=lambda source: self.rank[source[0]])
            forbidden = self.column_forbidden.get((table, column))
            pool = self._pool(*parent)
            if forbidden:
                pool = [value for value in pool if value not in forbidden]
            if not pool:
                continue
            pinned = self.pinned.get((table, column), set())
            if (table, column) in self.unique_fk:
                # One row per parent, so the modulo below is wrong here: it
                # wraps once the pool runs out and hands the same parent to
                # two rows. On dim_staff_cube_access that is not a cosmetic
                # duplicate — resolveAccess reads ONE row per staff member,
                # so a second one makes which access a viewer resolves
                # arbitrary.
                #
                # Drop the rows the pool cannot cover rather than repeating a
                # value. A table with fewer rows than its target is honest; a
                # table that violates its own grain is not.
                free = [value for value in pool if value not in self.excluded]
                for index, row in enumerate(rows):
                    if index in pinned:
                        continue
                    offset = index - sum(1 for p in pinned if p < index)
                    row[column] = free[offset] if offset < len(free) else None
                rows[:] = [
                    row
                    for index, row in enumerate(rows)
                    if index in pinned or row[column] is not None
                ]
                continue
            for index, row in enumerate(rows):
                if index not in pinned:
                    row[column] = pool[index % len(pool)]

        head = self._head(table)
        for column in self.columns[table]:
            if (table, column) not in self.orphan_required:
                continue
            if not self.fk.get((table, column)):
                # This side of the pair is the PARENT. `_referenceable`
                # already withholds its last row from every child, so the
                # orphan exists without planting anything.
                continue
            value = self._orphan_value(table, column)
            rows[head][column] = value
            self.excluded.add(value)

    def _plant_nulls(self, table: str, rows: list[dict[str, Any]]) -> None:
        head = self._head(table)
        # head carries the planted orphan and the final row is the parent-side
        # orphan donor; leave both alone.
        span = len(rows) - head - 2
        for column in sorted(self.columns[table]):
            if (table, column) not in self.null_required:
                continue
            if any(row[column] is None for row in rows):
                continue
            if span < 1:
                raise ValueError(
                    f"{table} has too few rows to carry a null for {column}: "
                    f"{len(rows)} rows, {head} reserved"
                )
            digest = hashlib.blake2s(
                f"{table}.{column}".encode(), digest_size=4
            ).digest()
            rows[head + 1 + int.from_bytes(digest) % span][column] = None

    # -- per-table declared content ---------------------------------------

    def _person(self, index: int, rng: random.Random) -> tuple[str, str]:
        """A given name beside a coined surname.

        The first rows cycle the reserved given names in order rather than
        sampling them, so every character class the file declares — the
        apostrophe, the RTL script, the single character — is present in
        every run instead of being present on most seeds.
        """
        given_names = reserved_given_names()
        if index < len(given_names):
            surnames = reserved_surnames()
            return given_names[index]["name"], surnames[index % len(surnames)]
        return fabricate_name(rng)

    def _special_dim_dates(self, index: int, rng: random.Random) -> dict[str, Any]:
        day = spine_date(index)
        return {
            "date_key": day,
            "date_timestamp": dt.datetime(day.year, day.month, day.day, tzinfo=dt.UTC),
            "academic_year": academic_year_of(day),
            "fiscal_year": academic_year_of(day) + 1,
            "year_number": day.year,
            "month_number": day.month,
            "month_name": calendar.month_name[day.month],
            "day_of_month": day.day,
            "day_of_week": day.isoweekday(),
            "day_of_week_name": calendar.day_name[day.weekday()],
            "day_of_year": day.timetuple().tm_yday,
            "week_of_year": day.isocalendar().week,
            "quarter_number": (day.month - 1) // 3 + 1,
            "is_weekday": day.weekday() < 5,
            "is_current_academic_year": academic_year_of(day) == TARGET_ACADEMIC_YEAR,
            "calendar_week_start_date": iso_week_start(day),
            "calendar_week_end_date": iso_week_start(day) + dt.timedelta(days=6),
            "school_week_start_date": school_week_start(day),
            "school_week_end_date": school_week_end(day),
        }

    def _special_dim_regions(self, index: int, rng: random.Random) -> dict[str, Any]:
        if index < len(_REGIONS):
            region = _REGIONS[index]
            return {
                **region,
                "state": "FL" if region["name"].startswith("Miami") else "NJ",
                "timezone": "America/New_York",
            }
        if index == len(_REGIONS):
            # The manifest wants a null in each of these. Putting all of them
            # on one extra region keeps the five a kit shows fully named.
            return {"name": None, "state": None, "timezone": None}
        return {"name": "Unreferenced Region", "legal_entity": "Unreferenced"}

    def _location_region(self, index: int) -> int:
        """Which region a location row belongs to.

        One office row, and every other row spread over the school regions by
        `_SCHOOL_REGION_WEIGHTS`, so a region-scoped viewer sees several
        schools and the regions differ in size the way production's do.
        """
        if index == _OFFICE_LOCATION:
            return _OFFICE_REGION
        layout = getattr(self, "_school_layout", None)
        if layout is None:
            layout = weighted_cycle(
                _SCHOOL_REGION_WEIGHTS, row_target("dim_locations", self.scale)
            )
            self._school_layout = layout
        return layout[index]

    def _is_campus_row(self, index: int) -> bool:
        return index == _OFFICE_LOCATION or index % 8 == 0

    def _special_dim_locations(self, index: int, rng: random.Random) -> dict[str, Any]:
        region = self.rows["dim_regions"][self._location_region(index)]
        campus = self._is_campus_row(index)
        return {
            "abbreviation": f"SBX{index:03d}",
            "name": (
                "Sandbox Network Office"
                if index == _OFFICE_LOCATION
                else f"Sandbox {'Campus' if campus else 'School'} {index:03d}"
            ),
            "postal_code": f"0{7000 + index:04d}",
            "address": f"{100 + index} Fabricated Way",
            "region_key": region["region_key"],
            "is_campus": campus,
            "grade_band": None if campus else ["ES", "MS", "HS"][index % 3],
        }

    def _school_in_region(self, region_index: int, nth: int) -> dict[str, Any]:
        """A school (not a campus, office, or reserved row) in one region."""
        region_key = self.rows["dim_regions"][region_index]["region_key"]
        referenceable = self._referenceable("dim_locations")
        schools = [
            row
            for index, row in enumerate(referenceable)
            if index > 0
            and not self._is_campus_row(index)
            and row["region_key"] == region_key
            and row["abbreviation"] is not None
        ]
        if not schools:
            raise ValueError(f"region {region_index} has no school to place anyone in")
        return schools[nth % len(schools)]

    def _special_dim_staff(self, index: int, rng: random.Random) -> dict[str, Any]:
        people = self.people
        if index < len(people):
            person = people[index]
            given, surname = person.given_name, person.surname
            email = person.email
            key = self.persona_key[person.email]
        elif index == len(people):
            # The unresolvable identity: a real staff member with no
            # dim_staff_cube_access row, so resolveAccess finds nothing and
            # the viewer takes the clean default-deny path. Excluded from
            # every pool below so no access row can accidentally adopt it.
            given, surname = "Unresolvable", "Odinson"
            email = personas.UNRESOLVABLE
            key = surrogate_key("persona:unresolvable", 0)
            self.excluded.add(key)
        else:
            given, surname = self._person(index, rng)
            email = self._unique_email(given, surname, index)
            key = surrogate_key("dim_staff.staff_key", index)
        return {
            "staff_key": key,
            "first_name": given,
            "last_name": surname,
            "full_name": f"{given} {surname}",
            "google_email": email,
            "work_email": email,
            "personal_email": email.replace("@", ".personal@"),
            "active_directory_username": _fold(given) + _fold(surname)[:1],
            "personal_cell_phone": fabricate_phone(index),
            "staff_unique_id": reserved_identifier(index),
            "birth_date": dt.date(1970 + index % 35, 1 + index % 12, 1 + index % 28),
            "original_hire_date": dt.date(2015 + index % 10, 7, 1),
            "rehire_date": dt.date(2020 + index % 5, 7, 1),
        }

    def _unique_email(self, given: str, surname: str, index: int) -> str:
        address = to_ascii_email(given, surname)
        if address in self._taken_emails:
            local, _, domain = address.partition("@")
            address = f"{local}{index}@{domain}"
        self._taken_emails.add(address)
        return address

    def _special_dim_staff_cube_access(
        self, index: int, rng: random.Random
    ) -> dict[str, Any]:
        """The declared personas, verbatim, then ordinary staff.

        Personas are declared and not generated because `canaries.yml` names
        them: a seed-derived persona means changing the seed silently changes
        who the canaries test, and the suite stays green while testing
        something else. Every scope column comes from the declaration — none
        is chosen here — so a persona's resolved access is readable from
        `personas.yml` alone.
        """
        if index >= len(self.people):
            return {}
        person = self.people[index]
        if needs_remit(person) and not declares_remit(person, self.scopes):
            raise ValueError(
                f"{person.email} declares staff_pii_scope "
                f"{person.scopes.get('staff_pii_scope')!r}, whose policy ANDs "
                "the location ∩ department remit, but its "
                "staff_location_scope / staff_department_scope resolve empty "
                "— buildGroups would emit no staff-pii group and the persona "
                "would silently default-deny"
            )
        school = self._persona_school(index)
        return {
            "google_email": person.email,
            "staff_key": self.persona_key[person.email],
            **person.scopes,
            # Region and school agree, as they do for a real employee: a
            # region-scoped persona whose school sat in another region would
            # test a person who cannot exist.
            "legal_entity_region_key": school["region_key"],
            "location_abbreviation": school["abbreviation"],
            "job_function_code": "TEACH" if index % 2 else "LEAD",
            "job_function_level": 3 + index % 4,
        }

    def _persona_school(self, index: int) -> dict[str, Any]:
        return self._school_in_region(index % _SCHOOL_REGIONS, index // _SCHOOL_REGIONS)

    def _special_dim_staff_reporting_chain(
        self, index: int, rng: random.Random
    ) -> dict[str, Any]:
        """The declared reporting edges first, so hasChain resolves as declared.

        `ororo.munroe` and `karl-anthony.maximoff` declare a reportee and must
        resolve a non-empty chain; `shaquille.oquinn` declares none and
        must resolve an empty one, which is the no-group default-deny branch
        production cannot reach.
        """
        if index >= len(self.chain_edges):
            return {}
        manager, reportee = self.chain_edges[index]
        return {
            "manager_staff_key": manager,
            "reportee_staff_key": reportee,
            "depth": 1,
        }

    def _special_dim_staff_work_history(
        self, index: int, rng: random.Random
    ) -> dict[str, Any]:
        """One current position per persona, so the directory can see them."""
        if index >= len(self.people):
            return {}
        person = self.people[index]
        return {
            "staff_key": self.persona_key[person.email],
            "staff_work_history_key": surrogate_key("persona:work_history", index),
            "is_primary_position": True,
            "is_management_position": bool(person.reportees),
            "effective_start_date": dt.date(TARGET_ACADEMIC_YEAR, 7, 1),
            "effective_end_date": dt.date(TARGET_ACADEMIC_YEAR + 1, 6, 30),
            "job_code": "TEACH" if index % 2 else "LEAD",
            "full_time_equivalency": 1.0,
            "work_location_key": self._persona_school(index)["location_key"],
        }

    def _special_dim_students(self, index: int, rng: random.Random) -> dict[str, Any]:
        """Grade first, then a birth date inside that grade's window.

        The order matters: sampling a birth date independently produces
        fifth-graders born in 1998, and a kit that derives age from either
        field alone then disagrees with itself.
        """
        if self.realistic:
            return self._realistic_student(index, rng)
        grade = rng.randint(0, 12)
        given, surname = self._person(index, rng)
        key = surrogate_key("dim_students.student_key", index)
        self.student_cohort[key] = (grade, TARGET_ACADEMIC_YEAR)
        return {
            "student_key": key,
            "full_name": f"{given} {surname}",
            "birth_date": birth_date_for_grade(grade, TARGET_ACADEMIC_YEAR, rng),
            "lea_student_identifier": reserved_identifier(index),
            "state_student_identifier": str(reserved_identifier(index + 1000)),
            "district_student_identifier": str(reserved_identifier(index + 2000)),
            "salesforce_contact_id": f"003SBX{index:012d}",
        }

    def _realistic_student(self, index: int, rng: random.Random) -> dict[str, Any]:
        """A planned student, born to fit the grade they arrived in.

        One birth date serves every year the student appears, because the
        grade steps by one each year. The row after the plan is an applicant
        who never enrolled: the dim_students row no stint references.
        """
        students = self.plan[0]
        if index < len(students):
            planned = students[index]
            grade, year, status = planned.grade, planned.year, planned.status
        else:
            grade, year, status = rng.randint(0, 12), TARGET_ACADEMIC_YEAR, "Inactive"
        given, surname = self._person(index, rng)
        return {
            "student_key": self._student_key(index),
            "full_name": f"{given} {surname}",
            "birth_date": birth_date_for_grade(grade, year, rng),
            "enrollment_status": status,
            "lea_student_identifier": reserved_identifier(index),
            "state_student_identifier": str(reserved_identifier(index + 1_000_000)),
            "district_student_identifier": str(reserved_identifier(index + 2_000_000)),
            "salesforce_contact_id": f"003SBX{index:012d}",
        }

    @staticmethod
    def _student_key(index: int) -> str:
        return surrogate_key("dim_students.student_key", index)

    def _special_dim_student_section_enrollments(
        self, index: int, rng: random.Random
    ) -> dict[str, Any]:
        return {"is_homeroom": index % 3 == 0}

    # -- per-table reconciliation -----------------------------------------

    def _after_dim_course_sections(
        self, rows: list[dict[str, Any]], rng: random.Random
    ) -> None:
        if not self.realistic:
            return
        # Every school offers sections, so a student is scheduled into
        # sections at their own school.
        schools = self._schools()
        for index, row in enumerate(rows):
            row["location_key"] = schools[index % len(schools)]["location_key"]

    def _after_dim_school_calendars(
        self, rows: list[dict[str, Any]], rng: random.Random
    ) -> None:
        if not self.realistic:
            return
        cells = (
            (school["location_key"], day, year)
            for school in self._schools()
            for year in realistic_years()
            for day in _days(*calendar_span(year))
        )
        for row, (location, day, year) in zip(rows, cells, strict=True):
            in_session = is_school_day(day, year)
            row["location_key"] = location
            row["date_key"] = day
            row["is_in_session"] = in_session
            row["is_membership_day"] = in_session

    def _after_dim_student_enrollments(
        self, rows: list[dict[str, Any]], rng: random.Random
    ) -> None:
        if self.realistic:
            self._shape_realistic_enrollments(rows)
            return
        for row in rows:
            cohort = self.student_cohort.get(row["student_key"])
            if cohort is None:
                continue
            grade, year = cohort
            row["grade_level"] = grade
            row["academic_year"] = year
            row["graduation_year"] = year + (12 - grade) + 1
            row["year_in_network"] = max(1, grade)
            row["entry_date_key"] = dt.date(year, 8, 15)
            row["exit_date_key"] = dt.date(year + 1, 6, 15)

    def _after_dim_student_section_enrollments(
        self, rows: list[dict[str, Any]], rng: random.Random
    ) -> None:
        if self.realistic:
            self._shape_realistic_sections(rows)
        else:
            by_stint = {
                row["student_enrollment_key"]: row
                for row in self.rows["dim_student_enrollments"]
            }
            for row in rows:
                stint = by_stint.get(row["student_enrollment_key"])
                if stint is not None:
                    row["academic_year"] = stint["academic_year"]
                    row["entry_date"] = stint["entry_date_key"]
                    row["exit_date"] = stint["exit_date_key"]
        resolve_spine(self.rows["dim_student_enrollments"], rows, rng)

    def _after_fct_student_attendance_enrollment_daily(
        self, rows: list[dict[str, Any]], rng: random.Random
    ) -> None:
        """One coherent attendance day per row, then the cumulative counters.

        The cumulative columns are re-stamped on every daily row, exactly as
        the production fact does. That is what makes an unpinned date range
        count every student who crossed the threshold on any day rather than
        the students chronically absent as of a date — the first divergence
        the sandbox has to teach.
        """
        head = self._head("fct_student_attendance_enrollment_daily")
        if self.realistic:
            self._shape_realistic_daily(rows, head, rng)
            self._stamp_cumulative(rows, head)
            return
        stints = [
            row
            for row in self._referenceable("dim_student_enrollments")
            if row["student_enrollment_key"] not in self.excluded
        ]
        calendars = [
            row
            for row in self._referenceable("dim_school_calendars")
            if row["date_key"] not in self.excluded
        ]
        if not stints or not calendars:
            return
        by_location: dict[Any, list[dict[str, Any]]] = {}
        for row in calendars:
            by_location.setdefault(row["location_key"], []).append(row)

        for index, row in enumerate(rows):
            if index == head:
                continue  # the planted orphan keeps its unmatched keys
            # Skewed on purpose: an even round-robin gives every student the
            # same number of days, and a day-weighted rate then equals a
            # student-weighted one. The two attendance views differ precisely
            # because real students have very different day counts.
            stint = stints[
                min(len(stints) - 1, int(len(stints) * (index / len(rows)) ** 2))
            ]
            days = by_location.get(stint["location_key"]) or calendars
            day_row = days[index % len(days)]
            self._mark_day(row, stint, day_row, rng)

        self._stamp_cumulative(rows, head)

    def _mark_day(
        self,
        row: dict[str, Any],
        stint: dict[str, Any],
        day_row: dict[str, Any],
        rng: random.Random,
    ) -> None:
        """One student's attendance on one calendar row of their school."""
        day = day_row["date_key"]
        row["student_enrollment_key"] = stint["student_enrollment_key"]
        row["location_key"] = stint["location_key"]
        row["academic_year"] = stint["academic_year"]
        row["date_key"] = day
        row["week_start_monday"] = school_week_start(day)
        row["is_in_session_day"] = bool(day_row["is_in_session"])
        membership = 1.0 if day_row["is_membership_day"] else 0.0
        row["membership_value"] = membership
        rate = _stable_fraction(stint["student_enrollment_key"], 0.70, 0.99)
        present = membership > 0 and rng.random() < rate
        row["attendance_value"] = 1.0 if present else 0.0
        row["present_weight"] = membership
        row["is_absent"] = 0 if present else 1
        row["is_ontime"] = 1 if present else 0
        row["attendance_category"] = "Present" if present else "Absent Unexcused"
        row["attendance_code"] = "P" if present else "AU"

    def _stamp_cumulative(self, rows: list[dict[str, Any]], head: int) -> None:
        grouped: dict[Any, list[dict[str, Any]]] = {}
        for index, row in enumerate(rows):
            if index == head:
                continue
            grouped.setdefault(row["student_enrollment_key"], []).append(row)
        for key, group in grouped.items():
            group.sort(key=lambda row: row["date_key"])
            # The window each student is chronically absent in. Disjoint
            # across students, so an open range unions them all and a pinned
            # date sees one.
            start = int(_stable_fraction(key, 0.0, 0.8) * len(group))
            membership = present = 0.0
            for position, row in enumerate(group):
                membership += row["membership_value"]
                present += row["attendance_value"]
                row["n_membership_days_ytd"] = membership
                row["n_present_days_ytd"] = present
                chronic = start <= position < start + 2
                row["is_chronically_absent"] = chronic
                row["is_truant"] = chronic
                row["ada_tier"] = "Tier 3" if chronic else "Tier 1"

    def _after_fct_student_attendance_enrollment_periods(
        self, rows: list[dict[str, Any]], rng: random.Random
    ) -> None:
        """Period-end rows derived from the daily rows, not invented beside them.

        A student-weighted rate computed from numbers unrelated to the daily
        fact would diverge from the day-weighted one for the wrong reason.
        These are the same days, aggregated the other way — which is what
        makes the divergence a lesson rather than an artefact.
        """
        periods = self._derived_periods()
        if not periods:
            return
        head = self._head("fct_student_attendance_enrollment_periods")
        for index, row in enumerate(rows):
            if index == head:
                continue
            row.update(periods[index % len(periods)])
            row["period_start_membership_date_key"] = row["period_start_date_key"]
            row["student_period_key"] = surrogate_key(
                "fct_student_attendance_enrollment_periods", index
            )
            row["is_truant"] = row["is_chronically_absent"]

    def _derived_periods(self) -> list[dict[str, Any]]:
        """A year row and one row per school week, per stint in the daily fact."""
        if self._periods is not None:
            return self._periods
        daily = self.rows["fct_student_attendance_enrollment_daily"]
        by_stint: dict[Any, list[dict[str, Any]]] = {}
        for row in daily:
            by_stint.setdefault(row["student_enrollment_key"], []).append(row)

        periods: list[dict[str, Any]] = []
        for key, group in by_stint.items():
            group = sorted(group, key=lambda row: row["date_key"])
            last = group[-1]
            by_week: dict[dt.date, list[dict[str, Any]]] = {}
            for row in group:
                by_week.setdefault(school_week_start(row["date_key"]), []).append(row)
            periods.append(
                {
                    "student_enrollment_key": key,
                    "period_type": "year",
                    "period_start_date_key": group[0]["date_key"],
                    "period_end_date_key": last["date_key"],
                    "n_membership_days_ytd": last["n_membership_days_ytd"],
                    "n_present_days_ytd": last["n_present_days_ytd"],
                    "is_chronically_absent": any(
                        row["is_chronically_absent"] for row in group
                    ),
                    "academic_year": last["academic_year"],
                }
            )
            for week in sorted(by_week):
                in_week = by_week[week]
                periods.append(
                    {
                        "student_enrollment_key": key,
                        "period_type": "week",
                        "period_start_date_key": week,
                        "period_end_date_key": school_week_end(week),
                        "n_membership_days_ytd": in_week[-1]["n_membership_days_ytd"],
                        "n_present_days_ytd": in_week[-1]["n_present_days_ytd"],
                        "is_chronically_absent": in_week[-1]["is_chronically_absent"],
                        "academic_year": in_week[-1]["academic_year"],
                    }
                )
        self._periods = periods
        return periods

    def _after_fct_assessment_scores_enrollment_scoped(
        self, rows: list[dict[str, Any]], rng: random.Random
    ) -> None:
        """A scale score inside its own assessment's range.

        SAT at 400-1600 beside ACT at 1-36 is the point: a wrong cross-scope
        average produces a number nobody can read as plausible, which is the
        one failure no assertion catches.
        """
        if self.realistic:
            self._shape_realistic_scores(rows)
        scope_by_administration = {}
        assessments = {
            row["assessment_key"]: row for row in self.rows["dim_assessments"]
        }
        for row in self.rows["dim_assessment_administrations"]:
            assessment = assessments.get(row["assessment_key"])
            if assessment is not None:
                scope_by_administration[row["assessment_administration_key"]] = (
                    assessment["scope"]
                )
        for row in rows:
            scope = scope_by_administration.get(row["assessment_administration_key"])
            low, high = _SCALE_RANGES.get(scope or "", (0, 100))
            row["scale_score"] = decimal.Decimal(rng.randint(low, high)).quantize(
                _NUMERIC_QUANTUM
            )
            row["percent_correct"] = (
                decimal.Decimal(rng.randint(0, 10_000))
                .scaleb(-2)
                .quantize(_NUMERIC_QUANTUM)
            )

    # -- the realistic profile --------------------------------------------
    #
    # The plan decides every student-year before any row exists; the hooks
    # below lay it onto rows. Each shaped table keeps its row 0 for the
    # planted orphans, so coverage holds at this scale exactly as at `tiny`.

    @property
    def plan(self) -> tuple[list[PlannedStudent], list[PlannedStint]]:
        if self._plan is None:
            self._plan = plan_enrollments(
                REALISTIC_STUDENTS_PER_YEAR,
                # trunk-ignore(bandit/B311): fabricating rows, not keys
                random.Random(f"{self.seed}:enrollment-plan"),
            )
        return self._plan

    def _real_stints(self) -> list[dict[str, Any]]:
        """Enrollment rows the plan laid down, without the two fixture rows."""
        return self.rows["dim_student_enrollments"][1:-1]

    def _schools(self) -> list[dict[str, Any]]:
        """Locations a student can attend.

        A school with a grade band in one of the four school regions. Never
        the office or a campus row, never row 0 (its region is the planted
        orphan) and never the last row, which `_referenceable` withholds
        from every child.
        """
        if self._school_rows is not None:
            return self._school_rows
        region_of = {
            self.rows["dim_regions"][index]["region_key"]: index
            for index in range(_SCHOOL_REGIONS)
        }
        schools = []
        for index, row in enumerate(self._referenceable("dim_locations")):
            region = region_of.get(row["region_key"])
            if (
                index == 0
                or self._is_campus_row(index)
                or region is None
                or row["grade_band"] not in _GRADE_BANDS
            ):
                continue
            schools.append(row)
            self._school_choices.setdefault((row["grade_band"], region), []).append(row)
        if not schools:
            raise ValueError("dim_locations has no school a student could attend")
        self._school_rows = schools
        return schools

    def _school_for(self, stint: PlannedStint) -> dict[str, Any]:
        """The student's school for this stint's band, kept while in the band.

        A region with no school in the band (Paterson has no high school)
        sends the student to one in the largest region. A transfer leg moves
        the student to a different school of the same band, which then
        becomes their school.
        """
        self._schools()
        band = grade_band_of(stint.grade)
        mine = (stint.student, band)
        current = self._school_of.get(mine)
        if current is not None and not stint.transfer:
            return current
        largest = _SCHOOL_REGION_WEIGHTS.index(max(_SCHOOL_REGION_WEIGHTS))
        region = self.plan[0][stint.student].region
        candidates = self._school_choices.get(
            (band, region)
        ) or self._school_choices.get((band, largest), [])
        if stint.transfer:
            candidates = [row for row in candidates if row is not current] or [
                row
                for row in self._schools()
                if row["grade_band"] == band and row is not current
            ]
        if not candidates:
            raise ValueError(f"no {band} school for student {stint.student}")
        seed = (stint.student, band, stint.year if stint.transfer else None)
        pick = candidates[int(_stable_fraction(seed, 0, len(candidates)))]
        self._school_of[mine] = pick
        return pick

    def _realistic_count_dim_students(self) -> int:
        return len(self.plan[0]) + 1  # + the applicant no stint references

    def _realistic_count_dim_student_enrollments(self) -> int:
        return len(self.plan[1]) + 2  # + the orphan row and the null carrier

    def _realistic_count_dim_student_enrollment_status(self) -> int:
        return len(self.plan[1]) + 2

    def _realistic_count_dim_course_sections(self) -> int:
        return len(self._schools()) * REALISTIC_SECTIONS_PER_SCHOOL

    def _realistic_count_dim_school_calendars(self) -> int:
        days = sum(len(_days(*calendar_span(year))) for year in realistic_years())
        return len(self._schools()) * days

    def _realistic_count_dim_student_section_enrollments(self) -> int:
        return 1 + REALISTIC_SECTIONS_PER_STINT * len(self.plan[1])

    def _realistic_count_fct_student_attendance_enrollment_daily(self) -> int:
        return 1 + sum((stint.exit - stint.entry).days + 1 for stint in self.plan[1])

    def _realistic_count_fct_student_attendance_enrollment_periods(self) -> int:
        return 1 + len(self._derived_periods())

    def _realistic_count_fct_assessment_scores_enrollment_scoped(self) -> int:
        return 1 + sum(self._score_counts())

    def _score_counts(self) -> list[int]:
        if self._scores_per_stint is None:
            # trunk-ignore(bandit/B311): fabricating rows, not keys
            rng = random.Random(f"{self.seed}:scores-per-stint")
            self._scores_per_stint = [
                rng.randint(*REALISTIC_SCORES_PER_STINT) for _ in self.plan[1]
            ]
        return self._scores_per_stint

    def _shape_realistic_enrollments(self, rows: list[dict[str, Any]]) -> None:
        """One row per planned stint, between two fixture rows.

        Row 0 keeps the student and school orphans the foreign-key pass
        planted and copies the rest from a real stint. The last row, which
        `_referenceable` withholds from every child, carries every null the
        manifest requires of this table — so `_plant_nulls` finds them
        present and leaves the real stints whole, and every real stint's
        dates can drive its attendance rows.
        """
        for row, stint in zip(rows[1:-1], self.plan[1], strict=True):
            row.update(
                student_key=self._student_key(stint.student),
                location_key=self._school_for(stint)["location_key"],
                academic_year=stint.year,
                grade_level=stint.grade,
                graduation_year=stint.year + 12 - stint.grade + 1,
                year_in_network=stint.year_in_network,
                entry_date_key=stint.entry,
                exit_date_key=stint.exit,
                is_retained_year=False,
            )
        keys = ("student_enrollment_key", "student_key", "location_key")
        rows[0].update({k: v for k, v in rows[1].items() if k not in keys})
        tail = rows[-1]
        tail["student_key"] = rows[1]["student_key"]
        tail["location_key"] = rows[1]["location_key"]
        for column in self.columns["dim_student_enrollments"]:
            if ("dim_student_enrollments", column) in self.null_required:
                tail[column] = None

    def _shape_realistic_sections(self, rows: list[dict[str, Any]]) -> None:
        """A homeroom and the rest of a schedule, at the stint's own school."""
        offered: dict[Any, list[Any]] = {}
        for row in self._referenceable("dim_course_sections"):
            if row["location_key"] is not None:
                offered.setdefault(row["location_key"], []).append(
                    row["course_section_key"]
                )
        anywhere = self._pool("dim_course_sections", "course_section_key")
        stints = self._real_stints()
        for index, row in enumerate(rows[1:]):
            stint = stints[index // REALISTIC_SECTIONS_PER_STINT]
            slot = index % REALISTIC_SECTIONS_PER_STINT
            sections = offered.get(stint["location_key"]) or anywhere
            start = int(
                _stable_fraction(stint["student_enrollment_key"], 0, len(sections))
            )
            row.update(
                student_enrollment_key=stint["student_enrollment_key"],
                course_section_key=sections[(start + slot) % len(sections)],
                academic_year=stint["academic_year"],
                entry_date=stint["entry_date_key"],
                exit_date=stint["exit_date_key"],
                is_homeroom=slot == 0,
                is_current_section_enrollment=(
                    stint["academic_year"] == TARGET_ACADEMIC_YEAR
                ),
                is_dropped_course=False,
                is_dropped_section=False,
            )

    def _shape_realistic_daily(
        self, rows: list[dict[str, Any]], head: int, rng: random.Random
    ) -> None:
        """One row per stint per calendar day, entry to exit, weekends included.

        Each day reads its school's calendar row, so membership is zero on a
        weekend or a holiday. No attendance is taken on those days, so they
        are neither an absence nor a category.
        """
        calendar = {
            (row["location_key"], row["date_key"]): row
            for row in self.rows["dim_school_calendars"]
        }
        cursor = iter(rows[head + 1 :])
        for stint in self._real_stints():
            for day in _days(stint["entry_date_key"], stint["exit_date_key"]):
                row = next(cursor)
                self._mark_day(row, stint, calendar[(stint["location_key"], day)], rng)
                if not row["membership_value"]:
                    row["is_absent"] = 0
                    row["attendance_category"] = None
                    row["attendance_code"] = None

    def _shape_realistic_scores(self, rows: list[dict[str, Any]]) -> None:
        """A few scores per stint, spread evenly across its dates.

        Scored against a subject section rather than homeroom where the
        stint has one, as an assessment is.
        """
        sections: dict[Any, list[dict[str, Any]]] = {}
        for row in self._referenceable("dim_student_section_enrollments"):
            sections.setdefault(row["student_enrollment_key"], []).append(row)
        cursor = iter(rows[1:])
        for stint, count in zip(self._real_stints(), self._score_counts(), strict=True):
            entry, exit_ = stint["entry_date_key"], stint["exit_date_key"]
            taken = sections.get(stint["student_enrollment_key"], [])
            subjects = [row for row in taken if not row["is_homeroom"]] or taken
            span = (exit_ - entry).days
            for n in range(count):
                row = next(cursor)
                day = entry + dt.timedelta(days=span * (2 * n + 1) // (2 * count))
                day = max(entry, _previous_weekday(day))
                row["assessment_date_key"] = day
                row["test_date_key"] = day
                if subjects:
                    row["student_section_enrollment_key"] = subjects[n % len(subjects)][
                        "student_section_enrollment_key"
                    ]


def _stable_fraction(seed: Any, low: float, high: float) -> float:
    """A repeatable value in [low, high) derived from a key, not from an rng.

    Derived from the key so a student's attendance rate is the same in the
    daily fact and in anything computed from it later, whatever order the
    rows were visited in.
    """
    digest = hashlib.blake2s(str(seed).encode(), digest_size=4).digest()
    return low + (int.from_bytes(digest) / 2**32) * (high - low)


def generate(
    snap: dict[str, Any],
    people: list[Persona],
    scale: str = "tiny",
    seed: int = DEFAULT_SEED,
    *,
    cells: list[dict[str, Any]] | None = None,
    cube_root: Path = CUBE_ROOT,
) -> dict[str, list[dict[str, Any]]]:
    """Every sandbox table, as rows, from committed inputs alone.

    Deterministic: the same seed against the same commit produces the same
    rows. Nothing here reads production, and nothing here reads the network.
    """
    return _Fabricator(
        snap=snap,
        people=people,
        scale=scale,
        seed=seed,
        cells=cells if cells is not None else load_cells(),
        cube_root=cube_root,
    ).build()


def write(
    tables: dict[str, list[dict[str, Any]]],
    snap: dict[str, Any],
    out_dir: Path,
) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for table, rows in tables.items():
        path = out_dir / f"{table}.avro"
        avro.write(path, avro.avro_schema(table, snap["tables"][table]), rows)
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scale", choices=SCALES, default="tiny")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    snap = snapshot.load()
    people = personas.load(PERSONAS_PATH)
    tables = generate(snap, people, args.scale, args.seed)
    out_dir = args.out / args.scale
    written = write(tables, snap, out_dir)
    total = sum(len(rows) for rows in tables.values())
    print(f"wrote {len(written)} Avro files to {out_dir}: {total} rows")
    for table in sorted(tables):
        print(f"  {table}: {len(tables[table])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
