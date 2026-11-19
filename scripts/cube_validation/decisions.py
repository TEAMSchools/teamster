"""Apply recorded decisions to the differences a run finds.

A decision quiets the groups it names only while the SQL on both sides is the
SQL it was made against. A `group` decision names its groups by one column's
value. A `formula` decision names its comparison's formula difference: the
differing cells no unmatched row lies in, and those the formula check filed,
up to the count it recorded. A `cause` decision names an explained
cause, never a group: the latest triage, which re-runs every stored explanation,
says which items it decides (`sort.mark_decided`), so `apply` only checks
its SQL. A comparison decision (`all_groups`) names every row group of its
comparison that no `group` decision claims, and never cells. Pure: no I/O.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from dataclasses import dataclass, field

from .config import MATCHED_ONLY, Decision
from .reconcile import CellDiff, Gap, Group


@dataclass
class Applied:
    open: list[Group] = field(default_factory=list)
    quiet: list[tuple[Decision, Group]] = field(default_factory=list)
    reconfirm: list[Decision] = field(default_factory=list)
    no_longer_needed: list[Decision] = field(default_factory=list)
    # A decision some of whose values match no group, with those values.
    partly_stale: list[tuple[Decision, list[str]]] = field(default_factory=list)
    open_gaps: list[Gap] = field(default_factory=list)
    quiet_gaps: list[tuple[Decision, Gap]] = field(default_factory=list)
    open_cells: list[CellDiff] = field(default_factory=list)
    quiet_cells: list[tuple[Decision, CellDiff]] = field(default_factory=list)
    # Cause decisions whose SQL still holds; the triage says what they cover.
    causes: list[Decision] = field(default_factory=list)


_OPEN = re.compile(r"(?i:rb|br|r|b)?('''|\"\"\"|'|\"|`)")


def _span_end(sql: str, start: int, quote: str, raw: bool) -> int:
    """Return the index just past the quoted span whose body starts at `start`."""
    i, n = start, len(sql)
    while i < n:
        if sql[i] == "\\" and (quote == "`" or not raw):
            i += 2
        elif sql.startswith(quote, i):
            return i + len(quote)
        else:
            i += 1
    return n


def _normalize(sql: str) -> str:
    """Drop comments, collapse whitespace, lower-case outside quoted spans.

    Quoted strings (single, double, triple, raw) and backtick identifiers are
    kept byte-for-byte, with backslash escapes honored.
    """
    out: list[str] = []
    gap = False
    i, n = 0, len(sql)

    def emit(text: str) -> None:
        nonlocal gap
        if gap and out:
            out.append(" ")
        gap = False
        out.append(text)

    while i < n:
        prev_is_word = i > 0 and (sql[i - 1].isalnum() or sql[i - 1] == "_")
        m = None if prev_is_word else _OPEN.match(sql, i)
        if m:
            quote = m.group(1)
            prefix = m.group(0)[: -len(quote)]
            end = _span_end(sql, m.end(), quote, "r" in prefix.lower())
            emit(prefix.lower() + sql[m.end() - len(quote) : end])
            i = end
        elif sql.startswith("--", i):
            j = sql.find("\n", i)
            i = n if j == -1 else j
            gap = True
        elif sql.startswith("/*", i):
            j = sql.find("*/", i + 2)
            i = n if j == -1 else j + 2
            gap = True
        elif sql[i].isspace():
            gap = True
            i += 1
        else:
            emit(sql[i].lower())
            i += 1
    return "".join(out)


def sql_fingerprint(sql: str) -> str:
    """Hash SQL so cosmetic edits do not change it.

    Args:
        sql: A query.

    Returns:
        The sha256 hex digest of the query with comments removed, whitespace
        collapsed, and everything outside single-quoted literals lower-cased.
    """
    return hashlib.sha256(_normalize(sql).encode()).hexdigest()


def decisions_fingerprint(decisions: list[Decision]) -> str:
    """Hash a validation file's `decisions:` block as it was parsed.

    Comments and layout do not change it; any key or value does, except
    `task`, which is filled in after the review issue posts. `all_groups` is
    left out where false, so a file with no comparison decision hashes as it
    did before the key existed.

    Args:
        decisions: The file's decisions, in file order.

    Returns:
        The sha256 hex digest of the decisions as sorted-key JSON.
    """

    def fields(d: Decision) -> dict:
        out = {**dataclasses.asdict(d), "task": None}
        if not d.all_groups:
            del out["all_groups"]
        return out

    text = json.dumps([fields(d) for d in decisions], sort_keys=True, default=str)
    return hashlib.sha256(text.encode()).hexdigest()


def cause_state(d: Decision, proof: str, current: dict[str, str]) -> str:
    """Whether a cause decision still holds for an item explained by `proof`.

    Args:
        d: A cause decision.
        proof: The fingerprint of the stored explanation the item's cause
            rests on.
        current: The comparison's current `{cube, dashboard}` fingerprints.

    Returns:
        `holds`, `sql` (either side's SQL changed since the decision) or
        `proof` (the explanation file changed since the decision).
    """
    if any(
        not d.fingerprints.get(side) or d.fingerprints[side] != current.get(side)
        for side in ("cube", "dashboard")
    ):
        return "sql"
    if not d.fingerprints.get("explanation") or d.fingerprints["explanation"] != proof:
        return "proof"
    return "holds"


def _text(value: object) -> str:
    """A decision value as group text: `None` reads as empty, as NULL does."""
    return "" if value is None else str(value)


def _names(d: Decision, g: Group) -> bool:
    """A `group` decision's column holds one of its values in `g`."""
    values = {_text(v) for v in d.group.get("values") or []}
    return g.value_of(d.group.get("column") or "") in values


def _gap_of(decision: Decision) -> tuple[str, str] | None:
    if decision.missing_cut:
        return "cut", decision.missing_cut
    if decision.missing_filter:
        return "filter", decision.missing_filter
    return None


def apply(
    decisions: list[Decision],
    groups: list[Group],
    fingerprints: dict[str, dict[str, str]],
    gaps: list[Gap] | tuple[Gap, ...] = (),
    cell_diffs: list[CellDiff] | tuple[CellDiff, ...] = (),
) -> Applied:
    """Sort groups and decisions by what the recorded decisions still cover.

    Args:
        decisions: The recorded decisions.
        groups: The groups of differences this run found.
        fingerprints: Current SQL fingerprints per comparison id, as
            `{"cube": ..., "dashboard": ...}`.
        gaps: Sheet fields with no Cube member. A decision naming one by kind
            and field quiets it; it carries no fingerprints, because a re-run of
            `rebuild-sheet` rewrites the list it matches.
        cell_diffs: Each comparison's differing cells. A `formula` decision
            quiets its comparison's `formula` diff while both fingerprints
            hold and the formula check has filed no more cells in it than the
            decision recorded (`MATCHED_ONLY`); no decision quiets a `cells`
            diff, which coverage closes.

    Returns:
        Groups still open or quieted, decisions to reconfirm because the SQL
        changed or the formula check filed more cells (their groups or diff
        stay open), decisions matching no group, and decisions only some of
        whose values match a group, with the values that match none. The
        values that do match stay quiet.

    A comparison decision (`all_groups`) quiets, while both fingerprints
    hold, every group of its comparison no `group` decision names, stale or
    not (a stale one's groups stay open until it is re-confirmed); with none
    left it is no longer needed.

    Raises:
        ValueError: Two decisions claim the same group, the same
            comparison's formula difference, or (2 comparison decisions)
            the same comparison's row groups.
    """
    applied = Applied()
    claimed: dict[int, Decision] = {}
    gap_claims: dict[tuple[str, str], Decision] = {}
    formula_claims: dict[str, Decision] = {}
    # After every `group` decision, so each keeps its groups.
    whole: list[Decision] = []

    for decision in decisions:
        if decision.all_groups:
            whole.append(decision)
            continue
        if decision.cause:
            # Its own explanation stands in for the item's: here only the SQL, and
            # that it has an explanation at all, can fail.
            state = cause_state(
                decision,
                decision.fingerprints.get("explanation", ""),
                fingerprints.get(decision.comparison) or {},
            )
            (applied.causes if state == "holds" else applied.reconfirm).append(decision)
            continue
        if (named := _gap_of(decision)) is not None:
            gap = next((g for g in gaps if (g.kind, g.field) == named), None)
            if gap is None:
                applied.no_longer_needed.append(decision)
                continue
            if named in gap_claims:
                raise ValueError(
                    f"decisions {gap_claims[named].id!r} and {decision.id!r} both "
                    f"claim missing {named[0]} {named[1]!r}"
                )
            gap_claims[named] = decision
            applied.quiet_gaps.append((decision, gap))
            continue
        if decision.formula:
            # Refused whatever this run holds (stale SQL, no formula cells),
            # so a file never keeps 2 claims a later run would refuse.
            if decision.comparison in formula_claims:
                raise ValueError(
                    f"decisions {formula_claims[decision.comparison].id!r} and "
                    f"{decision.id!r} both claim the formula difference of "
                    f"{decision.comparison!r}"
                )
            formula_claims[decision.comparison] = decision
        current = fingerprints.get(decision.comparison) or {}
        if any(
            not decision.fingerprints.get(side)
            or not current.get(side)
            or decision.fingerprints[side] != current[side]
            for side in ("cube", "dashboard")
        ):
            applied.reconfirm.append(decision)
            continue

        if decision.formula:
            diff = next(
                (
                    d
                    for d in cell_diffs
                    if d.comparison_id == decision.comparison and d.kind == "formula"
                ),
                None,
            )
            if diff is None:
                applied.no_longer_needed.append(decision)
                continue
            # Cells the formula check filed since the decision was made were
            # never put to whoever made it: ask again.
            if diff.matched_only > int(decision.fingerprints.get(MATCHED_ONLY) or 0):
                applied.reconfirm.append(decision)
                continue
            applied.quiet_cells.append((decision, diff))
            continue

        column = decision.group.get("column")
        # A group's value is text; YAML reads an unquoted `9` as an int.
        values = list(
            dict.fromkeys(_text(v) for v in decision.group.get("values") or [])
        )
        # A decision on one column covers every row with that value, whatever
        # its other group-by columns hold.
        matched = [
            i
            for i, g in enumerate(groups)
            if g.comparison_id == decision.comparison
            and g.value_of(column or "") in values
        ]
        if not matched:
            applied.no_longer_needed.append(decision)
            continue
        for i in matched:
            if i in claimed:
                where = ", ".join(f"{k}={v!r}" for k, v in groups[i].dims)
                raise ValueError(
                    f"decisions {claimed[i].id!r} and {decision.id!r} both "
                    f"claim group {where or 'with no group-by'} "
                    f"in comparison {decision.comparison!r}"
                )
            claimed[i] = decision
            applied.quiet.append((decision, groups[i]))
        found = {groups[i].value_of(column or "") for i in matched}
        if missing := [v for v in values if v not in found]:
            applied.partly_stale.append((decision, missing))

    whole_claims: dict[str, Decision] = {}
    for decision in whole:
        # Refused whatever this run holds, like 2 formula decisions.
        if decision.comparison in whole_claims:
            raise ValueError(
                f"decisions {whole_claims[decision.comparison].id!r} and "
                f"{decision.id!r} both claim every open row group of "
                f"{decision.comparison!r}"
            )
        whole_claims[decision.comparison] = decision
        current = fingerprints.get(decision.comparison) or {}
        if any(
            not decision.fingerprints.get(side)
            or not current.get(side)
            or decision.fingerprints[side] != current[side]
            for side in ("cube", "dashboard")
        ):
            applied.reconfirm.append(decision)
            continue
        # A group a `group` decision names stays that decision's, stale or
        # not: open until it is re-confirmed, never this decision's call.
        named = [
            d
            for d in decisions
            if d.group and not d.cause and d.comparison == decision.comparison
        ]
        matched = [
            i
            for i, g in enumerate(groups)
            if g.comparison_id == decision.comparison
            and i not in claimed
            and not any(_names(d, g) for d in named)
        ]
        if not matched:
            applied.no_longer_needed.append(decision)
            continue
        for i in matched:
            claimed[i] = decision
            applied.quiet.append((decision, groups[i]))

    applied.open = [g for i, g in enumerate(groups) if i not in claimed]
    applied.open_gaps = [g for g in gaps if (g.kind, g.field) not in gap_claims]
    quiet = {id(d) for _, d in applied.quiet_cells}
    applied.open_cells = [d for d in cell_diffs if id(d) not in quiet]
    return applied
