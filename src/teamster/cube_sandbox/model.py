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
from typing import Any, NamedTuple

import yaml

_SQL_TABLE = re.compile(r"sql_table:\s*(?:['\"])?kipptaf_marts\.(\w+)")
_CUBE_JS_REF = re.compile(r"`kipptaf_marts\.(\w+)`")
_SCOPE_CASE = re.compile(r"case\s+[\"'](\w+)[\"']")
_SCOPE_TIER = re.compile(r"scope:\s*[\"'](\w+_scope)[\"']")
_STAFF_PII_SWITCH = re.compile(r"switch\s*\(\s*row\.staff_pii_scope\s*\)\s*\{")

# The two access.js helpers that take a scope column as a bare parameter.
# Named here, not their scope columns: the column each one carries is read
# off the cube.js call site by `_remit_scope_values`.
_REMIT_HELPERS = ("computeAllowedAbbreviations", "computeAllowedDepartmentGroups")

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


# A double-quoted JS string literal, escapes honored. `cube.js` writes every
# identity query as one such literal on one line, so nothing here has to
# understand JS concatenation.
_JS_STRING = re.compile(r'"((?:[^"\\\n]|\\.)*)"')
# The literal's shape: SELECT <list> FROM `kipptaf_marts.<table>` <tail>.
_JS_QUERY = re.compile(
    r"SELECT\s+(?:DISTINCT\s+)?(?P<select>.+?)\s+FROM\s+"
    r"`kipptaf_marts\.(?P<table>\w+)`(?P<tail>.*)",
    re.IGNORECASE | re.DOTALL,
)
_BIND_PARAM = re.compile(r"@\w+")
# Lowercase-only, like member_columns: the queries write every SQL keyword
# (SELECT, FROM, WHERE, IS, NOT, NULL, ORDER BY, LIMIT) in upper case, so a
# lowercase identifier in the tail is a column and nothing else.
_LOWER_IDENTIFIER = re.compile(r"`?\b([a-z_][a-z0-9_]*)\b`?")


def cube_js_columns(
    cube_root: Path, snap_tables: dict[str, Any]
) -> dict[str, set[str]]:
    """Columns `cube.js` reads directly, as table -> columns.

    `referenced_columns` sees only cube-YAML dimensions and measures, so
    everything the identity path reads was invisible to the coverage
    contract. Two consequences, both real:
    `dim_staff_reporting_chain` appears in no cube YAML at all and so got
    ZERO cells — an empty table passed coverage in full — and
    `dim_staff_cube_access` got cells for four of its fifteen columns,
    leaving `google_email`, the exact key `resolveAccess` matches, uncovered.

    `SELECT *` expands to every column the snapshot carries for that table,
    because that is what the query reads: `resolveAccess` hands the whole row
    to `access.buildSecurityContext`, so any column left empty in the sandbox
    is an empty niche on the identity path itself.

    `snap_tables` is the snapshot's `tables` mapping. Passing it rather than
    returning a `"*"` sentinel keeps the sentinel out of the manifest, where
    it would become a cell for a column named `*`.
    """
    text = (cube_root / "cube.js").read_text()
    out: dict[str, set[str]] = {}
    for literal in _JS_STRING.findall(text):
        match = _JS_QUERY.search(literal)
        if not match:
            continue
        table = match.group("table")
        columns: set[str] = set()
        for item in match.group("select").split(","):
            item = item.strip().strip("`")
            if item == "*":
                columns |= set(snap_tables.get(table, {}))
            elif re.fullmatch(r"[a-z_][a-z0-9_]*", item):
                columns.add(item)
        # WHERE / ORDER BY / LIMIT: the filtered and ordered columns are read
        # too, and a null one makes the identity resolve to nobody.
        tail = _BIND_PARAM.sub(" ", match.group("tail"))
        columns |= set(_LOWER_IDENTIFIER.findall(tail))
        out.setdefault(table, set()).update(columns)
    return out


def all_referenced_columns(
    cube_root: Path, snap_tables: dict[str, Any]
) -> dict[str, set[str]]:
    """Every column the model reads, from the cube YAML AND from `cube.js`.

    The union, for the same reason `table_set` is a union: either source
    alone leaves a hole, and the hole in the cube-YAML-only read was the
    whole identity path. Every consumer of the coverage contract reads this,
    not `referenced_columns`.
    """
    out = {
        table: set(columns) for table, columns in referenced_columns(cube_root).items()
    }
    for table, columns in cube_js_columns(cube_root, snap_tables).items():
        out.setdefault(table, set()).update(columns)
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


class _Resolved(NamedTuple):
    table: str
    dimensions: dict[str, str]
    joins: list[dict]


def _resolve(name: str, cubes: dict[str, dict]) -> _Resolved:
    """A cube's table, dimension-name -> column map and joins, via `extends`.

    A role-play cube (`staff_lead_teacher`, `staff_manager`,
    `staff_homeroom_teacher`) is `extends: staff` with no `sql_table` and no
    dimensions of its own. A join's far side names one of those aliases, so
    reading `sql_table` off the named cube alone yields "" and drops the key.

    Joins are inherited too. No alias extends a cube that declares joins
    today, so this changes nothing now — but inheriting dimensions and not
    joins would be an inconsistency waiting for the first alias that does.
    """
    seen: set[str] = set()
    table = ""
    dimensions: dict[str, str] = {}
    joins: list[dict] = []
    current: str | None = name
    while current and current in cubes and current not in seen:
        seen.add(current)
        cube = cubes[current]
        if not table:
            table = str(cube.get("sql_table", "")).split(".")[-1]
        for dim in cube.get("dimensions", []):
            # The nearest definition wins, so only fill what the alias lacks.
            dimensions.setdefault(str(dim.get("name")), str(dim.get("sql", "")))
        joins.extend(cube.get("joins", []))
        current = cube.get("extends")
    return _Resolved(table, dimensions, joins)


# A join operand: `{CUBE}.column`, optionally backticked, or `{cube.member}`.
_OPERAND = r"(?:\{CUBE\}\.`?[a-z_][a-z0-9_]*`?|\{[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*\})"
_EQUALITY = re.compile(rf"({_OPERAND})\s*=\s*({_OPERAND})")
_CUBE_COLUMN = re.compile(r"^\{CUBE\}\.`?([a-z_][a-z0-9_]*)`?$")
_FAR_MEMBER = re.compile(r"^\{([a-z_][a-z0-9_]*)\.([a-z_][a-z0-9_]*)\}$")


def _column_of(sql: str) -> str | None:
    """The bare column a dimension's `sql:` names, or None if it is an
    expression.

    A key is always a plain column reference, though it may be written
    `{CUBE}`-qualified or backticked — `.claude/rules/cube-authoring.md`
    tells authors to qualify any expression-bodied dimension whose column
    name also exists on a joined cube, and the model backticks reserved
    words. `CAST(entry_date AS TIMESTAMP)` is not a key, and guessing a
    column out of an expression would invent an exemption rather than derive
    one.
    """
    match = re.fullmatch(r"(?:\{CUBE\}\.)?`?([a-z_][a-z0-9_]*)`?", sql.strip())
    return match.group(1) if match else None


def primary_key_columns(cube_root: Path) -> set[tuple[str, str]]:
    """Each cube's OWN primary key, as (table, column).

    Split out of `key_columns`, which unions primary keys with every join
    operand and so cannot tell the two apart. The generator needs the
    distinction: a column that is its own table's primary key is generated,
    never sampled from a parent, even when a join declares it on the child
    side. `dim_student_enrollments.student_enrollment_key` is the child
    operand of two joins (onto the status table and onto the section table)
    while being the enrollment grain's own key — sampling it from either
    would duplicate the key and invert the grain.
    """
    cubes = _cubes(cube_root)
    out: set[tuple[str, str]] = set()
    for name, cube in cubes.items():
        resolved = _resolve(name, cubes)
        if not resolved.table:
            continue
        for dim in cube.get("dimensions", []):
            if dim.get("primary_key") and (column := _column_of(str(dim.get("sql")))):
                out.add((resolved.table, column))
    return out


def key_columns(cube_root: Path) -> set[tuple[str, str]]:
    """Join and surrogate keys, as (table, column).

    Derived structurally, never from the column's name. A name-suffix rule
    (`_key`/`_id`/`_identifier`/`_number`) also catches
    `state_student_identifier`, `district_student_identifier` and
    `lea_student_identifier` on `dim_students` — routinely null for a newly
    enrolled student, and exactly the case the sandbox exists to teach. Two
    structural sources instead: a dimension marked `primary_key: true`, and
    the operands of an EQUALITY in a join's `sql:` predicate.

    Only an equality. A join predicate can also carry a bare boolean term
    (`... AND {student_homeroom_section.is_current_homeroom}`) and a range
    bound (`{dates.date_key} BETWEEN {CUBE}.effective_start_date AND ...`).
    Those columns are ordinary attributes that happen to appear in a
    predicate, not the keys that link the rows, and exempting them is the
    same over-exemption the name-suffix rule was deleted for. Where such a
    column is never null in practice and carries no dbt `not_null` test,
    that is a missing test, and the sandbox nulling it is how the spec says
    to surface it.
    """
    cubes = _cubes(cube_root)
    out: set[tuple[str, str]] = primary_key_columns(cube_root)

    def operand(text: str, near_table: str) -> tuple[str, str] | None:
        if match := _CUBE_COLUMN.match(text):
            return (near_table, match.group(1))
        if match := _FAR_MEMBER.match(text):
            far = _resolve(match.group(1), cubes)
            column = _column_of(far.dimensions.get(match.group(2), ""))
            if far.table and column:
                return (far.table, column)
        return None

    for name in cubes:
        resolved = _resolve(name, cubes)
        if not resolved.table:
            continue

        for join in resolved.joins:
            for left, right in _EQUALITY.findall(str(join.get("sql", ""))):
                for side in (left, right):
                    if pair := operand(side, resolved.table):
                        out.add(pair)

    return out


class JoinPath(NamedTuple):
    """One equality linking a referencing table to a referenced one.

    `child` is the `{CUBE}` side — the table carrying the foreign key — and
    `parent` the joined cube's own key. `name` is stable, so a test or a
    fixture can reference the path rather than describing it.
    """

    child: tuple[str, str]
    parent: tuple[str, str]

    @property
    def name(self) -> str:
        return f"{self.child[0]}.{self.child[1]}->{self.parent[0]}.{self.parent[1]}"


def join_paths(cube_root: Path) -> list[JoinPath]:
    """Every join equality in the model, as child -> parent column pairs.

    The manifest needs these to require an orphan on each side of each path.
    A join path with no orphan is an empty niche: a kit that assumes every
    foreign key resolves passes against the sandbox and breaks on production,
    where `dim_student_enrollments.location_key` is documented NULL for
    grade_level 99 placeholder schools and
    `dim_staff_work_history.work_location_key` NULL for an unmapped ADP
    location.
    """
    cubes = _cubes(cube_root)
    out: dict[str, JoinPath] = {}

    for name in cubes:
        resolved = _resolve(name, cubes)
        if not resolved.table:
            continue
        for join in resolved.joins:
            for left, right in _EQUALITY.findall(str(join.get("sql", ""))):
                near = [s for s in (left, right) if _CUBE_COLUMN.match(s)]
                far = [s for s in (left, right) if _FAR_MEMBER.match(s)]
                if len(near) != 1 or len(far) != 1:
                    continue
                child_column = _CUBE_COLUMN.match(near[0]).group(1)  # type: ignore[union-attr]
                far_match = _FAR_MEMBER.match(far[0])
                far_cube = _resolve(far_match.group(1), cubes)  # type: ignore[union-attr]
                parent_column = _column_of(
                    far_cube.dimensions.get(far_match.group(2), "")  # type: ignore[union-attr]
                )
                if not far_cube.table or not parent_column:
                    continue
                path = JoinPath(
                    child=(resolved.table, child_column),
                    parent=(far_cube.table, parent_column),
                )
                # Role-play aliases resolve to the same underlying pair, so
                # dedupe on the name rather than emitting a path twice.
                out.setdefault(path.name, path)

    return [out[k] for k in sorted(out)]


def view_member_columns(cube_root: Path) -> dict[str, tuple[str, str]]:
    """Each view member's exposed name -> the (table, column) behind it.

    A view member's exposed name follows the `prefix:` setting on the
    `includes:` block that surfaces it: `prefix: true` gives
    `<last join_path segment>_<member>`, anything else leaves it bare. So
    `locations_abbreviation` and a bare `abbreviation` can both mean
    `dim_locations.abbreviation`, and a bare `staff_key` means
    `dim_staff.staff_key` and nothing else.
    """
    cubes = _cubes(cube_root)
    out: dict[str, tuple[str, str]] = {}
    for path in (cube_root / "model" / "views").rglob("*.yml"):
        doc = yaml.safe_load(path.read_text()) or {}
        for view in doc.get("views", []):
            for block in view.get("cubes", []):
                segment = str(block.get("join_path", "")).split(".")[-1]
                resolved = _resolve(segment, cubes)
                includes = block.get("includes")
                if not resolved.table or not isinstance(includes, list):
                    continue
                for member in includes:
                    exposed = (
                        f"{segment}_{member}" if block.get("prefix") else str(member)
                    )
                    if column := _column_of(resolved.dimensions.get(str(member), "")):
                        out[exposed] = (resolved.table, column)
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


def policy_members(cube_root: Path) -> set[str]:
    """Every view member an access_policy row_level filter interpolates."""
    out: set[str] = set()
    for path in (cube_root / "model" / "views").rglob("*.yml"):
        doc = yaml.safe_load(path.read_text()) or {}
        for view in doc.get("views", []):
            for policy in view.get("access_policy", []):
                out |= _filter_members(policy.get("row_level", {}).get("filters", []))
    return out


def policy_columns(cube_root: Path) -> set[tuple[str, str]]:
    """The (table, column) behind every access_policy row_level filter.

    Resolved through the view's own `includes:` blocks rather than left as a
    bare member name. A bare name exempts the column on EVERY table that
    happens to carry it — `dim_staff_reporting_periods.staff_key` was exempt
    only because the string `staff_key` is a policy member on `staff_pii`,
    where it means `dim_staff.staff_key`. It also leaves the prefixed names
    (`locations_abbreviation`) matching no warehouse column at all, so the
    exemption they were meant to grant never applied. A name is not a
    contract here either.
    """
    lookup = view_member_columns(cube_root)
    return {lookup[m] for m in policy_members(cube_root) if m in lookup}


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


def _function_body(text: str, name: str) -> str:
    """The brace-matched body of `function <name>(...) { ... }`."""
    match = re.search(rf"function\s+{re.escape(name)}\s*\([^)]*\)\s*\{{", text)
    if not match:
        raise ValueError(f"access.js declares no function {name}")
    return _balanced_block(text, match.end() - 1)


def _remit_scope_values(access_text: str, cube_text: str) -> dict[str, set[str]]:
    """The two remit scopes, from the call site plus the helper's own switch.

    These are the columns a name grep of access.js cannot find. They reach it
    as bare parameters — `locationScope` and `deptScope` — so the string
    `staff_location_scope` / `staff_department_scope` appears nowhere in the
    file. The binding from column to helper lives at the cube.js call site
    (`access.computeAllowedAbbreviations(row?.staff_location_scope, ...)`),
    and the legal values are the `case` labels of the helper's own switch. So
    the column names come from cube.js and the values from access.js, and
    neither is written down here — the omission that produced five-of-seven
    personas is not expressible.

    Raises rather than returning an empty set on a miss: an empty set would
    drop the column from the manifest silently, which is the original bug.
    """
    out: dict[str, set[str]] = {}
    for helper in _REMIT_HELPERS:
        call = re.search(rf"access\.{helper}\(\s*row\??\.(\w+_scope)", cube_text)
        if not call:
            raise ValueError(f"cube.js has no row-scoped call to {helper}")
        values = set(_SCOPE_CASE.findall(_function_body(access_text, helper))) - {
            "none"
        }
        if not values:
            raise ValueError(f"{helper} branches on no scope value")
        out[call.group(1)] = values
    return out


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


def scope_values(access_js: Path, cube_js: Path | None = None) -> dict[str, set[str]]:
    """Scope enum values the code branches on, by scope column.

    Sourced from access.js because production is a subset of the domain the
    code handles — several policy branches have no production row. The two
    remit scopes additionally need cube.js, which is where the column names
    are bound to the helpers that consume them (see `_remit_scope_values`);
    it defaults to access.js's neighbour.

    The result must cover every `*_scope` column of dim_staff_cube_access.
    `tests/cube_sandbox/test_personas.py` asserts that against the committed
    snapshot, because "every scope the code branches on" and "every scope
    column the table has" drifted apart once already.
    """
    text = access_js.read_text()
    cube_text = (cube_js or access_js.with_name("cube.js")).read_text()
    tiers = set(_SCOPE_TIER.findall(text))
    out = {t: {"__non_none__"} for t in tiers}
    out["staff_pii_scope"] = _staff_pii_scope_values(text)
    out.update(_remit_scope_values(text, cube_text))
    # See _STUDENT_LOCATION_SCOPE_VALUES above: not derivable by regex from the
    # template-literal source, so this is a documented literal instead.
    out["student_location_scope"] = set(_STUDENT_LOCATION_SCOPE_VALUES)
    return {k: v for k, v in out.items() if v}
