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


def member_columns(sql: str) -> set[str]:
    """The columns ONE member's `sql:` reads from its own cube's table.

    A member's `sql:` carries three kinds of `{...}` reference, and only the
    first names a column on this cube's table:

    - `{CUBE}.column` / ``{CUBE}.`column` `` — this table's column. Keep it.
    - `{measure}` — another member of the SAME cube, by member name, as in
      ``1.0 * {_count_tier_3} / NULLIF({count_students}, 0)``. A member name
      is not a column.
    - `{other_cube.member}` — a member of a JOINED cube, as in
      `{students.student_key}`. It names no column on this table, and that
      cube's own dimensions already contribute it.

    Sweeping every bare identifier without stripping the last two is what
    made the Task 9 check report 30 columns that do not exist — among them
    `dim_student_attendance_enrollment_daily.count_students`, a measure, and
    `.students`, a cube. The check could never pass, so it could never catch
    the real thing it is for.

    SQL keywords and function names are excluded by the identifier pattern
    being lowercase-only: the model writes `CAST`, `NULLIF`, `CONCAT` and
    `IF` in upper case throughout.
    """
    columns = set(re.findall(r"\{CUBE\}\.`?([a-z_][a-z0-9_]*)`?", sql))
    bare = re.sub(r"\{[^}]*\}", " ", sql)
    return columns | set(re.findall(r"`?\b([a-z_][a-z0-9_]*)\b`?", bare))


def referenced_columns(cube_root: Path) -> dict[str, set[str]]:
    """Columns each table must carry, from every cube's dimensions and measures.

    A dimension's `sql:` may be an expression, so take every bare identifier
    left after the member references are resolved. Over-collecting what
    remains is safe: a column named that does not exist fails the Task 9
    check loudly, which is the outcome we want.
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
                names |= member_columns(str(member.get("sql", "")))
            out.setdefault(table, set()).update(names)
    return out


def _cubes(cube_root: Path) -> dict[str, dict]:
    """Every cube body in `model/cubes/`, keyed by its `name:`."""
    out: dict[str, dict] = {}
    for path in (cube_root / "model" / "cubes").rglob("*.yml"):
        doc = yaml.safe_load(path.read_text()) or {}
        for cube in doc.get("cubes", []):
            if name := cube.get("name"):
                out[str(name)] = cube
    return out


def _resolve(name: str, cubes: dict[str, dict]) -> tuple[str, dict[str, str]]:
    """A cube's table and its dimension-name -> column map, following `extends`.

    A role-play cube (`staff_lead_teacher`, `staff_manager`,
    `staff_homeroom_teacher`) is `extends: staff` with no `sql_table` and no
    dimensions of its own. A join's far side names one of those aliases, so
    reading `sql_table` off the named cube alone yields "" and drops the key.
    """
    seen: set[str] = set()
    table = ""
    dimensions: dict[str, str] = {}
    current: str | None = name
    while current and current in cubes and current not in seen:
        seen.add(current)
        cube = cubes[current]
        if not table:
            table = str(cube.get("sql_table", "")).split(".")[-1]
        for dim in cube.get("dimensions", []):
            # The nearest definition wins, so only fill what the alias lacks.
            dimensions.setdefault(str(dim.get("name")), str(dim.get("sql", "")))
        current = cube.get("extends")
    return table, dimensions


def _column_of(sql: str) -> str | None:
    """The bare column a dimension's `sql:` names, or None if it is an
    expression.

    A key is always a plain column reference. `CAST(entry_date AS TIMESTAMP)`
    and `{CUBE}.\\`type\\`` are not keys, and guessing a column out of an
    expression would invent an exemption rather than derive one.
    """
    text = sql.strip()
    return text if re.fullmatch(r"[a-z_][a-z0-9_]*", text) else None


def key_columns(cube_root: Path) -> set[tuple[str, str]]:
    """Join and surrogate keys, as (table, column).

    Derived structurally, never from the column's name. A name-suffix rule
    (`_key`/`_id`/`_identifier`/`_number`) also catches
    `state_student_identifier`, `district_student_identifier` and
    `lea_student_identifier` on `dim_students` — routinely null for a newly
    enrolled student, and exactly the case the sandbox exists to teach. Two
    structural sources instead: a dimension marked `primary_key: true`, and
    either side of a join's `sql:` predicate.
    """
    cubes = _cubes(cube_root)
    out: set[tuple[str, str]] = set()

    for name, cube in cubes.items():
        table, _ = _resolve(name, cubes)
        if not table:
            continue

        for dim in cube.get("dimensions", []):
            if dim.get("primary_key") and (column := _column_of(str(dim.get("sql")))):
                out.add((table, column))

        for join in cube.get("joins", []):
            sql = str(join.get("sql", ""))
            # `{CUBE}.<column>` — the near side, a column on this cube's table.
            for column in re.findall(r"\{CUBE\}\.([a-z_][a-z0-9_]*)", sql):
                out.add((table, column))
            # `{<cube>.<member>}` — the far side, a DIMENSION on another cube
            # that has to be resolved to that cube's own table and column.
            for other, member in re.findall(
                r"\{([a-z_][a-z0-9_]*)\.([a-z_][a-z0-9_]*)\}", sql
            ):
                other_table, other_dims = _resolve(other, cubes)
                column = _column_of(other_dims.get(member, ""))
                if other_table and column:
                    out.add((other_table, column))

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
