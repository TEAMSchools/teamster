"""Fabricate the sandbox dataset.

Facts never invent a key: every foreign key is sampled from rows already
generated, which makes referential integrity hold by construction rather than
by a check afterwards.
"""

from __future__ import annotations

import calendar
import datetime as dt
import hashlib
import random
import unicodedata
from functools import cache
from pathlib import Path
from typing import Any

import yaml

SPINE_HEAD = "dim_student_enrollments"
SPINE_TAIL = "dim_student_section_enrollments"

SANDBOX_DOMAIN = "ktaf-sandbox.invalid"
NAMES_PATH = Path("src/cube/sandbox/reserved_names.yml")

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
    """
    by_stint: dict[str, list[dict[str, Any]]] = {}
    for row in sections:
        row["is_current_homeroom"] = False
        if row.get("is_homeroom"):
            by_stint.setdefault(row["student_enrollment_key"], []).append(row)

    for stint in enrollments:
        candidates = by_stint.get(stint["student_enrollment_key"], [])
        # Exactly one, or none. The homeroom join is one_to_one, so a second
        # current homeroom on one stint fans the attendance views out.
        if candidates and rng.random() >= unresolved_share:
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
