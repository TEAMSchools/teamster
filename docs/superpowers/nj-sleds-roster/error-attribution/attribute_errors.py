"""Attribute a bare NJSLEDS error count to specific handbook validation rules.

NJSLEDS has reduced its service level: it processes Course Roster uploads but
only generates detailed error information overnight. An upload therefore returns
a count with no detail. This tool evaluates the handbook's documented rules
against the file that was uploaded and works out which rule, or combination of
rules, accounts for that count.

Usage:
    uv run python attribute_errors.py FILE.csv --errors 23
    uv run python attribute_errors.py FILE.csv                  # counts only
    uv run python attribute_errors.py FILE.csv --rule STU-CREDITSEARNED-RANGE

The submission type is inferred from the header. Pass --submission to override.

Only handbook rules can explain a state error count, because only those are what
the state validates. Local KTAF expectations are reported separately and never
counted toward the target.
"""

from __future__ import annotations

import argparse
import csv
import importlib
import sys
from collections.abc import Sequence
from itertools import combinations
from pathlib import Path

from rules import Row, Rule

# Columns safe to print when drilling into a rule's violating rows. Names, dates
# of birth, and state IDs are deliberately excluded - the audit runbook's
# worklist convention identifies records by local IDs only.
SAFE_COLUMNS = {
    "staff": [
        "LocalStaffIdentifier",
        "StaffMemberIdentifier",
        "LocalSectionCode",
        "LocalCourseCode",
    ],
    "student": [
        "LocalIdentificationNumber",
        "LocalSectionCode",
        "LocalCourseCode",
    ],
}

# A header column unique to each submission, used to infer the type.
SIGNATURE = {"staff": "LocalStaffIdentifier", "student": "CreditsEarned"}

MAX_COMBINATION_SIZE = 3


def load_rows(path: Path) -> tuple[list[Row], list[str]]:
    """Read the upload file. utf-8-sig because the native exports carry a BOM."""
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        header = list(reader.fieldnames or [])
        return [dict(row) for row in reader], header


def infer_submission(header: Sequence[str]) -> str:
    for submission, column in SIGNATURE.items():
        if column in header:
            return submission
    raise SystemExit(
        "cannot infer submission type from the header; pass --submission "
        "staff or --submission student"
    )


def load_rules(submission: str) -> list[Rule]:
    module = importlib.import_module(f"rules_{submission}")
    return list(module.RULES)


def evaluate(rules: Sequence[Rule], rows: Sequence[Row]) -> dict[str, int]:
    """Count violations per rule id. Row predicates and file counts both."""
    counts: dict[str, int] = {}
    for rule in rules:
        if not rule.checkable:
            continue
        if rule.file_count is not None:
            counts[rule.id] = rule.file_count(rows)
        elif rule.predicate is not None:
            counts[rule.id] = sum(1 for row in rows if rule.predicate(row))
    return counts


def violating_rows(rule: Rule, rows: Sequence[Row]) -> list[Row]:
    if rule.predicate is None:
        return []
    return [row for row in rows if rule.predicate(row)]


def find_coextensive_rules(
    rules: Sequence[Rule], rows: Sequence[Row]
) -> list[tuple[tuple[str, ...], int]]:
    """Groups of rules that flag exactly the same rows.

    Some handbook statements describe one underlying condition from two sides.
    Entry-date-after-exit-date and exit-date-before-entry-date are the same
    comparison, stated once under each date element, so a single bad row fires
    both and contributes 2 to the error-instance total.

    But an identical row set has a second, quite different cause: several
    genuinely distinct conditions co-occurring on the same records, as a
    placeholder row with a bad name and a missing date of birth does. There the
    instance total is already correct.

    So this only detects the overlap and hands both readings to the caller; it
    does not adjust anything. `report` distinguishes the two by predicate
    identity - rules sharing one predicate object are certainly one condition -
    and offers an adjusted range only for that case. Detecting overlap from the
    data rather than hand-tagging known pairs means a pair nobody anticipated
    still surfaces, just without a claim attached.
    """
    signatures: dict[frozenset[int], list[str]] = {}
    for rule in rules:
        if not rule.checkable or rule.predicate is None:
            continue
        hits = frozenset(i for i, row in enumerate(rows) if rule.predicate(row))
        if not hits:
            continue
        signatures.setdefault(hits, []).append(rule.id)
    return [(tuple(ids), len(hits)) for hits, ids in signatures.items() if len(ids) > 1]


def rows_with_any_violation(rules: Sequence[Rule], rows: Sequence[Row]) -> int:
    """How many rows break at least one rule.

    This is the other reading of a bare count: the state may report one error
    per bad row rather than one per bad field.
    """
    row_rules = [r for r in rules if r.checkable and r.predicate is not None]
    return sum(1 for row in rows if any(r.predicate(row) for r in row_rules))


def find_explanations(counts: dict[str, int], target: int) -> list[tuple[str, ...]]:
    """Rule-id sets whose violation counts sum exactly to target.

    Ranked by fewest rules first, then by largest single contribution — one rule
    accounting for the whole count is a likelier explanation than several
    coincidentally summing to it.
    """
    candidates = {rid: n for rid, n in counts.items() if n > 0}
    found: list[tuple[str, ...]] = []
    for size in range(1, MAX_COMBINATION_SIZE + 1):
        for combo in combinations(sorted(candidates), size):
            if sum(candidates[rid] for rid in combo) == target:
                found.append(combo)
    found.sort(key=lambda combo: (len(combo), -max(candidates[r] for r in combo)))
    return found


def report(
    submission: str,
    path: Path,
    rows: Sequence[Row],
    rules: Sequence[Rule],
    counts: dict[str, int],
    target: int | None,
) -> None:
    by_id = {rule.id: rule for rule in rules}
    handbook = {rid: n for rid, n in counts.items() if by_id[rid].source == "handbook"}
    ktaf = {rid: n for rid, n in counts.items() if by_id[rid].source == "ktaf"}
    uncheckable = [r for r in rules if not r.checkable]

    print(f"file        : {path.name}")
    print(f"submission  : {submission}")
    print(f"rows        : {len(rows)}")
    print(
        f"rules       : {len(handbook)} handbook checkable, "
        f"{len(ktaf)} KTAF, {len(uncheckable)} not locally checkable"
    )
    print()

    instances = sum(handbook.values())
    bad_rows = rows_with_any_violation(
        [r for r in rules if r.source == "handbook"], rows
    )
    print("=== handbook rule violations ===")
    print()
    firing = {rid: n for rid, n in handbook.items() if n > 0}
    if not firing:
        print("  none - no handbook rule this tool can check is violated")
    for rid, count in sorted(firing.items(), key=lambda kv: -kv[1]):
        rule = by_id[rid]
        print(f"  {count:6}  {rid}")
        print(f"          {rule.element} (handbook p{rule.page})")
        print(f"          {rule.error_text}")
    print()
    print(f"  total error instances (one per violated field) : {instances}")
    print(f"  total rows with at least one violation         : {bad_rows}")
    print()

    handbook_rules = [r for r in rules if r.source == "handbook"]
    overlaps = find_coextensive_rules(handbook_rules, rows)
    if overlaps:
        by_id = {rule.id: rule for rule in rules}
        print("=== rules flagging identical row sets ===")
        print()
        print("  Each group below flags exactly the same rows. That has two very")
        print("  different possible causes, so check which before adjusting any")
        print("  total:")
        print()
        print("    - One condition stated twice. The handbook sometimes states")
        print("      the same test under two elements - entry-date-after-exit and")
        print("      exit-date-before-entry are one comparison. Then the instance")
        print("      total counts one defect more than once.")
        print("    - Distinct conditions that co-occur. A placeholder record with")
        print("      a bad name AND a missing date of birth breaks several real,")
        print("      separate rules. Then the total is correct as it stands.")
        print()
        for ids, hits in overlaps:
            shared = len({id(by_id[rid].predicate) for rid in ids}) == 1
            marker = (
                "same predicate - one condition"
                if shared
                else "distinct predicates - check whether these co-occur"
            )
            print(f"  {hits:6}  {', '.join(ids)}")
            print(f"          {marker}")
        print()
        definite = sum(
            (len(ids) - 1) * hits
            for ids, hits in overlaps
            if len({id(by_id[rid].predicate) for rid in ids}) == 1
        )
        if definite:
            print(
                f"  Groups sharing a predicate account for {definite} redundant "
                f"instance(s),"
            )
            print(f"  so the total reads as {instances - definite} to {instances}.")
            print()

    if ktaf:
        print("=== additional local findings, NOT state errors ===")
        print()
        print("  The state does not validate these; they cannot explain its count.")
        for rid, count in sorted(ktaf.items(), key=lambda kv: -kv[1]):
            if count:
                print(f"  {count:6}  {rid}  {by_id[rid].element}")
        print()

    if target is not None:
        attribute(target, instances, bad_rows, handbook, by_id, uncheckable)

    if uncheckable:
        print("=== rules this tool cannot check ===")
        print()
        print("  An unexplained residual most likely lives here.")
        for rule in uncheckable:
            print(f"  {rule.id}  ({rule.element}, p{rule.page})")
            print(f"      {rule.uncheckable_reason}")
        print()


def attribute(
    target: int,
    instances: int,
    bad_rows: int,
    handbook: dict[str, int],
    by_id: dict[str, Rule],
    uncheckable: Sequence[Rule],
) -> None:
    print(f"=== attributing the state's reported {target} errors ===")
    print()

    for label, total in (
        ("error instances", instances),
        ("error rows", bad_rows),
    ):
        if total == target:
            print(
                f"  EXACT MATCH on total {label}: everything this tool can "
                f"check accounts for all {target}."
            )
            print()

    explanations = find_explanations(handbook, target)
    if explanations:
        print(f"  Rule combinations summing exactly to {target}:")
        print()
        for combo in explanations[:10]:
            total = sum(handbook[rid] for rid in combo)
            parts = " + ".join(f"{rid} ({handbook[rid]})" for rid in combo)
            print(f"    {parts} = {total}")
            if len(combo) == 1:
                rule = by_id[combo[0]]
                print(f"      {rule.error_text}")
        if len(explanations) > 10:
            print(f"    ... and {len(explanations) - 10} more combinations")
        print()
        print("  Prefer the single-rule explanations. Several rules summing to the")
        print("  same total is often coincidence, not diagnosis.")
        print()
    else:
        print(
            f"  No combination of up to {MAX_COMBINATION_SIZE} checkable rules "
            f"sums to {target}."
        )
        print()

    if target > instances:
        print(
            f"  RESIDUAL: {target - instances} errors beyond what this tool "
            f"can account for."
        )
        print(
            f"  {len(uncheckable)} rules cannot be checked locally - see below. "
            "The residual"
        )
        print("  most likely lives there, or in a rule the handbook omits.")
        print()
    elif target < instances:
        print(
            f"  This tool finds {instances} violations but the state reported {target}."
        )
        print("  Likely causes: the state stops at the first error per row, or")
        print("  it does not enforce every documented rule. Compare against the")
        print(f"  {bad_rows} rows-with-a-violation figure.")
        print()

    print("  To confirm a hypothesis without waiting for overnight detail: fix")
    print("  the top candidate, re-upload, and check the count drops by exactly")
    print("  that rule's violation count. One cycle confirms or refutes it.")
    print()


def drill(rule: Rule, rows: Sequence[Row], submission: str) -> None:
    """Print local identifiers for a rule's violating rows. No names or DOBs."""
    if not rule.checkable:
        raise SystemExit(f"{rule.id} is not locally checkable")
    if rule.predicate is None:
        raise SystemExit(f"{rule.id} is file-scoped; there are no per-row hits")
    hits = violating_rows(rule, rows)
    columns = SAFE_COLUMNS[submission]
    print(f"{rule.id}: {len(hits)} violating row(s)")
    print(f"  {rule.error_text}")
    print()
    print("  " + ",".join(columns))
    for row in hits:
        print("  " + ",".join(str(row.get(c, "") or "") for c in columns))
    print()
    print("  Local identifiers only - names, dates of birth, and state IDs are")
    print("  deliberately omitted. Keep this output local.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path, help="the CSV that was uploaded")
    parser.add_argument(
        "--errors",
        type=int,
        default=None,
        help="the error count NJSLEDS reported for this upload",
    )
    parser.add_argument(
        "--submission",
        choices=sorted(SIGNATURE),
        default=None,
        help="override the submission type inferred from the header",
    )
    parser.add_argument(
        "--rule",
        default=None,
        help="print local identifiers for one rule's violating rows",
    )
    args = parser.parse_args()

    if not args.file.exists():
        raise SystemExit(f"no such file: {args.file}")

    rows, header = load_rows(args.file)
    submission = args.submission or infer_submission(header)
    rules = load_rules(submission)

    if args.rule:
        matching = [r for r in rules if r.id == args.rule]
        if not matching:
            raise SystemExit(f"unknown rule id: {args.rule}")
        drill(matching[0], rows, submission)
        return 0

    counts = evaluate(rules, rows)
    report(submission, args.file, rows, rules, counts, args.errors)
    return 0


if __name__ == "__main__":
    sys.exit(main())
