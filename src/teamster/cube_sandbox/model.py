"""Parse the Cube model for the facts the sandbox toolchain needs.

Nothing else in this package parses `src/cube/`. The table set in particular
is the union of two sources, and using either alone is wrong: most tables are
named in `sql_table:` on a cube YAML, but `cube.js` reads
`dim_staff_reporting_chain` directly (for reporting-chain identity
resolution) and that table appears in no cube YAML at all.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

_SQL_TABLE = re.compile(r"sql_table:\s*(?:['\"])?kipptaf_marts\.(\w+)")
_CUBE_JS_REF = re.compile(r"`kipptaf_marts\.(\w+)`")
_SCOPE_CASE = re.compile(r"case\s+[\"'](\w+)[\"']")
_SCOPE_TIER = re.compile(r"scope:\s*[\"'](\w+_scope)[\"']")
_STAFF_PII_SWITCH = re.compile(r"switch\s*\(\s*row\.staff_pii_scope\s*\)\s*\{")

# access.js's buildGroups emits `student-${row.student_location_scope}` — the
# scope value is interpolated into a template literal, not enumerated as a
# string literal, so it is not statically extractable by regex the way
# staff_pii_scope's `case "..."` branches are. A prior regex-based attempt at
# recovering these values from the template-literal text matched nothing and
# silently returned an empty set, which would make any consumer reject every
# valid student-location persona declaration. access.js is still the source
# of truth for the *domain* (see its buildGroups switch/if on
# student_location_scope and the "student-region / student-school /
# student-network" comment above it) — these three values are that domain,
# recorded here as a documented literal rather than derived unreliably.
_STUDENT_LOCATION_SCOPE_VALUES = frozenset({"region", "school", "network"})


def table_set(cube_root: Path) -> set[str]:
    """Every kipptaf_marts table the model reads, from both sources."""
    tables: set[str] = set()
    for path in (cube_root / "model").rglob("*.yml"):
        tables |= set(_SQL_TABLE.findall(path.read_text()))
    tables |= set(_CUBE_JS_REF.findall((cube_root / "cube.js").read_text()))
    return tables


def referenced_columns(cube_root: Path) -> dict[str, set[str]]:
    """Columns each table must carry, from every cube's dimensions and measures.

    A dimension's `sql:` may be an expression, so take every bare identifier in
    it. Over-collecting is safe here: a column named that does not exist fails
    the Task 9 check loudly, which is the outcome we want.
    """
    out: dict[str, set[str]] = {}
    for path in (cube_root / "model" / "cubes").rglob("*.yml"):
        doc = yaml.safe_load(path.read_text()) or {}
        for cube in doc.get("cubes", []):
            table = str(cube.get("sql_table", "")).split(".")[-1]
            if not table:
                continue
            names: set[str] = set()
            for member in (*cube.get("dimensions", []), *cube.get("measures", [])):
                names |= set(
                    re.findall(r"\b[a-z_][a-z0-9_]*\b", str(member.get("sql", "")))
                )
            out.setdefault(table, set()).update(names)
    return out


def _filter_members(filters: list) -> set[str]:
    """Every `member` named in a row_level filter list, at any nesting depth.

    A filter entry is either `{member: ..., operator: ..., values: ...}` or a
    combinator (`{or: [...]}` / `{and: [...]}`) wrapping more filter entries —
    see `staff_pii.yml`'s `staff-pii-reporting_chain_or_below_rank` policy,
    whose only path to `job_function_level` is inside an `or` → `and`. A
    shallow, top-level-only read misses it, which silently starves a Task 4
    persona of the column its policy actually gates on.
    """
    out: set[str] = set()
    for f in filters:
        if not isinstance(f, dict):
            continue
        if member := f.get("member"):
            out.add(str(member))
        for combinator in ("or", "and"):
            nested = f.get(combinator)
            if isinstance(nested, list):
                out |= _filter_members(nested)
    return out


def policy_columns(cube_root: Path) -> set[str]:
    """Every view member an access_policy row_level filter interpolates."""
    out: set[str] = set()
    for path in (cube_root / "model" / "views").rglob("*.yml"):
        doc = yaml.safe_load(path.read_text()) or {}
        for view in doc.get("views", []):
            for policy in view.get("access_policy", []):
                out |= _filter_members(policy.get("row_level", {}).get("filters", []))
    return out


def _balanced_block(text: str, open_brace_index: int) -> str:
    r"""The `{...}` block starting at `open_brace_index`, brace-depth matched.

    A plain non-greedy regex (`\{.*?\}`) stops at the FIRST `}`, which is
    wrong the moment the block contains its own nested braces — the
    `staff_pii_scope` switch does, in its `reporting_chain_or_below_rank`
    case's `if (...) { ... }`. Counting depth is what keeps this scoped to
    exactly the one switch statement, no more and no less.
    """
    depth = 0
    for i in range(open_brace_index, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[open_brace_index : i + 1]
    raise ValueError("unbalanced braces starting at the given index")


def _staff_pii_scope_values(text: str) -> set[str]:
    """The `case` labels of the switch that branches on `row.staff_pii_scope`.

    `_SCOPE_CASE` alone matches every `case "..."` in the whole file,
    including unrelated switches in `computeAllowedAbbreviations`
    (`network`/`region`/`school`) and `computeAllowedDepartmentGroups`
    (`all`/`own_group`) — values that are not, and never were, staff_pii_scope
    values. Bounding the search to the `switch (row.staff_pii_scope) { ... }`
    block itself (not just any `case` nearby) is what keeps those out.
    """
    match = _STAFF_PII_SWITCH.search(text)
    if not match:
        return set()
    block = _balanced_block(text, match.end() - 1)
    return set(_SCOPE_CASE.findall(block)) - {"none"}


def scope_values(access_js: Path) -> dict[str, set[str]]:
    """Scope enum values the code branches on, by scope column.

    Sourced from access.js because production is a subset of the domain the
    code handles — several policy branches have no production row.
    """
    text = access_js.read_text()
    tiers = set(_SCOPE_TIER.findall(text))
    out = {t: {"__non_none__"} for t in tiers}
    out["staff_pii_scope"] = _staff_pii_scope_values(text)
    # See _STUDENT_LOCATION_SCOPE_VALUES above: not derivable by regex from the
    # template-literal source, so this is a documented literal instead.
    out["student_location_scope"] = set(_STUDENT_LOCATION_SCOPE_VALUES)
    return {k: v for k, v in out.items() if v}
