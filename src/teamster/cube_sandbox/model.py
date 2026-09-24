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


def policy_columns(cube_root: Path) -> set[str]:
    """Every view member an access_policy row_level filter interpolates."""
    out: set[str] = set()
    for path in (cube_root / "model" / "views").rglob("*.yml"):
        doc = yaml.safe_load(path.read_text()) or {}
        for view in doc.get("views", []):
            for policy in view.get("access_policy", []):
                for f in policy.get("row_level", {}).get("filters", []):
                    if member := f.get("member"):
                        out.add(str(member))
    return out


def scope_values(access_js: Path) -> dict[str, set[str]]:
    """Scope enum values the code branches on, by scope column.

    Sourced from access.js because production is a subset of the domain the
    code handles — several policy branches have no production row.
    """
    text = access_js.read_text()
    tiers = set(_SCOPE_TIER.findall(text))
    branched = set(_SCOPE_CASE.findall(text))
    out = {t: {"__non_none__"} for t in tiers}
    out["staff_pii_scope"] = branched - {"none"}
    # See _STUDENT_LOCATION_SCOPE_VALUES above: not derivable by regex from the
    # template-literal source, so this is a documented literal instead.
    out["student_location_scope"] = set(_STUDENT_LOCATION_SCOPE_VALUES)
    return {k: v for k, v in out.items() if v}
