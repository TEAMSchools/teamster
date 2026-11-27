"""Bounded residual-parameter sweep for NJSLEDS error attribution.

Sometimes the checkable handbook rules explain fewer errors than the state
reported for an upload - the gap between "the rule counts add up to N" and
"the state said M" is the **residual**. A handful of this tool's own
parameters are not handbook facts; they are judgment calls the catalog had to
make where the handbook is silent or ambiguous (see `rules.py`'s module
docstring: the SY_START/SY_END window and the NAME_PATTERN character classes
are both flagged there as assumptions, not transcriptions). A wrong judgment
call could be why the residual exists. This module tests that, one parameter
at a time, against the residual the state already reported.

## Why this is not the Camden 111/179 mistake

`rules.py` documents an incident where a first draft retuned a KTAF reference
value - Camden's expected CDS school code - until the FILE passed, because the
rule fired on every row and firing on every row looked like a bad reference
value. It was not: the file was the defect, and the retune would have
reported a wholly non-compliant file as clean. That is fitting a parameter to
the artifact under test.

This module does the opposite. It fits a parameter to an INDEPENDENT number
that already exists before this tool runs: the error count NJSLEDS reported
for this specific upload. A candidate here only "matches" when it closes a
gap the state itself told us exists - not when it makes the file look
cleaner. Nothing here ever changes what counts as a violation in the real
rule catalog; every sweep is evaluated in this module's own throwaway
predicates, against `rows`, and thrown away when the process exits. A match
is a hypothesis to go confirm by fixing the record at source and
re-uploading - never a verdict.

## The four bounding constraints

1. One parameter at a time, never a cross-product. Searching combinations of
   parameters ("widen the window AND flip the band AND drop spaces sums to
   the residual") is numerology, not diagnosis, and the combinatorics
   explode. Every sweep function below varies exactly one parameter and
   holds everything else - including every other sweepable parameter - fixed
   at its current, shipped value.
2. Small, fixed candidate sets. Only the candidates enumerated per parameter
   below are ever evaluated - no continuous range (no day-by-day calendar
   sweep, no numeric threshold search).
3. Silent when there is nothing to explain. `report()` returns immediately if
   the residual it is given is not positive. Callers should only invoke it
   once they already know a residual exists (no `--errors`, or a target that
   the checkable rules already account for, both mean this module never
   runs).
4. Capped, honest output. At most `MAX_CANDIDATES_REPORTED` candidates print
   per parameter, and the closing summary states the total number of matches
   across every parameter swept - including zero. Zero matches is not a null
   result: it rules the swept parameters out and points the analyst at the
   rules this tool cannot check locally instead. Several matches is weak
   evidence, not a menu to pick from, and the summary says so plainly.

## Anti-patterns this module deliberately avoids

- Never modifies `SY_START`, `SY_END`, `NAME_PATTERN`, or any `Rule` in
  `rules.py` / `rules_staff.py` / `rules_student.py`. Every alternative is
  evaluated hypothetically, in this module's own local predicates.
- Never searches parameter combinations (constraint 1).
- Never generates a continuous candidate range (constraint 2).
- Never reports a matching candidate as a finding - only as something to
  confirm by fixing at source and re-uploading.
- Never sweeps anything on `NEVER_SWEEPABLE` below.
- No BigQuery, no `eval`/`exec`, no new third-party dependencies - file-only,
  same as the rest of this tool.

## What is never sweepable, and why

See `NEVER_SWEEPABLE`. If a future maintainer is tempted to add a parameter
to this module, that constant is where to check first.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from rules import NAME_PATTERN, SY_END, SY_START, Row, blank, is_date8, malformed

MAX_CANDIDATES_REPORTED = 5


@dataclass(frozen=True)
class ExcludedParameter:
    """One parameter this module will never sweep, and why."""

    name: str
    reason: str


# Hard exclusion list. These are handbook facts or authoritative external
# references, not judgment calls - sweeping them would be indistinguishable
# from tuning a value until the file passes, which is the mistake this whole
# module exists to avoid. See the module docstring's "Camden 111/179" section.
NEVER_SWEEPABLE: tuple[ExcludedParameter, ...] = (
    ExcludedParameter(
        name="KTAF CDS combinations (County/District/School triples)",
        reason=(
            "Sourced from the data team and the NJDOE directory, not from "
            "handbook ambiguity - see rules.py's module docstring for the "
            "Camden 111-vs-179 incident this guards against."
        ),
    ),
    ExcludedParameter(
        name="CourseLevel codes (B, G, E, H, X)",
        reason="Enumerated directly in the handbook's Acceptable Values; not ambiguous.",
    ),
    ExcludedParameter(
        name="AlphaGradeEarned values (18: A-F, each optionally with + or -)",
        reason="Enumerated directly in the handbook's Acceptable Values; not ambiguous.",
    ),
    ExcludedParameter(
        name="CompletionStatus values (P, F, W, I, NG)",
        reason="Enumerated directly in the handbook's Acceptable Values; not ambiguous.",
    ),
    ExcludedParameter(
        name="Credits / AvailableCredit numeric range (0.000-35.000)",
        reason="Stated explicitly in the handbook; not ambiguous.",
    ),
    ExcludedParameter(
        name="NumericGradeEarned numeric range (0-100)",
        reason="Stated explicitly in the handbook; not ambiguous.",
    ),
    ExcludedParameter(
        name=(
            "Field formats and lengths (8-digit SMID, 10-digit SID, "
            "2/4/3-digit CDS segments, YYYYMMDD dates, etc.)"
        ),
        reason="Stated explicitly in the handbook; not ambiguous.",
    ),
)


@dataclass(frozen=True)
class SweepCandidate:
    """One candidate value for one swept parameter.

    count: the violation count this candidate would produce.
    delta: count minus the count the CURRENT (shipped) value produces - this
        is what gets compared against the residual, not the raw count.
    is_match: whether delta exactly equals the residual being tested against.
    """

    label: str
    count: int
    delta: int
    is_match: bool


@dataclass(frozen=True)
class SweepSection:
    """All candidates swept for one parameter."""

    parameter: str
    candidates: list[SweepCandidate]


# --------------------------------------------------------------------------- #
# 1 & 2. School-year window start/end (SY_START / SY_END).
# --------------------------------------------------------------------------- #


def _valid_dates(rows: Sequence[Row], column: str) -> list[str]:
    values = (str(row.get(column) or "").strip() for row in rows)
    return [value for value in values if is_date8(value)]


def _earliest_present(rows: Sequence[Row], column: str) -> str | None:
    dates = _valid_dates(rows, column)
    return min(dates) if dates else None


def _latest_present(rows: Sequence[Row], columns: Sequence[str]) -> str | None:
    dates: list[str] = []
    for column in columns:
        dates.extend(_valid_dates(rows, column))
    return max(dates) if dates else None


def _count_before(rows: Sequence[Row], candidate: str) -> int:
    """Rows whose SectionEntryDate or SectionExitDate is a valid date earlier
    than `candidate`. One count per row (not per field) even if both dates
    qualify.
    """
    count = 0
    for row in rows:
        entry = row.get("SectionEntryDate")
        exit_ = row.get("SectionExitDate")
        entry_before = is_date8(entry) and str(entry).strip() < candidate
        exit_before = is_date8(exit_) and str(exit_).strip() < candidate
        if entry_before or exit_before:
            count += 1
    return count


def _count_after(rows: Sequence[Row], candidate: str) -> int:
    """Rows whose SectionEntryDate or SectionExitDate is a valid date later
    than `candidate`. One count per row, same reasoning as `_count_before`.
    """
    count = 0
    for row in rows:
        entry = row.get("SectionEntryDate")
        exit_ = row.get("SectionExitDate")
        entry_after = is_date8(entry) and str(entry).strip() > candidate
        exit_after = is_date8(exit_) and str(exit_).strip() > candidate
        if entry_after or exit_after:
            count += 1
    return count


def _sweep_date_window(
    rows: Sequence[Row],
    current: str,
    fixed_alternates: Sequence[str],
    dynamic_label: str,
    dynamic_value: str | None,
    count_fn: Callable[[Sequence[Row], str], int],
    residual: int,
) -> list[SweepCandidate]:
    entries: list[tuple[str, str]] = [(current, "current")]
    entries.extend((value, "candidate") for value in fixed_alternates)
    if dynamic_value is not None:
        entries.append((dynamic_value, dynamic_label))

    baseline_count = count_fn(rows, current)
    candidates: list[SweepCandidate] = []
    for value, label in entries:
        count = count_fn(rows, value)
        delta = count - baseline_count
        candidates.append(
            SweepCandidate(
                label=f"{value} ({label})",
                count=count,
                delta=delta,
                is_match=delta == residual,
            )
        )
    return candidates


def sweep_sy_start(rows: Sequence[Row], residual: int) -> list[SweepCandidate]:
    """Candidates: SY_START (current), 20250801, 20250901, and the earliest
    SectionEntryDate present in the file. Violations = rows whose
    SectionEntryDate or SectionExitDate falls before the candidate.
    """
    earliest = _earliest_present(rows, "SectionEntryDate")
    return _sweep_date_window(
        rows,
        current=SY_START,
        fixed_alternates=("20250801", "20250901"),
        dynamic_label="earliest SectionEntryDate present",
        dynamic_value=earliest,
        count_fn=_count_before,
        residual=residual,
    )


def sweep_sy_end(rows: Sequence[Row], residual: int) -> list[SweepCandidate]:
    """Candidates: SY_END (current), 20260601, 20260701, and the latest valid
    date present in the file across SectionEntryDate and SectionExitDate.
    Violations = rows whose SectionEntryDate or SectionExitDate falls after
    the candidate.
    """
    latest = _latest_present(rows, ("SectionEntryDate", "SectionExitDate"))
    return _sweep_date_window(
        rows,
        current=SY_END,
        fixed_alternates=("20260601", "20260701"),
        dynamic_label="latest date present",
        dynamic_value=latest,
        count_fn=_count_after,
        residual=residual,
    )


# --------------------------------------------------------------------------- #
# 3. Grade-span band threshold (student files only).
# --------------------------------------------------------------------------- #

# The handbook's "grade span of 060X or higher" (pp34-36, quoted verbatim in
# STU-GRADE-COMPLETION-REQUIRED) does not say which two-character half of a
# concatenated GradeSpan (e.g. "0810" = grade 08 through grade 10) is tested
# against the 06-12 band. KTAF-GRADE-COMPLETION-MISSING-HEURISTIC in
# rules_student.py reads it as the span START; this sweep tests the only other
# plausible reading, the span END, against the same 06-12 band. Two
# candidates only - this is not a range to search, it is one either/or
# question.
_GRADE_SPAN_BAND = frozenset({"06", "07", "08", "09", "10", "11", "12"})


def _grade_span_in_band(value: str | None, *, use_end_token: bool) -> bool:
    if blank(value):
        return False
    text = str(value).strip()
    token = text[2:4] if use_end_token else text[:2]
    return token in _GRADE_SPAN_BAND


def sweep_band_threshold(rows: Sequence[Row], residual: int) -> list[SweepCandidate]:
    """Candidates: span start in 06-12 (current reading), span end in 06-12
    (the alternative). Violations = rows that newly fall in scope for the
    grade-or-completion mandate under the alternative reading - i.e. rows
    where the end token is in-band but the start token is not.
    """
    newly_in_scope = sum(
        1
        for row in rows
        if _grade_span_in_band(row.get("GradeSpan"), use_end_token=True)
        and not _grade_span_in_band(row.get("GradeSpan"), use_end_token=False)
    )
    return [
        SweepCandidate(
            label="span start in 06-12 (current reading)",
            count=0,
            delta=0,
            is_match=0 == residual,
        ),
        SweepCandidate(
            label="span end in 06-12 (alternative reading)",
            count=newly_in_scope,
            delta=newly_in_scope,
            is_match=newly_in_scope == residual,
        ),
    ]


# --------------------------------------------------------------------------- #
# 4. Name pattern character classes.
# --------------------------------------------------------------------------- #

# Each is NAME_PATTERN (rules.py) with exactly one allowed character class
# removed, to test that class's toggle in isolation. These never replace
# NAME_PATTERN and are never written back to rules.py - see the module
# docstring.
_NAME_NO_SPACE = r"(?:[^\W\d_]|['‘’\-])+"
_NAME_NO_ACCENTED = r"(?:[A-Za-z]|[ '‘’\-])+"
_NAME_NO_TYPOGRAPHIC_APOSTROPHE = r"(?:[^\W\d_]|[ '’\-])+"

_NAME_TOGGLES: tuple[tuple[str, str], ...] = (
    ("disallow space", _NAME_NO_SPACE),
    ("disallow accented Latin letters", _NAME_NO_ACCENTED),
    ("disallow the typographic apostrophe (U+2018)", _NAME_NO_TYPOGRAPHIC_APOSTROPHE),
)


def _newly_flagged_name_rows(rows: Sequence[Row], alternate_pattern: str) -> int:
    """Rows where FirstName or LastName passes NAME_PATTERN today but would
    fail under `alternate_pattern` - i.e. would newly be flagged.
    """
    count = 0
    for row in rows:
        first = row.get("FirstName")
        last = row.get("LastName")
        newly_first = malformed(first, alternate_pattern) and not malformed(
            first, NAME_PATTERN
        )
        newly_last = malformed(last, alternate_pattern) and not malformed(
            last, NAME_PATTERN
        )
        if newly_first or newly_last:
            count += 1
    return count


def sweep_name_pattern(rows: Sequence[Row], residual: int) -> list[SweepCandidate]:
    """Three independent toggles, each evaluated alone against the current
    NAME_PATTERN baseline: disallow space, disallow accented Latin letters,
    disallow the typographic apostrophe. Violations = additional FirstName or
    LastName rows that would be flagged with that one character class
    removed.
    """
    candidates: list[SweepCandidate] = []
    for label, alternate_pattern in _NAME_TOGGLES:
        count = _newly_flagged_name_rows(rows, alternate_pattern)
        candidates.append(
            SweepCandidate(
                label=label, count=count, delta=count, is_match=count == residual
            )
        )
    return candidates


# --------------------------------------------------------------------------- #
# Orchestration and report.
# --------------------------------------------------------------------------- #


def _sections(
    rows: Sequence[Row], submission: str, residual: int
) -> list[SweepSection]:
    sections = [
        SweepSection(
            "school-year window start (SY_START)", sweep_sy_start(rows, residual)
        ),
        SweepSection("school-year window end (SY_END)", sweep_sy_end(rows, residual)),
    ]
    if submission == "student":
        sections.append(
            SweepSection(
                "grade-span band threshold (student files only)",
                sweep_band_threshold(rows, residual),
            )
        )
    sections.append(
        SweepSection(
            "name pattern character classes", sweep_name_pattern(rows, residual)
        )
    )
    return sections


def report(rows: Sequence[Row], submission: str, residual: int) -> None:
    """Print the residual sweep, or nothing at all if there is no residual to
    explain. Only call this from a branch that already knows `residual` is
    positive (see constraint 3 in the module docstring); the check below is
    defense in depth, not the primary gate.
    """
    if residual <= 0:
        return

    print("=== residual parameter sweep ===")
    print()
    print(
        "  Testing whether one of this tool's own assumed parameters (not a "
        "handbook fact) explains"
    )
    print(f"  the {residual} error(s) left unexplained by checkable handbook rules.")
    print(
        "  One parameter at a time, against the state's own reported count - "
        "never combined, never"
    )
    print("  tuned until the file passes. A match is a hypothesis to confirm by")
    print("  fixing at source and re-uploading, not a finding.")
    print()

    total_matches = 0
    for section in _sections(rows, submission, residual):
        print(f"  --- {section.parameter} ---")
        shown = section.candidates[:MAX_CANDIDATES_REPORTED]
        for candidate in shown:
            marker = "  <-- MATCHES RESIDUAL" if candidate.is_match else ""
            print(
                f"    {candidate.count:6}  delta {candidate.delta:+6}  "
                f"{candidate.label}{marker}"
            )
            if candidate.is_match:
                total_matches += 1
        hidden = len(section.candidates) - len(shown)
        if hidden:
            print(f"    ... and {hidden} more candidate(s) not shown")
        print()

    if total_matches == 0:
        print(f"  No swept candidate explains the residual of {residual}.")
        print(
            "  That rules out every parameter this tool can sweep - look at "
            "the rules this"
        )
        print(
            "  tool cannot check locally instead; the residual most likely lives there."
        )
    elif total_matches == 1:
        print(f"  1 candidate matches the residual of {residual}.")
        print(
            "  Confirm it by fixing the record at source and re-uploading - a "
            "match here is"
        )
        print("  a hypothesis, not a finding.")
    else:
        print(f"  {total_matches} candidates match the residual of {residual}.")
        print(
            "  Several matches is weak evidence, not a menu to choose from - "
            "confirm one at"
        )
        print("  a time by fixing at source and re-uploading.")
    print()
