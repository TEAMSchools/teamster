"""Apply recorded decisions to the differences a run finds.

A decision quiets the groups it names only while the SQL on both sides is the
SQL it was made against. Pure: no I/O.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from .compare import Group
from .config import Decision


@dataclass
class Applied:
    open: list[Group] = field(default_factory=list)
    quiet: list[tuple[Decision, Group]] = field(default_factory=list)
    reconfirm: list[Decision] = field(default_factory=list)
    no_longer_needed: list[Decision] = field(default_factory=list)


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


def apply(
    decisions: list[Decision],
    groups: list[Group],
    fingerprints: dict[str, dict[str, str]],
) -> Applied:
    """Sort groups and decisions by what the recorded decisions still cover.

    Args:
        decisions: The recorded decisions.
        groups: The groups of differences this run found.
        fingerprints: Current SQL fingerprints per comparison id, as
            `{"cube": ..., "dashboard": ...}`.

    Returns:
        Groups still open or quieted, decisions to reconfirm because the SQL
        changed (their groups stay open), and decisions matching no group.

    Raises:
        ValueError: Two decisions claim the same group.
    """
    applied = Applied()
    claimed: dict[int, Decision] = {}

    for decision in decisions:
        current = fingerprints.get(decision.comparison) or {}
        if any(
            not decision.fingerprints.get(side)
            or not current.get(side)
            or decision.fingerprints[side] != current[side]
            for side in ("cube", "dashboard")
        ):
            applied.reconfirm.append(decision)
            continue

        column = decision.group.get("column")
        values = decision.group.get("values") or []
        matched = [
            i
            for i, g in enumerate(groups)
            if g.comparison_id == decision.comparison
            and g.column == column
            and g.value in values
        ]
        if not matched:
            applied.no_longer_needed.append(decision)
            continue
        for i in matched:
            if i in claimed:
                raise ValueError(
                    f"decisions {claimed[i].id!r} and {decision.id!r} both "
                    f"claim group {groups[i].column}={groups[i].value!r} "
                    f"in comparison {decision.comparison!r}"
                )
            claimed[i] = decision
            applied.quiet.append((decision, groups[i]))

    applied.open = [g for i, g in enumerate(groups) if i not in claimed]
    return applied
