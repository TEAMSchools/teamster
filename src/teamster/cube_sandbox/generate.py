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


def row_target(table: str, scale: str) -> int:
    """Rows to generate for one table under a named profile."""
    if scale not in ("tiny", "full"):
        raise ValueError(f"unknown scale {scale!r}")
    if table == "dim_dates":
        return DATE_SPINE_MAX
    if scale == "tiny":
        return MANIFEST_FLOOR
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
    # universe. A region_key or abbreviation that matches no location resolves
    # to an empty remit, which is a silent default-deny.
    ("dim_staff_cube_access", "region_key"): ("dim_regions", "region_key"),
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
        self.seed = seed
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
        # shaquille.oneal's BLOCKED canary quietly becomes a ROWS one.
        # That branch (reporting_chain with an empty chain) is the one
        # production cannot reach, so nothing else would catch the loss.
        self.column_forbidden: dict[tuple[str, str], set[Any]] = {
            ("dim_staff_reporting_chain", "manager_staff_key"): {
                self.persona_key[person.email]
                for person in people
                if not person.reportees
            }
        }

    # -- plumbing ---------------------------------------------------------

    def _head(self, table: str) -> int:
        return self.head.get(table, 0)

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
        raise ValueError(f"{table}.{column}: no fabrication rule for {kind}")

    def _target_year_date(self, index: int) -> dt.date:
        start = dt.date(TARGET_ACADEMIC_YEAR, 7, 1)
        return start + dt.timedelta(days=index % 365)

    # -- the run ----------------------------------------------------------

    def build(self) -> dict[str, list[dict[str, Any]]]:
        for table in self.order:
            count = row_target(table, self.scale)
            # trunk-ignore(bandit/B311): fabricating rows, not keys
            rng = random.Random(f"{self.seed}:{table}")
            rows = self._base_rows(table, count, rng)
            self._assign_foreign_keys(table, rows)
            after = getattr(self, f"_after_{table}", None)
            if after is not None:
                after(rows, rng)
            self._plant_nulls(table, rows)
            self.rows[table] = rows
        return self.rows

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
        cities = ["Newark", "Camden", "Miami", "Paterson"]
        city = cities[index % len(cities)]
        return {
            "name": f"{city} Region {index // len(cities) + 1}",
            "state": "FL" if city == "Miami" else "NJ",
            "timezone": "America/New_York",
        }

    def _special_dim_locations(self, index: int, rng: random.Random) -> dict[str, Any]:
        return {
            "abbreviation": f"SBX{index:03d}",
            "name": f"Sandbox School {index:03d}",
            "postal_code": f"0{7000 + index:04d}",
            "address": f"{100 + index} Fabricated Way",
        }

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
        return {
            "google_email": person.email,
            "staff_key": self.persona_key[person.email],
            **person.scopes,
            "job_function_code": "TEACH" if index % 2 else "LEAD",
            "job_function_level": 3 + index % 4,
        }

    def _special_dim_staff_reporting_chain(
        self, index: int, rng: random.Random
    ) -> dict[str, Any]:
        """The declared reporting edges first, so hasChain resolves as declared.

        `ororo.munroe` and `karl-anthony.maximoff` declare a reportee and must
        resolve a non-empty chain; `shaquille.oneal` declares none and
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
        }

    def _special_dim_students(self, index: int, rng: random.Random) -> dict[str, Any]:
        """Grade first, then a birth date inside that grade's window.

        The order matters: sampling a birth date independently produces
        fifth-graders born in 1998, and a kit that derives age from either
        field alone then disagrees with itself.
        """
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

    def _special_dim_student_section_enrollments(
        self, index: int, rng: random.Random
    ) -> dict[str, Any]:
        return {"is_homeroom": index % 3 == 0}

    # -- per-table reconciliation -----------------------------------------

    def _after_dim_student_enrollments(
        self, rows: list[dict[str, Any]], rng: random.Random
    ) -> None:
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

        head = self._head("fct_student_attendance_enrollment_daily")
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
            row["student_enrollment_key"] = stint["student_enrollment_key"]
            row["location_key"] = stint["location_key"]
            row["academic_year"] = stint["academic_year"]
            days = by_location.get(stint["location_key"]) or calendars
            day_row = days[index % len(days)]
            day = day_row["date_key"]
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

        self._stamp_cumulative(rows, head)

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
        daily = self.rows["fct_student_attendance_enrollment_daily"]
        by_stint: dict[Any, list[dict[str, Any]]] = {}
        for row in daily:
            by_stint.setdefault(row["student_enrollment_key"], []).append(row)

        periods: list[dict[str, Any]] = []
        for key, group in by_stint.items():
            group = sorted(group, key=lambda row: row["date_key"])
            last = group[-1]
            weeks = sorted({school_week_start(row["date_key"]) for row in group})
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
            for week in weeks:
                in_week = [
                    row for row in group if school_week_start(row["date_key"]) == week
                ]
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

    def _after_fct_assessment_scores_enrollment_scoped(
        self, rows: list[dict[str, Any]], rng: random.Random
    ) -> None:
        """A scale score inside its own assessment's range.

        SAT at 400-1600 beside ACT at 1-36 is the point: a wrong cross-scope
        average produces a number nobody can read as plausible, which is the
        one failure no assertion catches.
        """
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
    parser.add_argument("--scale", choices=("tiny", "full"), default="tiny")
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
