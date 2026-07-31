"""Rule model and predicate helpers for NJSLEDS upload-error attribution.

NJSLEDS returns a bare error count on upload and only generates detailed error
information overnight. This package evaluates the handbook's documented
validation rules against the file that was uploaded so the count can be
attributed to specific rules the same day.

Two kinds of rule live here, and the distinction is load-bearing:

- **Handbook rules** (`source="handbook"`) transcribe an "An error will occur..."
  statement verbatim from a Course Roster handbook. Only these can explain a
  state error count, because only these are what the state actually validates.
- **KTAF rules** (`source="ktaf"`) encode a local expectation that the handbook
  does not impose - for example that a CDS code matches the specific combination
  KTAF reports under. These are useful for finding real problems but must never
  be counted toward a state error total, because the state does not check them.

`predicate` returns **True when the row VIOLATES the rule**. That polarity is
easy to invert by accident, so every predicate is named for the violation it
detects, not for the condition it requires.

## Reference values never come from the file under test

A KTAF rule needs a reference value - the CDS combination the region reports
under, the instructional-year window, the credit ceiling. Those come from the
data team, the handbook, or an authoritative directory. **Never from the file
being validated.**

This is not hypothetical. A first draft of the staff catalog found that Camden's
expected school code of 111 made its CDS rule fire on 100 percent of Camden
rows, applied the usual heuristic that a rule firing on every row has a bad
reference value, and substituted the 179 the file actually contained. But 179 is
the defect: the Alternate School Number is unset in PowerSchool School Setup, so
the extract falls back to a prefix of the internal school number. Every Camden
row genuinely is wrong, so 100 percent was the correct answer, and the
substitution would have reported a wholly non-compliant file as clean.

When a rule fires on everything, that is a hypothesis to check against an
authoritative source - not a licence to retune the rule until the file passes.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

Row = Mapping[str, str]

# SY 2025-26 instructional window, inclusive, as YYYYMMDD strings. Update each
# year to the actual first and last instructional days.
SY_START = "20250701"
SY_END = "20260630"


@dataclass(frozen=True)
class Rule:
    """One documented validation condition.

    id: stable identifier, prefix STU- or STF- for handbook rules and KTAF- for
        local expectations.
    element: the handbook data element the rule belongs to.
    page: handbook page the rule is stated on, for citation.
    error_text: the handbook's wording, verbatim. Never paraphrase - this is what
        the report quotes back to justify a hypothesis.
    checkable: whether the rule can be evaluated from the upload file alone.
    predicate: row-scoped test, True when the row violates the rule.
    file_count: file-scoped count, for rules about duplication across rows.
    uncheckable_reason: required when checkable is False. Says what external
        input the rule would need, so an unexplained residual points somewhere
        real instead of looking like a tool failure.
    """

    id: str
    element: str
    page: int
    error_text: str
    checkable: bool
    source: str = "handbook"
    predicate: Callable[[Row], bool] | None = None
    file_count: Callable[[Sequence[Row]], int] | None = None
    uncheckable_reason: str | None = None
    notes: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.source not in {"handbook", "ktaf"}:
            raise ValueError(f"{self.id}: source must be handbook or ktaf")
        if self.checkable and not (self.predicate or self.file_count):
            raise ValueError(f"{self.id}: checkable but has no predicate")
        if not self.checkable:
            if self.predicate or self.file_count:
                raise ValueError(f"{self.id}: not checkable but has a predicate")
            if not self.uncheckable_reason:
                raise ValueError(f"{self.id}: not checkable but gives no reason")
        if self.predicate and self.file_count:
            raise ValueError(f"{self.id}: give a row predicate or a file count")


# --------------------------------------------------------------------------- #
# Value helpers.
#
# Every helper treats None, "" and whitespace as blank, because a CSV read gives
# "" where BigQuery gives None and the rules must behave identically either way.
# --------------------------------------------------------------------------- #


def blank(value: str | None) -> bool:
    """True when the field carries no value."""
    return value is None or not str(value).strip()


def present(value: str | None) -> bool:
    """True when the field carries a value."""
    return not blank(value)


def matches(value: str | None, pattern: str) -> bool:
    """True when a populated value fully matches pattern. Blank never matches."""
    if blank(value):
        return False
    return re.fullmatch(pattern, str(value).strip()) is not None


def malformed(value: str | None, pattern: str) -> bool:
    """True when a populated value fails pattern.

    Use this rather than `not matches(...)` so a blank field does not also count
    as a format violation - blankness is its own rule, and double-counting one
    bad field as two errors corrupts the attribution arithmetic.
    """
    return present(value) and not matches(value, pattern)


def as_float(value: str | None) -> float | None:
    """Parse a numeric field, or None when blank or non-numeric."""
    if blank(value):
        return None
    try:
        return float(str(value).strip())
    except ValueError:
        return None


def is_date8(value: str | None) -> bool:
    """True when a populated value is a real calendar date in YYYYMMDD."""
    if not matches(value, r"\d{8}"):
        return False
    text = str(value).strip()
    year, month, day = int(text[:4]), int(text[4:6]), int(text[6:])
    if not 1 <= month <= 12:
        return False
    lengths = [31, 29 if _is_leap(year) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return 1 <= day <= lengths[month - 1]


def _is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def in_window(value: str | None, start: str = SY_START, end: str = SY_END) -> bool:
    """True when a populated YYYYMMDD value falls inside the window, inclusive."""
    return is_date8(value) and start <= str(value).strip() <= end


def duplicates_on(rows: Sequence[Row], keys: Sequence[str]) -> int:
    """Count rows whose key tuple appears more than once. Blank keys are skipped."""
    seen: dict[tuple[str, ...], int] = {}
    for row in rows:
        values = tuple(str(row.get(k, "") or "").strip() for k in keys)
        if any(not v for v in values):
            continue
        seen[values] = seen.get(values, 0) + 1
    return sum(count for count in seen.values() if count > 1)
