"""Explain row groups with stored classification queries: `explain`.

The trace only leads. A person explains causes with ONE classification query per
comparison and bucket: a `CASE` in lineage order that names each unmatched
row's first failing model predicate, with an `UNEXPLAINED` else-bucket. It is
stored as SQL only, with no data, at
`<validation dir>/explanations/<view>/<comparison>__<bucket>.sql`, under a leading
comment block that maps each bucket to its side and plain words:

    -- cause C1 = dashboard: WPP assessments are left off the dashboard

The query reads the run's unmatched rows of its comparison and bucket through
the placeholder `{unmatched}`, which the tool fills from the run's reconcile:
`__row` (a row id), `item_key`, `side`, the group-by columns, with group-by
columns `__moved` and `__d_<column>` (the dashboard's value of a column that
differs between the sides, else NULL: read `COALESCE(u.__d_x, u.x)` for the
dashboard's cell), the grain under its Cube names, and `__rn` (the row's
duplicate number on its grain). It
returns exactly `__row, cause`, one row per unmatched row. The tool counts:
its own outer query joins the explanation back to `{unmatched}` and returns only
item keys, cause literals and counts, refusing a row the explanation drops or
repeats and a cause that is no string literal of the explanation. Every `sort`
re-runs every stored explanation on the current run's rows; an item whose rows an
explanation fully explains (no `UNEXPLAINED` row) goes to `cause`. A cell set goes
to `cause` when every group with a row in each differing cell is in `cause` or
closed by a decision (`coverage`).
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import sqlglot
from google.api_core.exceptions import GoogleAPIError
from sqlglot import exp
from sqlglot.errors import SqlglotError
from sqlglot.tokens import TokenType

from . import (
    coverage,
    decisions,
    explain_progress,
    pipeline,
    reconcile,
    results,
    saved,
    sort,
    trace,
)
from .bq import CostCapError, ViewHistoryError, Warehouse
from .config import Comparison, ViewConfig, id_like, mask_digits, row_population
from .cube_client import Cube, CubeError, CubeRefusal, network_schools
from .moment import Build, MomentError, pick_moment
from .reconcile import Group
from .report import RunResult, Ticker, mask, shown_counts
from .timetravel import PROJECT, utc_literal
from .trace import TIMEOUT_S, TRACED, _failure

# The buckets a stored explanation classifies: the one-sided rows the trace leads on,
# and rows both sides hold whose values differ.
EXPLAINABLE = (*TRACED, "value_differs", "dims_differ")
# The buckets of rows both sides hold, which each side may file in its own cell.
MOVABLE = ("value_differs", "dims_differ")

PLACEHOLDER = "{unmatched}"
# Enough of a BigQuery message to name the table and the reason.
MAX_MESSAGE = 600
_NOT_AN_ID = re.compile(
    re.escape(PROJECT) + r"|\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?"
)
UNEXPLAINED = "UNEXPLAINED"
COLUMNS = ("__row", "cause")
SIDES = ("cube", "dashboard")
# Trunk lints and formats every committed `.sql` file; an explanation is not dbt SQL,
# and a reformat would only churn it. The sql-banned-syntax opt-out is written
# only when the explanation uses what it bans: an unused one trips
# `trunk/ignore-does-nothing`.
HEADER = (
    "-- trunk-ignore-all(sqlfluff)",
    "-- trunk-ignore-all(sql-banned-syntax)",
    "-- fmt: off",
)
_BUCKET = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,63}")
_REPRODUCE = re.compile(r"--\s*reproduce\s+(?P<bucket>[A-Za-z][A-Za-z0-9_]*)\s*:")
_BLOCK = re.compile(
    r"--\s*cause\s+(?P<bucket>\S+)\s*=\s*(?P<side>\S+?)\s*:\s*(?P<words>.*\S)\s*"
)
_STRINGS = (
    TokenType.STRING,
    TokenType.RAW_STRING,
    TokenType.BYTE_STRING,
    TokenType.NATIONAL_STRING,
)


def explanations_dir(view_file: Path, view: str) -> Path:
    """Where a view's explanations live: beside its validation file.

    Raises:
        pipeline.Refusal: The view's explanations are still in the old
            `proofs/<view>` folder and `explanations/<view>` does not exist;
            reading neither would silently skip them.
    """
    found = view_file.parent / "explanations" / view
    old = view_file.parent / "proofs" / view
    if old.exists() and not found.exists():
        raise pipeline.Refusal(
            f"rename {old} to {found} (git mv); stored explanations moved"
        )
    return found


def explanation_path(directory: Path, comparison: str, bucket: str) -> Path:
    return directory / f"{comparison}__{bucket}.sql"


@dataclass(frozen=True)
class Explanation:
    """One stored explanation: its bucket map and its SQL."""

    path: Path
    comparison: str
    bucket: str
    causes: dict[str, tuple[str, str]]
    body: str
    # Per cause bucket, an aggregate query on today's tables an owner can run
    # (`-- reproduce <bucket>:`); not part of what the explanation explains.
    reproduce: dict[str, str] = field(default_factory=dict)

    @property
    def text(self) -> str:
        return compose(self.causes, self.body, self.reproduce)

    @property
    def recorded(self) -> str:
        """The path `triage.json` records: relative to the validation file."""
        return "/".join(self.path.parts[-3:])

    @property
    def fingerprint(self) -> str:
        return fingerprint(self.causes, self.body)


def fingerprint(causes: dict[str, tuple[str, str]], body: str) -> str:
    """The explanation's bucket map and its SQL, blind to comments, case and spacing."""
    text = json.dumps(
        [
            sorted((b, list(v)) for b, v in causes.items()),
            decisions.sql_fingerprint(body),
        ]
    )
    return hashlib.sha256(text.encode()).hexdigest()


def file_fingerprint(path: Path) -> str | None:
    """A stored explanation file's fingerprint, or None when it is gone or
    unreadable."""
    try:
        return read_explanation(path).fingerprint
    except (OSError, pipeline.Refusal):
        return None


def compose(
    causes: dict[str, tuple[str, str]],
    body: str,
    reproduce: dict[str, str] | None = None,
) -> str:
    """The explanation file: the lint opt-outs, its bucket map, each cause's
    reproduce query as comment lines, then the SQL."""
    block = [f"-- cause {b} = {side}: {words}" for b, (side, words) in causes.items()]
    for b, sql in (reproduce or {}).items():
        block.append(f"-- reproduce {b}:")
        block += [f"--  {line}" if line.strip() else "--" for line in sql.splitlines()]
    banned = re.search(r"\bqualify\b|\bgroup\s+by\s+all\b", body, re.IGNORECASE)
    header = [h for h in HEADER if banned or "sql-banned-syntax" not in h]
    return "\n".join([*header, *block]) + "\n\n" + body.strip() + "\n"


def split_block(text: str) -> tuple[dict[str, tuple[str, str]], str]:
    """An explanation's leading `-- cause` block and the SQL after it.

    The lint opt-outs, blank lines and `-- reproduce` blocks above or inside
    the block are skipped (`split_explanation` reads those too).

    Raises:
        pipeline.Refusal: A line of the block names no side or no words.
    """
    causes, _, body = split_explanation(text)
    return causes, body


def split_explanation(
    text: str,
) -> tuple[dict[str, tuple[str, str]], dict[str, str], str]:
    """An explanation's `-- cause` block, its `-- reproduce <bucket>:` queries, its SQL.

    A reproduce query is the comment lines after its header, each without
    its `--` and up to 2 spaces, up to the next header or SQL line.

    Raises:
        pipeline.Refusal: A cause line names no side or no words, or a
            reproduce header names no bucket or repeats one.
    """
    causes: dict[str, tuple[str, str]] = {}
    reproduce: dict[str, list[str]] = {}
    current: list[str] | None = None
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("-- cause"):
            bucket, side, words = _cause(line)
            causes[bucket] = (side, words)
            current = None
        elif line.startswith("-- reproduce"):
            m = _REPRODUCE.fullmatch(line)
            if not m or m["bucket"] in reproduce:
                raise pipeline.Refusal(
                    "cannot read a `-- reproduce` line: write `-- reproduce "
                    "<bucket>:`, once per bucket, then the query as comment lines"
                )
            current = reproduce[m["bucket"]] = []
        elif current is not None and line.startswith("--") and line not in HEADER:
            rest = lines[i].lstrip()[2:]
            current.append(rest[2:] if rest.startswith("  ") else rest.lstrip(" "))
        elif line and line not in HEADER:
            break
        else:
            # A blank line or a lint opt-out ends a reproduce query.
            current = None
        i += 1
    queries = {b: "\n".join(q).strip() for b, q in reproduce.items()}
    return causes, queries, "\n".join(lines[i:]).strip()


def _cause(line: str) -> tuple[str, str, str]:
    m = _BLOCK.fullmatch(line)
    if not m:
        raise pipeline.Refusal(
            "cannot read a `-- cause` line: write "
            "`-- cause <bucket> = <side>: <plain words>`"
        )
    return _checked(m["bucket"], m["side"], m["words"])


# Digit groups joined by single spaces. `answers.NOTE_REFUSALS` refuses any such
# run of 5 digits, which would also refuse a grade list (`9 10 11 12`), so a cause
# refuses only a run holding a group of 3+ digits, and lets a run of years
# (`2024 2025 2026`) through.
_SPACED_DIGITS = re.compile(r"\d+(?: \d+)+")
_YEAR_SPAN = re.compile(r"(?:19|20)\d{2}(?: (?:19|20)\d{2})+")


def _spaced_id(words: str) -> bool:
    return any(
        sum(c.isdigit() for c in run) >= 5
        and any(len(g) >= 3 for g in run.split())
        and not _YEAR_SPAN.fullmatch(run)
        for run in _SPACED_DIGITS.findall(words)
    )


def _checked(bucket: str, side: str, words: str) -> tuple[str, str, str]:
    if not _BUCKET.fullmatch(bucket) or bucket == UNEXPLAINED:
        raise pipeline.Refusal(
            "a bucket name must use letters, digits and _, start with a letter, "
            f"and not be {UNEXPLAINED}"
        )
    if side not in SIDES:
        raise pipeline.Refusal(f"bucket {bucket}: side must be cube or dashboard")
    words = " ".join(words.split())
    if not words:
        raise pipeline.Refusal(f"bucket {bucket}: say what the cause is in words")
    if id_like(words) or _spaced_id(words):
        raise pipeline.Refusal(
            f"bucket {bucket}: the words hold an email or an ID-like number; "
            "an explanation is committed, so name no student or staff member"
        )
    return bucket, side, words


def parse_cause_flag(flag: str) -> tuple[str, str, str]:
    """`<bucket>=<side>:<plain words>`, checked."""
    bucket, eq, rest = flag.partition("=")
    side, colon, words = rest.partition(":")
    if not eq or not colon:
        raise pipeline.Refusal("a --cause flag reads <bucket>=<side>:<plain words>")
    return _checked(bucket.strip(), side.strip(), words)


def read_explanation(path: Path) -> Explanation:
    """A stored explanation, named `<comparison>__<bucket>.sql`."""
    comparison, sep, bucket = path.stem.rpartition("__")
    if not sep or bucket not in EXPLAINABLE:
        raise pipeline.Refusal(
            f"{path.name}: name an explanation <comparison>__<{'|'.join(EXPLAINABLE)}>.sql"
        )
    causes, reproduce, body = split_explanation(path.read_text())
    return Explanation(path, comparison, bucket, causes, body, reproduce)


# --- the checks -------------------------------------------------------------------


def grain_names(comparison: Comparison) -> set[str]:
    """Every name a grain column goes by, lowercased."""
    grain = comparison.rows.grain if comparison.rows else []
    return {n.lower() for p in grain for n in (p.cube, p.dashboard)}


def identifying(comparison: Comparison) -> set[str]:
    """The student column's names: a literal compared with one names a row."""
    grain = comparison.rows.grain if comparison.rows else []
    return {n.lower() for p in grain[:1] for n in (p.cube, p.dashboard)}


# Numbers that name or reach a person (direct identifiers and contact details in
# `.claude/rules/ferpa-pii.md`), whatever else the name says.
_PERSON_NUMBERS = (
    "student_number",
    "studentnumber",
    "employee_number",
    "phone_number",
    "state_id",
    "local_id",
    "school_specific_id",
)
_PEOPLE = ("student", "employee", "staff", "teacher")
# What a `_number` column may number and still name no one. Any other
# `_number` column is treated as naming a person: a missed identifier costs
# more than a refused category.
_CATEGORIES = (
    "band",
    "level",
    "grade",
    "module",
    "unit",
    "section",
    "course",
    "school",
    "week",
    "month",
    "quarter",
    "term",
    "year",
    "period",
)


def _identifies(column: str, student: set[str]) -> bool:
    """A column whose value can name or reach a student or staff member.

    The student grain column, a name or email column, a number that names or
    reaches a person (`student_number`, `employee_number`, a phone number), an
    id, key or identifier of a student or staff member, or any `_number`
    column that does not number a category (`_CATEGORIES`, such as
    `module_number` or a band number). Another id (`assessment_id`) names no
    one, so an explanation may compare it with a literal.
    """
    name = column.lower()
    person = any(word in name for word in _PEOPLE)
    return (
        name in student
        or name.endswith(("_name", "_email"))
        or name.endswith(_PERSON_NUMBERS)
        or (person and name.endswith(("_id", "_key", "_number", "_identifier")))
        or (name.endswith("_number") and not any(word in name for word in _CATEGORIES))
    )


def _id_like(column: str, student: set[str]) -> bool:
    """A column a cause may not select: any identifier, not only a person's."""
    return _identifies(column, student) or column.lower().endswith(sort._ID_SUFFIXES)


_STOP = (exp.Predicate, exp.Connector, exp.Not, exp.Subquery, exp.AggFunc, exp.Exists)


def _selected(node: exp.Expression | None):
    """The columns whose values a projection returns, not those it only tests."""
    if node is None or isinstance(node, _STOP):
        return
    if isinstance(node, exp.Column):
        yield node.name.lower()
        return
    if isinstance(node, exp.Case):
        for branch in node.args.get("ifs") or []:
            yield from _selected(branch.args.get("true"))
        yield from _selected(node.args.get("default"))
        return
    if isinstance(node, exp.If):
        yield from _selected(node.args.get("true"))
        yield from _selected(node.args.get("false"))
        return
    for child in node.iter_expressions():
        yield from _selected(child)


def _outer_selects(node: exp.Expression):
    if isinstance(node, exp.SetOperation):
        yield from _outer_selects(node.left)
        yield from _outer_selects(node.right)
    elif isinstance(node, exp.Subquery):
        yield from _outer_selects(node.this)
    elif isinstance(node, exp.Select):
        yield node


def _leaves(node: exp.Expression):
    """Columns and literals of a comparison, through casts, arithmetic and
    UNNEST, but not into a subquery that reads a table."""
    for child in node.iter_expressions():
        if isinstance(child, exp.Exists) or (
            isinstance(child, exp.Select) and child.args.get("from")
        ):
            continue
        if isinstance(child, (exp.Column, exp.Literal)):
            yield child
        yield from _leaves(child)


def _scan_text(body: str) -> None:
    """Refuse an ID-like value or an email in a comment or a string literal."""
    try:
        tokens = sqlglot.Dialect.get_or_raise("bigquery").tokenize(body)
    except SqlglotError as exc:
        raise pipeline.Refusal(
            f"the explanation does not parse as BigQuery SQL: {type(exc).__name__}"
        ) from exc
    for token in tokens:
        texts = list(token.comments)
        if token.token_type in _STRINGS:
            texts.append(token.text)
        if any(id_like(t) for t in texts):
            raise pipeline.Refusal(
                "the explanation holds an email or an ID-like number in a comment "
                "or a string; an explanation is committed, so name no student or "
                "staff member"
            )


def check_sql(body: str, grain: set[str], student: set[str] = frozenset()) -> set[str]:
    """Refuse an explanation that could return or name a row, before it runs.

    Args:
        body: The explanation's SQL, without its `-- cause` block.
        grain: Every grain column name, lowercased.
        student: The student column's names, lowercased. No literal may be
            compared with them, nor with a column `_identifies` names a
            person by; `cause` may select no identifier column at all.

    Returns:
        The explanation's string literals: the only values a `cause` may take.

    Raises:
        pipeline.Refusal: No `{unmatched}`; SQL that does not parse; an
            outer SELECT returning `*`, anything but `__row` and `cause`, or a
            grain or identifying column's value as `cause`; no string literal
            to name a cause; an ID-like value or an email in a comment or a
            string; or a literal compared with an identifying column.
    """
    if PLACEHOLDER not in body:
        raise pipeline.Refusal(f"the explanation never reads {PLACEHOLDER}")
    _scan_text(body)
    try:
        tree = sqlglot.parse_one(body.replace(PLACEHOLDER, "__u"), read="bigquery")
    except SqlglotError as exc:
        raise pipeline.Refusal(
            f"the explanation does not parse as BigQuery SQL: {type(exc).__name__}"
        ) from exc
    selects = list(_outer_selects(tree))
    causes: list[exp.Expression] = []
    if not selects:
        raise pipeline.Refusal("the explanation is not a SELECT")
    for select in selects:
        names = []
        for projection in select.expressions:
            if isinstance(projection, exp.Star) or (
                isinstance(projection, exp.Column)
                and isinstance(projection.this, exp.Star)
            ):
                raise pipeline.Refusal(
                    "the explanation selects *; return only __row, cause"
                )
            name = projection.alias_or_name.lower()
            names.append(name)
            value = projection.unalias()
            if name == "__row" and not (
                isinstance(value, exp.Column) and value.name.lower() == "__row"
            ):
                raise pipeline.Refusal(
                    f"the explanation's __row must be {PLACEHOLDER}'s own __row"
                )
            if name == "cause":
                causes.append(value)
            if name == "cause" and any(
                c in grain or _id_like(c, student) for c in _selected(value)
            ):
                raise pipeline.Refusal(
                    "the explanation's cause selects a grain or identifying column; "
                    "name each cause with a string literal"
                )
        if sorted(names) != sorted(COLUMNS):
            raise pipeline.Refusal(
                f"the explanation returns {len(names)} column(s) other than __row and "
                "cause; return exactly __row, cause"
            )
    for node in tree.find_all(exp.Predicate):
        if isinstance(node, exp.Exists):
            continue
        leaves = list(_leaves(node))
        if any(
            isinstance(c, exp.Column) and _identifies(c.name, student) for c in leaves
        ) and any(isinstance(c, exp.Literal) for c in leaves):
            raise pipeline.Refusal(
                "the explanation compares an identifying column with a literal: never "
                "name a row by its value"
            )
    literals = {lit.this for lit in tree.find_all(exp.Literal) if lit.is_string}
    if not literals:
        raise pipeline.Refusal(
            "the explanation has no string literal; name each cause with one"
        )
    for value in causes:
        _check_default(value)
    for table in _unpinned(tree):
        print(
            f"warning: the explanation reads {table} with no project and dataset, "
            "so it reads the table as it is now, not as of the run; write it "
            "`teamster-332318`.`<dataset>`.`<table>`"
        )
    return literals


def check_reproduce(sql: str, grain: set[str], student: set[str] = frozenset()) -> None:
    """Refuse a reproduce query that could return or name a row, before it runs.

    A reproduce query reads today's tables, outside the run, and returns
    counts an owner compares with the cause: every column it returns is an
    aggregate or one of its GROUP BY columns.

    Args:
        sql: The query, without its comment prefixes.
        grain: Every grain column name, lowercased.
        student: The student column's names, lowercased.

    Raises:
        pipeline.Refusal: It reads `{unmatched}` or time-travels; does not
            parse; is not 1 SELECT; returns `*`, a window function, or a
            column that is no aggregate and not grouped by; has no aggregate;
            groups by or returns a grain or identifying column; holds an
            ID-like value or an email in a comment or string; or compares an
            identifying column with a literal.
    """
    if PLACEHOLDER in sql:
        raise pipeline.Refusal(
            f"a reproduce query reads today's tables, never {PLACEHOLDER}"
        )
    if re.search(r"\bfor\s+system_time\b", sql, re.IGNORECASE):
        raise pipeline.Refusal(
            "a reproduce query reads today's tables: drop FOR SYSTEM_TIME AS OF"
        )
    _scan_text(sql)
    try:
        parsed = sqlglot.parse(sql, read="bigquery")
    except SqlglotError as exc:
        raise pipeline.Refusal(
            f"the reproduce query does not parse as BigQuery SQL: {type(exc).__name__}"
        ) from exc
    statements = [t for t in parsed if t is not None]
    if len(statements) != 1 or not isinstance(statements[0], exp.Select):
        raise pipeline.Refusal("a reproduce query is 1 SELECT (a WITH may lead it)")
    tree = statements[0]
    group = (tree.args.get("group") or exp.Group()).expressions
    by_position = {int(g.this) for g in group if isinstance(g, exp.Literal)}
    grouped = {g.sql().lower() for g in group} | {
        g.alias_or_name.lower() for g in group if not isinstance(g, exp.Literal)
    }

    def names_a_row(node: exp.Expression) -> bool:
        cols = [c.name.lower() for c in node.find_all(exp.Column)]
        if isinstance(node, exp.Column):
            cols.append(node.name.lower())
        return any(c in grain or _id_like(c, student) for c in cols)

    aggregates = 0
    for n, projection in enumerate(tree.expressions, start=1):
        value = projection.unalias()
        if isinstance(value, exp.Star) or (
            isinstance(value, exp.Column) and isinstance(value.this, exp.Star)
        ):
            raise pipeline.Refusal("the reproduce query selects *; return counts")
        if value.find(exp.Window):
            raise pipeline.Refusal(
                "the reproduce query uses a window function; aggregate with GROUP BY"
            )
        if value.find(exp.AggFunc):
            aggregates += 1
            continue
        name = projection.alias_or_name.lower()
        if not (n in by_position or name in grouped or value.sql().lower() in grouped):
            raise pipeline.Refusal(
                f"the reproduce query returns {name or 'a column'} that is no "
                "aggregate and not in its GROUP BY; return counts only"
            )
        if name in grain or _id_like(name, student) or names_a_row(value):
            raise pipeline.Refusal(
                "the reproduce query groups by a grain or identifying column; "
                "count by school, grade or another column that names no one"
            )
    if not aggregates:
        raise pipeline.Refusal("the reproduce query returns no aggregate; count rows")
    for g in group:
        if not isinstance(g, exp.Literal) and names_a_row(g):
            raise pipeline.Refusal(
                "the reproduce query groups by a grain or identifying column; "
                "count by school, grade or another column that names no one"
            )
    for node in tree.find_all(exp.Predicate):
        # An EXISTS is no comparison: each comparison inside it is tested on
        # its own, as find_all reaches it.
        if isinstance(node, exp.Exists):
            continue
        leaves = list(_leaves(node))
        if any(
            isinstance(c, exp.Column) and _identifies(c.name, student) for c in leaves
        ) and any(isinstance(c, exp.Literal) for c in leaves):
            raise pipeline.Refusal(
                "the reproduce query compares an identifying column with a "
                "literal: never name a row by its value"
            )


def _check_default(value: exp.Expression) -> None:
    """Refuse a cause that is not one CASE of literals ending in `ELSE 'UNEXPLAINED'`.

    A catch-all cause would file the rows of a new cause, in a later run,
    under an old one with no one looking. Only literal branches rule that
    out: an `IF()`, a nested CASE or a column carried from a CTE in a THEN
    can hide a catch-all of its own. Conditions may use anything.

    Raises:
        pipeline.Refusal: The cause is not a CASE, a THEN is not a string
            literal, or the ELSE is missing or another value.
    """

    def _is_text(node: exp.Expression | None, text: str | None = None) -> bool:
        return (
            isinstance(node, exp.Literal)
            and node.is_string
            and (text is None or node.this == text)
        )

    if not isinstance(value, exp.Case) or value.this is not None:
        raise pipeline.Refusal(
            f"the explanation's cause must be one CASE WHEN ... THEN '<cause>' ... "
            f"ELSE '{UNEXPLAINED}' END"
        )
    if not all(_is_text(branch.args.get("true")) for branch in value.args["ifs"]):
        raise pipeline.Refusal(
            "every THEN of the explanation's cause must be a quoted cause name: a "
            "function, nested CASE or column there can hide a catch-all"
        )
    if not _is_text(value.args.get("default"), UNEXPLAINED):
        raise pipeline.Refusal(
            f"the explanation's cause must end in ELSE '{UNEXPLAINED}', so a row of a "
            "new cause is never filed under an old one"
        )


def _unpinned(tree: exp.Expression) -> list[str]:
    """Tables the explanation names without a project and dataset, CTEs aside."""
    ctes = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    out = []
    for t in tree.find_all(exp.Table):
        name = t.name.lower()
        if name == "__u" or name in ctes or (t.catalog and t.db):
            continue
        out.append(t.sql(dialect="bigquery"))
    return list(dict.fromkeys(out))


# --- the rows it reads ------------------------------------------------------------


def unmatched_sql(
    comparison: Comparison,
    bucket: str,
    items: list[tuple[str, Group]],
    source: str,
) -> tuple[str, str]:
    """Every unmatched row of the bucket, as the run's reconcile found them.

    Args:
        source: The comparison's saved rows (`require_saved`), or the same rows
            inline as a parenthesized query (`pipeline.inline_unmatched`).

    Returns:
        A `WITH` holding the bucket's rows as `__f` (`bucket_rows_sql`), and the
        SELECT that returns `__row` (a row id from the grain keys and the
        duplicate number), `item_key` (the triage item id of the row's group,
        NULL for a row no open group holds), `side` (the side holding the row),
        the group-by columns as text, with group-by columns `__moved` (the row
        sits in another cell on each side) and `__d_<column>` per column (the
        dashboard's value, NULL unless that column differs between the sides,
        so an explanation reads `COALESCE(u.__d_x, u.x)` for the dashboard's
        cell), the grain under its Cube names (as the side holding the row
        types it), and `__rn`. A `value_differs` row's side reads `both`.
    """
    if comparison.rows is None:
        raise pipeline.Refusal(f"comparison {comparison.id!r} has no rows to explain")
    dims = pipeline.group_dims(comparison)
    grain = comparison.rows.grain
    whens = []
    for item_id, g in items:
        nulls = set(g.nulls)
        tests = [
            f"{_joined_column(column)} IS NULL"
            if column in nulls
            else f"{_joined_column(column)} = {pipeline.lit(value)}"
            for column, value in g.dims
        ]
        if dims:
            # A row each side files in another cell belongs only to a group
            # with the dashboard's cell (`d:` dims), whatever its own dims.
            moved = any(c.startswith(reconcile.DASH_PREFIX) for c, _ in g.dims)
            tests.append(f"COALESCE({reconcile._MOVED}, FALSE) = {str(moved).upper()}")
        test = " AND ".join(tests)
        whens.append(f"WHEN {test or 'TRUE'} THEN {pipeline.lit(item_id)}")
    key = f"CASE {' '.join(whens)} END" if whens else "CAST(NULL AS STRING)"
    ctes = f"WITH __f AS (\n{bucket_rows_sql(comparison, bucket, source)}\n)"
    columns = [
        "__row",
        f"{key} AS item_key",
        "side",
        *(p.cube for p in dims),
        *([reconcile._MOVED] if dims else []),
        *(f"__d_{p.cube}" for p in dims),
        *(p.cube for p in grain),
        "__rn",
    ]
    # trunk-ignore(bandit/B608): identifiers are validated in config.py; values are bound literals
    return ctes, f"SELECT {', '.join(columns)}\nFROM __f"


def bucket_rows_sql(comparison: Comparison, bucket: str, source: str) -> str:
    """The bucket's saved rows with every column an explanation or item reads.

    `source` holds `reconcile.reconcile_script`'s saved rows. Returns
    `unmatched_sql`'s columns but `item_key`, plus, with group-by columns,
    `__moved` and `__d_<column>` per column (the dashboard's cell of a row
    each side files in another cell, which its group names as `d:` dims), and
    each cut's flag (`__cut<j>`). The grain and the cut flags are read on the
    side holding the row: the dashboard's for a `dashboard_only` row, else
    Cube's (a value-differing row is on both sides; Cube types its grain). A
    row both sides hold adds the dashboard's cut flags (`__dcut<j>`): each
    side may file it under another cut.
    """
    if comparison.rows is None:
        raise pipeline.Refusal(f"comparison {comparison.id!r} has no rows to explain")
    if bucket not in reconcile.UNMATCHED:
        raise pipeline.Refusal(f"{bucket!r} is no bucket a run saves")
    side = "d" if bucket == "dashboard_only" else "c"
    held = {"cube_only": "cube", "dashboard_only": "dashboard"}.get(bucket, "both")
    dims = pipeline.group_dims(comparison)
    flags = pipeline.cut_flags(comparison) or []
    columns = [
        "__row",
        f"'{held}' AS side",
        *(p.cube for p in dims),
        *([reconcile._MOVED] if dims else []),
        *(f"__d_{p.cube}" for p in dims),
        *(f"__g{side}{i} AS {p.cube}" for i, p in enumerate(comparison.rows.grain)),
        "__rn",
        *(f"__{side}k{j} AS __cut{j}" for j in range(len(flags))),
        *(
            f"__dk{j} AS __dcut{j}"
            for j in range(len(flags) if bucket in MOVABLE else 0)
        ),
    ]
    # trunk-ignore(bandit/B608): identifiers are validated in config.py; the bucket is checked above
    return f"SELECT {', '.join(columns)}\nFROM {source}\nWHERE bucket = '{bucket}'"


def _joined_column(dim: str) -> str:
    """The `joined` column a group's dim reads: a `d:` dim is the dashboard's."""
    if dim.startswith(reconcile.DASH_PREFIX):
        return f"__d_{dim[len(reconcile.DASH_PREFIX) :]}"
    return dim


@dataclass(frozen=True)
class StudentCount:
    """What `explanation_query` needs to count a cause's students per cell and cut.

    The rows are `unmatched_sql`'s `__f` (`bucket_rows_sql`); `student` is the
    first grain column; `dims` the cell's columns; `moved` adds each row both
    sides hold to the dashboard's cell too, under the dashboard's cut flags
    (`__dcut<j>`): with dims, only a row each side files in another cell
    (`__moved`); `cuts` is how many `__cut<j>` flags the rows carry.
    """

    student: str
    dims: tuple[str, ...]
    moved: bool
    cuts: int


def explanation_query(
    ctes: str,
    select: str,
    body: str,
    literals: set[str],
    students: StudentCount | None = None,
) -> str:
    """The explanation inside the tool's own counting query.

    Only item keys, cause literals and counts come back: per item and cause,
    the rows, the rows the explanation dropped (`missed`) or repeated (`doubled`),
    the rows whose cause is no string literal of the explanation (`bad`), and the
    explanation's rows with a `__row` `{unmatched}` lacks (`stray`). With
    `students`, every row carries `__kind` `count`, and rows of `__kind`
    `students` add per cause, cut (`__cut`, its index) and cell (`__cell`,
    its dims as JSON) the distinct students the explanation gives that cause
    (`n_students`): counted in BigQuery, never listed.
    """
    allowed = ", ".join(pipeline.lit(v) for v in sorted(literals))
    proof = body.replace(PLACEHOLDER, "__u")
    head = f"{ctes},\n" if ctes else "WITH "
    if students is not None:
        return _with_students(head, select, proof, allowed, students)
    return (
        # trunk-ignore(bandit/B608): the explanation is the analyst's read-only SQL, vetted by check_sql; cause literals are quoted by pipeline.lit
        f"{head}__u AS (\n{select}\n),\n__p AS (\n{proof}\n),\n"
        "__per AS (\n  SELECT __row, COUNT(*) AS __times, "
        f"MIN(IF(cause IN ({allowed}), cause, NULL)) AS cause, "
        f"COUNTIF(cause IS NULL OR cause NOT IN ({allowed})) AS __bad\n"
        "  FROM __p GROUP BY __row\n),\n"
        "__stray AS (\n  SELECT COUNT(*) AS n FROM __per "
        "WHERE __row NOT IN (SELECT __row FROM __u)\n)\n"
        "SELECT u.item_key, per.cause, COUNT(*) AS n, "
        "COUNTIF(per.__row IS NULL) AS missed, "
        "COUNTIF(per.__times > 1) AS doubled, "
        "COUNTIF(per.__bad > 0) AS bad, "
        "ANY_VALUE(s.n) AS stray\n"
        "FROM __u AS u LEFT JOIN __per AS per ON per.__row = u.__row "
        "CROSS JOIN __stray AS s\n"
        "GROUP BY u.item_key, per.cause"
    )


def _with_students(
    head: str, select: str, proof: str, allowed: str, s: StudentCount
) -> str:
    """`explanation_query` with the cause-student counts after the item counts."""

    def placed(dim, flag: str = "__cut", where: str = "") -> str:
        cols = ", ".join(f"CAST(f.{dim(d)} AS STRING) AS {d}" for d in s.dims)
        flags = "".join(f", f.{flag}{j} AS __cut{j}" for j in range(s.cuts))
        return (
            # trunk-ignore(bandit/B608): identifiers are validated in config.py; cause literals are quoted by pipeline.lit
            f"SELECT per.cause, {cols + ', ' if cols else ''}f.{s.student} AS __st"
            f"{flags} FROM __per AS per JOIN __f AS f ON f.__row = per.__row "
            f"WHERE per.cause IN ({allowed}) AND per.__times = 1{where}"
        )

    places = [placed(lambda d: d)]
    if s.moved:
        # A row in the same cell on both sides has no dashboard cell of its own.
        moved = f" AND f.{reconcile._MOVED}" if s.dims else ""
        places.append(placed(lambda d: f"__d_{d}", "__dcut", moved))
    cell = "TO_JSON_STRING(STRUCT(" + ", ".join(s.dims) + "))" if s.dims else "'{}'"
    nulls = "CAST(NULL AS STRING) AS item_key, cause, " + ", ".join(
        f"CAST(NULL AS INT64) AS {c}"
        for c in ("n", "missed", "doubled", "bad", "stray")
    )
    per_cut = [
        # trunk-ignore(bandit/B608): identifiers are validated in config.py; no values are interpolated
        f"SELECT 'students' AS __kind, {nulls}, {j} AS __cut, {cell} AS __cell, "
        f"COUNT(DISTINCT __st) AS n_students FROM __cs WHERE __cut{j} "
        "GROUP BY cause, __cell"
        for j in range(s.cuts)
    ]
    return (
        # trunk-ignore(bandit/B608): the explanation is the analyst's read-only SQL, vetted by check_sql; identifiers come from validated config
        f"{head}__u AS (\n{select}\n),\n__p AS (\n{proof}\n),\n"
        "__per AS (\n  SELECT __row, COUNT(*) AS __times, "
        f"MIN(IF(cause IN ({allowed}), cause, NULL)) AS cause, "
        f"COUNTIF(cause IS NULL OR cause NOT IN ({allowed})) AS __bad\n"
        "  FROM __p GROUP BY __row\n),\n"
        "__stray AS (\n  SELECT COUNT(*) AS n FROM __per "
        "WHERE __row NOT IN (SELECT __row FROM __u)\n),\n"
        f"__cs AS (\n  {' UNION ALL '.join(places)}\n)\n"
        "SELECT 'count' AS __kind, u.item_key, per.cause, COUNT(*) AS n, "
        "COUNTIF(per.__row IS NULL) AS missed, "
        "COUNTIF(per.__times > 1) AS doubled, "
        "COUNTIF(per.__bad > 0) AS bad, "
        "ANY_VALUE(s.n) AS stray, CAST(NULL AS INT64) AS __cut, "
        "CAST(NULL AS STRING) AS __cell, CAST(NULL AS INT64) AS n_students\n"
        "FROM __u AS u LEFT JOIN __per AS per ON per.__row = u.__row "
        "CROSS JOIN __stray AS s\n"
        "GROUP BY u.item_key, per.cause" + "".join(f"\nUNION ALL\n{q}" for q in per_cut)
    )


def cause_students(
    rows: list[dict], proof: Explanation, comparison: Comparison
) -> list[dict]:
    """The `students` rows of `explanation_query`, as triage keeps them: per cause
    (`sort.cause_key`), cut label and cell (`dims` as [column, value]
    pairs), `n` distinct students, and the explanation's `bucket`. Rows of causes
    the explanation does not map are left out (`outcomes` refuses those)."""
    labels = [label for label, _, _ in pipeline.cut_flags(comparison) or []]
    dims = [p.cube for p in pipeline.group_dims(comparison)]
    out = []
    for r in rows:
        if r.get("__kind") != "students" or r["cause"] not in proof.causes:
            continue
        side, words = proof.causes[r["cause"]]
        cell = json.loads(r["__cell"] or "{}")
        out.append(
            {
                "cause": sort.cause_key(side, words),
                "cut": labels[int(r["__cut"])],
                "dims": [[d, cell.get(d)] for d in dims],
                "n": int(r["n_students"]),
                "bucket": proof.bucket,
            }
        )
    return out


def keep_students(
    loaded: dict, comparison: str, bucket: str, found: list[dict]
) -> None:
    """Put an explanation's cause-student counts in a triage, per comparison.

    They replace the counts an earlier run of the same bucket's explanation left,
    and any count saved without its bucket: a revised explanation's smaller count
    must not lose to its old one. A count 2 buckets' explanations give the same
    cell keeps the larger (each is exact for its own bucket's rows).
    """
    by_comparison = loaded.setdefault("cause_students", {})
    kept = [
        e
        for e in by_comparison.get(comparison, [])
        if e.get("bucket") not in (bucket, None)
    ]
    by_comparison[comparison] = kept
    at = {(e["cause"], e["cut"], json.dumps(e["dims"])): e for e in kept}
    for e in found:
        key = (e["cause"], e["cut"], json.dumps(e["dims"]))
        if key in at:
            at[key]["n"] = max(at[key]["n"], e["n"])
        else:
            at[key] = dict(e)
            kept.append(at[key])


# --- one explanation's outcome ---------------------------------------------------


@dataclass
class Outcome:
    """What one explanation found for one item."""

    n_rows: int
    counts: Counter
    unexplained: int = 0

    @property
    def counted(self) -> int:
        return sum(self.counts.values())

    @property
    def explained(self) -> bool:
        return self.n_rows > 0 and not self.unexplained and self.counted == self.n_rows

    def gap_line(self, name: str) -> str:
        """Why the explanation does not explain the item, with exact counts."""
        seen = self.counted + self.unexplained
        if seen != self.n_rows:
            return f"explanation {name} saw {seen} of the item's {self.n_rows} rows"
        return f"explanation {name} leaves {self.unexplained} rows unexplained"


def outcomes(
    rows: list[dict],
    proof: Explanation,
    items: list[tuple[str, Group]],
    literals: set[str],
) -> dict[str, Outcome]:
    """Read the counting query's result per item.

    Raises:
        pipeline.Refusal: The explanation dropped or repeated a row, gave a row a
            cause that is no string literal of it, returned a `__row`
            `{unmatched}` lacks, or named a cause literal the bucket map
            lacks. Each refusal names counts and literals, never a value.
    """
    out = {item_id: Outcome(g.n_rows, Counter()) for item_id, g in items}
    totals: Counter = Counter()
    unmapped: set[str] = set()
    for r in rows:
        if r.get("__kind") == "students":
            continue
        for what in ("missed", "doubled", "bad"):
            totals[what] += int(r[what] or 0)
        totals["stray"] = max(totals["stray"], int(r["stray"] or 0))
        key, cause, n = r["item_key"], r["cause"], int(r["n"])
        if key is None or key not in out or cause is None:
            continue
        if cause == UNEXPLAINED:
            out[key].unexplained += n
        elif cause in proof.causes:
            out[key].counts[cause] += n
        elif cause in literals:
            unmapped.add(cause)
    reasons = {
        "missed": "unmatched rows have no row in its output",
        "doubled": "unmatched rows appear more than once in its output",
        "bad": "rows got a cause that is no string literal of the explanation",
        "stray": "output rows carry a __row that is not in {unmatched}",
    }
    if problems := [f"{totals[k]} {why}" for k, why in reasons.items() if totals[k]]:
        raise pipeline.Refusal(
            f"{proof.path.name}: {'; '.join(problems)}. Return exactly one row per "
            f"{PLACEHOLDER} row, with a string-literal cause"
        )
    if unmapped:
        named = sorted(b for b in unmapped if _BUCKET.fullmatch(b))
        other = len(unmapped) - len(named)
        what = ", ".join(named) + (
            f"{', ' if named else ''}{other} other literal(s)" if other else ""
        )
        raise pipeline.Refusal(
            f"{proof.path.name}: no --cause for {what}; map every bucket "
            "(`--cause <bucket>=<side>:<plain words>`)"
        )
    return out


def bigquery_said(exc: GoogleAPIError) -> str:
    """A BigQuery error with its message, for the terminal and local files only.

    The message names tables, columns and timestamps; ID-shaped numbers in it
    are masked in case it quotes a value. Posted text keeps a fixed line.
    """
    message = " ".join(str(getattr(exc, "message", None) or exc).split())
    # The project and the timestamps name what clashed; they are no ID.
    kept: list[str] = []

    def keep(m: re.Match) -> str:
        kept.append(m[0])
        return f"\x00{len(kept) - 1}\x00"

    masked = re.sub(
        "\x00(\\d+)\x00",
        lambda m: kept[int(m[1])],
        mask_digits(_NOT_AN_ID.sub(keep, message)),
    )
    # Cut after masking, so a cut never leaves part of an ID unmasked.
    if len(masked) > MAX_MESSAGE:
        masked = masked[:MAX_MESSAGE] + "..."
    return f"{_failure(exc)}: {masked}"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def require_saved(
    wh: Warehouse, cfg: ViewConfig, run: RunResult, comparison: Comparison
) -> str:
    """The comparison's saved rows for this run, as SQL names the table.

    The rows were saved at the comparison's own moment (`run.moment_of`). The
    table must exist and carry the labels that moment and its SQL give it
    (`saved.labels`): a table of another run, or of SQL that changed since, is
    never read.

    Raises:
        pipeline.Refusal: The table is gone, or its labels differ; the message
            says what to run, by whether the comparison's moment is still
            within time travel.
    """
    moment = run.moment_of(comparison.id)
    table = saved.table_id(cfg.view, moment, comparison.id)
    want = saved.labels(
        cfg.view,
        moment,
        comparison.id,
        pipeline.checkpoint_fingerprint(
            comparison, run.fingerprints.get(comparison.id, {})
        ),
    )
    have = wh.saved_labels(table)
    if have is None:
        why = (
            f"comparison {comparison.id!r}: no saved rows for the run of "
            f"{utc_literal(moment.end)}; they expired or were never saved."
        )
    elif differ := sorted(k for k in want if have.get(k) != want[k]):
        why = (
            f"comparison {comparison.id!r}: the saved rows are labelled for another "
            f"run or SQL ({', '.join(differ)})."
        )
    else:
        return saved.table_sql(table)
    again = f"compare --comparison {comparison.id}"
    try:
        pick_moment([moment], _utcnow(), None)
        step = f"Run `{again} --moment '{moment.end.isoformat()}'` to save them again"
    except MomentError:
        step = (
            f"Run `{again}` at a new moment: this moment is past BigQuery's 7 days "
            "of time travel"
        )
    raise pipeline.Refusal(f"{why} {step}")


def explanation_sql(
    wh: Warehouse,
    cfg: ViewConfig,
    comparison: Comparison,
    sides: pipeline.RowSides,
    proof: Explanation,
    items: list[tuple[str, Group]],
    build: Build,
    *,
    table: str,
    moved: dict[str, bool] | None = None,
    students: bool = False,
) -> tuple[str, set[str]]:
    """Check and pin an explanation, and build its counting query over the saved rows.

    The explanation's own tables are read as of the build start, as the dashboard
    side is (`timetravel.as_of`); a table only the Cube side reads is read at
    the build end, as the trace does, since BigQuery reads a table at 1 moment
    per query. The saved rows are read as they are: they were written after
    the moment. Runs no priced query.

    Args:
        table: The comparison's saved rows (`require_saved`).
        moved: The tables already checked for a change during the build, and
            whether they changed; shared across the explanations of one triage.
        students: Also count each cause's students per cell and cut.

    Returns:
        The query and the explanation's string literals.

    Raises:
        pipeline.Refusal: The explanation fails a check (`check_sql`), cannot be read
            as of the moment, or reads a table that changed during the build at
            the build end.
    """
    literals = check_sql(proof.body, grain_names(comparison), identifying(comparison))
    at = pipeline.checked_as_of(proof.body, build.start, wh)
    body = trace._one_moment(
        at,
        set(sides.cube.tables - sides.dashboard.tables),
        {} if moved is None else moved,
        build,
        wh,
        doing=f"read in {proof.path.name}",
    )
    ctes, select = unmatched_sql(comparison, proof.bucket, items, table)
    count = _student_count(comparison, proof.bucket) if students else None
    return explanation_query(ctes, select, body, literals, count), literals


def run_explanation(
    wh: Warehouse,
    cfg: ViewConfig,
    comparison: Comparison,
    sides: pipeline.RowSides,
    proof: Explanation,
    items: list[tuple[str, Group]],
    build: Build,
    moved: dict[str, bool] | None = None,
    students: list[dict] | None = None,
    *,
    table: str,
) -> dict[str, Outcome]:
    """Check, pin, price and run an explanation on the run's saved rows. Call inside
    `wh.budget`.

    Args:
        moved: As `explanation_sql` takes it.
        students: Given, receives the explanation's cause-student counts per cell
            and cut (`cause_students`), for `triage.json`.
        table: The comparison's saved rows (`require_saved`).

    Raises:
        pipeline.Refusal: As `explanation_sql`, a failed outcome check (`outcomes`),
            or BigQuery refuses it (its message is kept for the terminal).
        CostCapError: It would pass the run's or the day's cap.
    """
    sql, literals = explanation_sql(
        wh,
        cfg,
        comparison,
        sides,
        proof,
        items,
        build,
        table=table,
        moved=moved,
        students=students is not None,
    )
    try:
        usd = wh.estimate(sql)
        wh.refuse_past_caps(usd)
        print(f"Explanation {proof.path.name}: ${usd:.2f} (dry run).")
        rows = wh.rows(sql, timeout_s=TIMEOUT_S)
    except GoogleAPIError as exc:
        raise pipeline.Refusal(
            f"{proof.path.name}: BigQuery refused it ({bigquery_said(exc)})"
        ) from exc
    found = outcomes(rows, proof, items, literals)
    if students is not None:
        students += cause_students(rows, proof, comparison)
    return found


def _student_count(comparison: Comparison, bucket: str) -> StudentCount | None:
    """The `StudentCount` for an explanation's rows, or None when the comparison's
    cuts cannot be told apart (`pipeline.cut_flags`)."""
    flags = pipeline.cut_flags(comparison)
    if not flags or comparison.rows is None:
        return None
    return StudentCount(
        student=comparison.rows.grain[0].cube,
        dims=tuple(p.cube for p in pipeline.group_dims(comparison)),
        moved=bucket in MOVABLE,
        cuts=len(flags),
    )


def _explanation_lines(proof: Explanation, outcome: Outcome, posted: bool) -> list[str]:
    ranked = outcome.counts.most_common()
    _, texts = shown_counts(outcome.n_rows, [n for _, n in ranked], posted)
    return [
        f"explanation {proof.path.name}: {proof.causes[b][1]}: {t} rows"
        for (b, _), t in zip(ranked, texts, strict=True)
    ]


def _kept(lines: list[str]) -> list[str]:
    """An item's evidence without any earlier explanation's lines."""
    return [line for line in lines if not line.startswith("explanation ")]


def apply_outcomes(
    items: list[dict], proof: Explanation, found: dict[str, Outcome]
) -> None:
    """Move each fully explained item to `cause`; note the rest in place."""
    for item in items:
        outcome = found.get(item["id"])
        if outcome is None:
            continue
        evidence = _kept(item.get("evidence") or [])
        posted = _kept(item.get("evidence_posted") or item.get("evidence") or [])
        if outcome.explained:
            item.update(
                suggestion="cause",
                cause=[
                    {
                        "side": proof.causes[b][0],
                        "step": b,
                        "label": proof.causes[b][1],
                        "n_rows": n,
                    }
                    for b, n in outcome.counts.most_common()
                ],
                proof={
                    "kind": "query",
                    "path": proof.recorded,
                    "fingerprint": proof.fingerprint,
                },
                evidence=_explanation_lines(proof, outcome, False),
                evidence_posted=_explanation_lines(proof, outcome, True),
            )
            continue
        # A bucket's groups reach `cause` only through its explanation.
        item.update(suggestion="investigate", cause=None, proof=None)
        item["evidence"] = [outcome.gap_line(proof.path.name), *evidence]
        item["evidence_posted"] = [
            f"explanation {proof.path.name} does not explain every row",
            *posted,
        ]


def note(items: list[dict], ids: set[str], line: str, name: str) -> None:
    """Add why explanation `name` did not run to each listed item's evidence.

    The posted copy is a fixed line: a refusal's text stays local.
    """
    for item in items:
        if item["id"] in ids:
            evidence = item.get("evidence") or []
            posted = item.get("evidence_posted") or evidence
            item["evidence"] = [line, *evidence]
            item["evidence_posted"] = [
                f"explanation {name} not run; see the terminal",
                *posted,
            ]


def _bucket_items(run: RunResult, comparison: str, bucket: str):
    return [
        (item.id, g)
        for item, g in sort._entries(run)
        if isinstance(g, Group) and g.comparison_id == comparison and g.bucket == bucket
    ]


# `link_cells`' evidence lines, which the next link replaces.
_COVERED = "every differing cell is covered by explained or decided groups"
_UNCOVERED = "differing cells are not covered"
_NO_CELLS = "the run lists no differing cells to link"


def _covering(
    run: RunResult, comparison: str, entries
) -> tuple[list[tuple[str | None, Group]], dict[str, tuple]]:
    """A comparison's groups, each with its open item id (None when a `group`
    decision closed it), and each closed group's key with its decision."""
    groups: list[tuple[str | None, Group]] = [
        (i.id, g)
        for i, g in entries
        if isinstance(g, Group) and g.comparison_id == comparison
    ]
    closed = {}
    for d, g in run.applied.quiet:
        if g.comparison_id == comparison:
            groups.append((None, g))
            closed[sort._open_key(g)] = (d, g)
    return groups, closed


def link_cells(
    run: RunResult,
    items: list[dict],
    comparison: str | None = None,
    cfg: ViewConfig | None = None,
    open_cells: dict[str, list[dict]] | None = None,
) -> dict[str, tuple[int, int]]:
    """Move each cell set whose differing cells are all covered to `cause`.

    A cell is covered when the groups with a row in it (`coverage`) are each
    closed by a `group` decision (`run.applied.quiet`) or an open item in
    `cause`. A cell `compare` saved as `kind: formula` belongs to the
    comparison's formula difference, its own item, and is left out of the
    cell set. Any other cell with no group in it (a run saved before cells
    carried a kind), or one that cannot be placed, stays open. A `formula`
    item is never linked here.

    Args:
        open_cells: Filled, per cell-set item id, with each cell left open:
            the cell, the groups in it (`[id, bucket, suggestion]`) and
            `why`. For the terminal only: a cell's dims and values are not
            masked.

    Returns:
        Per cell-set item id: the differing cells left open, and all of them.
    """
    entries = sort._entries(run)
    by_id = {i["id"]: i for i in items}
    by_cmp = {c.id: c for c in (cfg.comparisons if cfg else [])}
    out = {}
    for item, _ in entries:
        if item.kind != "cells" or (comparison and item.comparison != comparison):
            continue
        spec = by_cmp.get(item.comparison)
        groups, closed = _covering(run, item.comparison, entries)
        pool = [g for _, g in groups]
        ids = {id(g): gid for gid, g in groups}
        # The formula item holds a run's formula cells.
        cells = [
            c
            for c in run.diff_cells
            if c["comparison"] == item.comparison and c.get("kind") != "formula"
        ]
        used: dict[str, None] = {}
        shut: dict[str, None] = {}
        left: list[dict] = []
        for cell in cells:
            why = (
                coverage.unplaced(cell, pool, spec)
                if spec
                else "the comparison is not in the validation file"
            )
            if why is not None:
                left.append(
                    {"cell": cell, "groups": [], "why": f"cannot be placed: {why}"}
                )
                continue
            inside = [g for g in pool if coverage.has_rows_in(g, cell)]
            if not inside:
                left.append(
                    {"cell": cell, "groups": [], "why": "no unmatched row lies in it"}
                )
                continue
            said = []
            short = 0
            for g in inside:
                gid = ids[id(g)]
                if gid is None:
                    said.append([sort._open_key(g), g.bucket, "closed by a decision"])
                    continue
                state = by_id[gid]["suggestion"]
                said.append([gid, g.bucket, state])
                short += state != "cause"
            if short:
                left.append(
                    {
                        "cell": cell,
                        "groups": said,
                        "why": f"{short} of its {len(inside)} groups are not in cause",
                    }
                )
                continue
            for g in inside:
                if (gid := ids[id(g)]) is None:
                    shut[sort._open_key(g)] = None
                else:
                    used[gid] = None
        out[item.id] = (len(left), len(cells))
        if open_cells is not None and left:
            open_cells[item.id] = left
        target = by_id[item.id]
        if cells and not left:
            merged: dict[tuple, dict] = {}
            for gid in used:
                for c in by_id[gid]["cause"] or []:
                    k = (c["side"], c["step"], c["label"])
                    entry = merged.setdefault(k, {**c, "n_rows": 0})
                    entry["n_rows"] += c["n_rows"] or 0
            # A closed group's rows are explained by the decision closing it.
            for key in shut:
                d, g = closed[key]
                k = ("both", "decision", f"closed by {d.id}")
                entry = merged.setdefault(
                    k, {"side": k[0], "step": k[1], "label": k[2], "n_rows": 0}
                )
                entry["n_rows"] += g.n_rows
            named = [*used, *([f"{len(shut)} closed by a decision"] if shut else [])]
            line = f"{_COVERED}: {', '.join(named)}"
            target.update(
                suggestion="cause",
                cause=list(merged.values()),
                proof={"kind": "cells", "groups": list(used), "closed": list(shut)},
                evidence=[line],
                evidence_posted=[line],
            )
        else:
            if target.get("suggestion") == "cause":
                target.update(suggestion="investigate", cause=None, proof=None)
            if not cells:
                line = posted = f"{_NO_CELLS}; `compare` again"
            else:
                line = f"{len(left)} of {len(cells)} {_UNCOVERED}"
                posted = f"{mask(len(left))} of {mask(len(cells))} {_UNCOVERED}"
            target["evidence"] = [line, *_unlinked(target.get("evidence"))]
            target["evidence_posted"] = [
                posted,
                *_unlinked(target.get("evidence_posted")),
            ]
    return out


def _shown(value: float | None) -> str:
    return "nothing" if value is None else f"{value:.4g}"


def open_cell_lines(left: list[dict]) -> list[str]:
    """Each cell a cell set left open, for the terminal: its cut, its dims,
    both sides' values, the groups it matched and why it stayed open."""
    lines = []
    for o in left:
        cell = o["cell"]
        dims = ", ".join(f"{k}={v}" for k, v in cell["dims"]) or "(no dims)"
        groups = (
            "; ".join(f"{gid} {bucket} ({said})" for gid, bucket, said in o["groups"])
            or "none"
        )
        lines += [
            f"- {dims} | cut {cell.get('cut', '{}')} | Cube "
            f"{_shown(cell.get('cube'))}, dashboard {_shown(cell.get('dashboard'))}",
            f"  groups: {groups}",
            f"  open: {o['why']}",
        ]
    return lines


def _unlinked(lines: list[str] | None) -> list[str]:
    """Evidence without an earlier link line."""
    return [
        e
        for e in lines or []
        if not e.startswith(_COVERED) and _UNCOVERED not in e and _NO_CELLS not in e
    ]


@dataclass
class Ran:
    """One stored explanation's run: its outcomes per item, or why it did not run."""

    proof: Explanation
    items: list[tuple[str, Group]]
    found: dict[str, Outcome] | None = None
    why: str = ""
    # Its cause-student counts per cell and cut (`cause_students`).
    students: list[dict] = field(default_factory=list)


def siblings(cfg: ViewConfig, comparison: Comparison) -> list[Comparison]:
    """The other comparisons that reconcile the same rows (`row_population`)."""
    key = row_population(comparison)
    return [
        c
        for c in cfg.comparisons
        if key is not None and c.id != comparison.id and row_population(c) == key
    ]


def _shared(
    cfg: ViewConfig, directory: Path, proof: Explanation, comparison: Comparison
) -> list[Comparison]:
    """The siblings an explanation also classifies: those with no explanation
    of their own.

    A sibling's own explanation wins even when it fails: its refusal shows, rather
    than another explanation standing in for it.
    """
    return [
        c
        for c in siblings(cfg, comparison)
        if not explanation_path(directory, c.id, proof.bucket).is_file()
    ]


def run_stored(
    cfg: ViewConfig,
    run: RunResult,
    directory: Path,
    *,
    wh: Warehouse,
    cube: Cube,
    prepared: trace.Prepared | None = None,
    progress_dir: Path | None = None,
    comparisons: set[str] | None = None,
    ticker: Ticker | None = None,
) -> list[Ran]:
    """Run every stored explanation of the view on the run's saved rows. Call inside
    `wh.budget`.

    An explanation also runs on each comparison that reconciles the same rows and
    has no explanation of its own for the bucket (`siblings`). Each pair's outcome
    is kept in `progress_dir` (`explain_progress`) as it finishes, and a later triage
    reuses one whose explanation and open items still match, once the comparison's
    SQL still matches the run (`pipeline.row_sides`, compile only) and its
    saved rows still carry the run's labels (`require_saved`).
    The rest are priced together first, and a total over a cap refuses
    before any runs; then they run one at a time. An explanation that cannot run (a
    failed check, its saved rows gone, a BigQuery or Cube error, its SQL no
    longer the run's) keeps why and moves nothing; the rest still run.

    Args:
        progress_dir: Where finished outcomes are kept; None keeps none.
        comparisons: Run only these comparisons' explanations; another's outcome is
            reused when kept, else it reads "not run: outside --comparison".
        ticker: Prints a progress line after each explanation runs.

    Raises:
        CostCapError: The explanations to run, together, would pass the run's or the
            day's cap.
    """
    by_id = {c.id: c for c in cfg.comparisons}
    prepared = prepared or trace.Prepared()
    kept = explain_progress.load(progress_dir) if progress_dir is not None else {}
    out: list[Ran] = []
    todo: list[tuple[Ran, Comparison, str, set[str], str]] = []
    reused = 0
    for path in sorted(directory.glob("*__*.sql")) if directory.is_dir() else []:
        try:
            proof = read_explanation(path)
        except (OSError, pipeline.Refusal) as exc:
            print(f"Explanation {path.name} skipped: {exc}")
            continue
        if (own := by_id.get(proof.comparison)) is None:
            continue
        for comparison in [own, *_shared(cfg, directory, proof, own)]:
            items = _bucket_items(run, comparison.id, proof.bucket)
            if not items:
                continue
            ran = Ran(proof, items)
            out.append(ran)
            done = explain_progress.key(
                proof.fingerprint,
                comparison.id,
                proof.bucket,
                run.fingerprints.get(comparison.id, {}),
                [sort._open_key(g) for _, g in items],
            )
            # A kept outcome holds only while the run's SQL and saved rows do:
            # check both, compile only, before reusing or running anything.
            try:
                if prepared.schools is None:
                    prepared.schools = network_schools(wh)
                sides = prepared.row_sides(cfg, comparison, run, wh, cube)
                table = require_saved(wh, cfg, run, comparison)
            except _CANNOT_RUN as exc:
                ran.why = f"explanation {path.name} not run: {exc}"
                continue
            except GoogleAPIError as exc:
                ran.why = f"explanation {path.name} not run ({bigquery_said(exc)})"
                continue
            if done in kept:
                _from_progress(ran, kept[done])
                reused += 1
                continue
            if comparisons is not None and comparison.id not in comparisons:
                ran.why = f"explanation {path.name} not run: {_OUTSIDE}"
                continue
            try:
                sql, literals = explanation_sql(
                    wh,
                    cfg,
                    comparison,
                    sides,
                    proof,
                    items,
                    run.moment_of(comparison.id),
                    table=table,
                    moved=prepared.moved_at(run.moment_of(comparison.id)),
                    students=True,
                )
            except _CANNOT_RUN as exc:
                ran.why = f"explanation {path.name} not run: {exc}"
                continue
            except GoogleAPIError as exc:
                ran.why = f"explanation {path.name} not run ({bigquery_said(exc)})"
                continue
            todo.append((ran, comparison, sql, literals, done))

    ready = []
    total = 0.0
    for job, price in zip(todo, trace._dry_runs(wh, [t[2] for t in todo]), strict=True):
        if isinstance(price, GoogleAPIError):
            job[
                0
            ].why = (
                f"explanation {job[0].proof.path.name} not run ({bigquery_said(price)})"
            )
        else:
            total += price
            ready.append(job)
    if ready or reused:
        print(
            f"Explanations: {len(ready)} to run, ${total:.2f} (dry run); {reused} "
            f"reused from {explain_progress.FILE}."
        )
    wh.refuse_past_caps(total)
    for ran, comparison, sql, literals, done in ready:
        name = ran.proof.path.name
        try:
            rows = wh.rows(sql, timeout_s=TIMEOUT_S)
            ran.found = outcomes(rows, ran.proof, ran.items, literals)
            ran.students = cause_students(rows, ran.proof, comparison)
        except (pipeline.Refusal, CostCapError) as exc:
            ran.why = f"explanation {name} not run: {exc}"
        except GoogleAPIError as exc:
            # As `run_explanation` words it, so the evidence reads the same.
            ran.why = (
                f"explanation {name} not run: {name}: BigQuery refused it "
                f"({bigquery_said(exc)})"
            )
        else:
            if progress_dir is not None:
                explain_progress.save(progress_dir, done, _to_progress(ran))
        if ticker is not None:
            ticker.say("sort explain", name, wh.spent)
    outside = [r for r in out if r.why.endswith(_OUTSIDE)]
    for ran in out:
        if ran.why and ran not in outside:
            print(ran.why)
    if outside:
        print(
            f"{len(outside)} explanation{'s' if len(outside) != 1 else ''} outside "
            "--comparison not run (no kept outcome)."
        )
    return out


# Why an explanation of a comparison `sort --comparison` left out did not run.
_OUTSIDE = "outside --comparison"
# What keeps one explanation from running, besides a BigQuery error.
_CANNOT_RUN = (pipeline.Refusal, CostCapError, ViewHistoryError, CubeError, CubeRefusal)


def _to_progress(ran: Ran) -> dict:
    """A finished explanation's outcome as `explain_progress` keeps it: by open
    key, counts only."""
    found = ran.found or {}
    return {
        "found": {
            sort._open_key(g): {
                "n_rows": found[item_id].n_rows,
                "counts": dict(found[item_id].counts),
                "unexplained": found[item_id].unexplained,
            }
            for item_id, g in ran.items
            if item_id in found
        },
        "students": ran.students,
    }


def _from_progress(ran: Ran, kept: dict) -> None:
    """Fill `ran` from a kept outcome (`_to_progress`)."""
    by_key = kept["found"]
    ran.found = {
        item_id: Outcome(
            n_rows=o["n_rows"],
            counts=Counter(o["counts"]),
            unexplained=o["unexplained"],
        )
        for item_id, g in ran.items
        if (o := by_key.get(sort._open_key(g))) is not None
    }
    ran.students = kept["students"]


def _run_one(
    cfg: ViewConfig,
    run: RunResult,
    comparison: Comparison,
    proof: Explanation,
    wh: Warehouse,
    cube: Cube,
    prepared: trace.Prepared,
) -> Ran | None:
    """Run `proof` on one comparison's open groups of its bucket, if any."""
    path = proof.path
    bucket_items = _bucket_items(run, comparison.id, proof.bucket)
    if not bucket_items:
        return None
    ran = Ran(proof, bucket_items)
    try:
        if prepared.schools is None:
            prepared.schools = network_schools(wh)
        table = require_saved(wh, cfg, run, comparison)
        ran.found = run_explanation(
            wh,
            cfg,
            comparison,
            prepared.row_sides(cfg, comparison, run, wh, cube),
            proof,
            bucket_items,
            run.moment_of(comparison.id),
            prepared.moved_at(run.moment_of(comparison.id)),
            ran.students,
            table=table,
        )
    except _CANNOT_RUN as exc:
        ran.why = f"explanation {path.name} not run: {exc}"
    except GoogleAPIError as exc:
        ran.why = f"explanation {path.name} not run ({bigquery_said(exc)})"
    if ran.why:
        print(ran.why)
    return ran


def explained(runs: list[Ran]) -> set[tuple]:
    """The `trace.item_key` of every group an explanation fully explains."""
    return {
        trace.item_key(g)
        for r in runs
        for item_id, g in r.items
        if r.found and r.found[item_id].explained
    }


def apply_runs(
    run: RunResult,
    items: list[dict],
    runs: list[Ran],
    cfg: ViewConfig,
    loaded: dict | None = None,
) -> None:
    """Sort the items by the explanations' runs, then link cell sets."""
    for r in runs:
        if r.found is not None and loaded is not None:
            keep_students(loaded, _comparison_of(r), r.proof.bucket, r.students)
        if r.found is None:
            note(items, {i for i, _ in r.items}, r.why, r.proof.path.name)
        else:
            apply_outcomes(items, r.proof, r.found)
    link_cells(run, items, cfg=cfg)


# --- the command -------------------------------------------------------------------


def _load_sort(run: RunResult, run_json: Path) -> tuple[Path, dict]:
    found = run_json.parent / "triage.json"
    again = f"run `sort` for {run.moment.start:%Y-%m-%d %H:%M} UTC first"
    if not found.exists():
        raise pipeline.Refusal(f"{run.view}: no sort of the latest run; {again}")
    try:
        loaded = json.loads(found.read_text())
    except json.JSONDecodeError as exc:
        raise pipeline.Refusal(
            f"{run.view}: triage.json is unreadable; {again}"
        ) from exc
    if not isinstance(loaded, dict) or loaded.get("moment") != sort._moment(run):
        raise pipeline.Refusal(f"{run.view}: triage.json is of another moment; {again}")
    if set(sort.open_keys(run)) - set(loaded.get("open") or []):
        raise pipeline.Refusal(
            f"{run.view}: the latest run has open items its sort lacks; {again}"
        )
    return found, loaded


def _mark(run: RunResult, items: list[dict], cfg: ViewConfig) -> None:
    """Refresh the decision marks after a re-sort, as `sort` writes them."""
    for item in items:
        item.pop("decisions", None)
        item.pop("decided", None)
        for key in ("evidence", "evidence_posted"):
            item[key] = [
                line
                for line in item.get(key) or []
                if not line.startswith(("decision ", "decisions "))
            ]
    sort.mark_decided(run, items, cfg.decisions, note=True)


def _save_sort(path: Path, loaded: dict, items: list[dict]) -> None:
    loaded["items"] = sorted(
        items, key=lambda i: sort.SUGGESTIONS.index(i["suggestion"])
    )
    path.write_text(json.dumps(loaded, indent=1))


def _report(items: list[dict], wanted: set[str] | None) -> None:
    for item in items:
        if wanted and item["id"] not in wanted:
            continue
        print(f"- {item['id']}: {item['suggestion']}")
        for line in item.get("evidence") or []:
            print(f"    {line}")


def explain(
    cfg: ViewConfig,
    view_file: Path,
    *,
    wh: Warehouse,
    cube: Cube,
    max_usd: float,
    cache_root: Path,
    comparison: str,
    bucket: str,
    sql: Path | None = None,
    causes: list[str] | None = None,
    items: list[str] | None = None,
) -> int:
    """Run a new or edited explanation once, save it, and re-sort the triage.

    The comparison's cell set is linked again (`link_cells`); each cell it
    leaves open prints with why, in the terminal only.

    Args:
        cfg: The view's config.
        view_file: Its validation file; explanations are saved beside it.
        wh: The warehouse.
        cube: Cube, to rebuild the run's row SQL.
        max_usd: The cap for this command.
        cache_root: The local cache holding the run and its triage.
        comparison: The comparison the explanation covers.
        bucket: One of `EXPLAINABLE`.
        sql: The explanation's SQL; it may carry a `-- cause` block. Defaults to
            the stored explanation, to re-run it after an edit.
        causes: `<bucket>=<side>:<plain words>` per bucket, added to (and
            replacing entries of) the SQL's own block.
        items: Triage item ids to print; every item of the bucket is explained
            either way.

    Returns:
        0.

    Raises:
        pipeline.Refusal: No triage of the latest run; an unknown comparison
            or bucket; or an explanation that fails a check.
        CostCapError: The explanation would pass a cap.
    """
    run, run_json = results.latest_run(cfg, cache_root)
    path, loaded = _load_sort(run, run_json)
    all_items = loaded.get("items", [])
    target = next((c for c in cfg.comparisons if c.id == comparison), None)
    if target is None:
        raise pipeline.Refusal(f"{cfg.view}: no comparison {comparison!r}")
    wanted = set(items or []) or None

    if bucket not in EXPLAINABLE:
        raise pipeline.Refusal(f"--bucket must be one of {', '.join(EXPLAINABLE)}")
    stored = explanation_path(explanations_dir(view_file, cfg.view), comparison, bucket)
    source = sql or stored
    if not source.is_file():
        raise pipeline.Refusal(f"{source}: no such explanation; pass --sql <file>")
    block, reproduce, body = split_explanation(source.read_text())
    for flag in causes or []:
        b, side, words = parse_cause_flag(flag)
        block[b] = (side, words)
    proof = Explanation(stored, comparison, bucket, block, body, reproduce)
    for b, query in reproduce.items():
        if b not in block:
            raise pipeline.Refusal(
                f"-- reproduce {b}: the explanation has no cause {b}; name a bucket "
                "of its `-- cause` block"
            )
        try:
            check_reproduce(query, grain_names(target), identifying(target))
        except pipeline.Refusal as exc:
            raise pipeline.Refusal(f"-- reproduce {b}: {exc}") from exc
    bucket_items = _bucket_items(run, comparison, bucket)
    if not bucket_items:
        raise pipeline.Refusal(f"{comparison} {bucket}: no open row group to explain")
    if wanted and (unknown := wanted - {i for i, _ in bucket_items}):
        raise pipeline.Refusal(
            f"--items: {len(unknown)} id(s) are no open item of {comparison} {bucket}"
        )

    with wh.budget(max_usd):
        for b, query in reproduce.items():
            try:
                usd = wh.estimate(query)
            except GoogleAPIError as exc:
                raise pipeline.Refusal(
                    f"-- reproduce {b}: BigQuery refused it ({bigquery_said(exc)})"
                ) from exc
            print(f"Reproduce {b}: dry run OK, ${usd:.2f} on today's tables.")
        prepared = trace.Prepared(schools=network_schools(wh))
        students: list[dict] = []
        found = run_explanation(
            wh,
            cfg,
            target,
            prepared.row_sides(cfg, target, run, wh, cube),
            proof,
            bucket_items,
            run.moment_of(target.id),
            prepared.moved_at(run.moment_of(target.id)),
            students,
            table=require_saved(wh, cfg, run, target),
        )
        # The comparisons holding the same rows: the explanation classifies theirs
        # too, unless one has its own. A refusal there keeps this explanation.
        shared = [
            r
            for c in _shared(cfg, stored.parent, proof, target)
            if (r := _run_one(cfg, run, c, proof, wh, cube, prepared))
        ]

    stored.parent.mkdir(parents=True, exist_ok=True)
    stored.write_text(proof.text)
    apply_outcomes(all_items, proof, found)
    keep_students(loaded, target.id, proof.bucket, students)
    apply_runs(run, all_items, shared, cfg, loaded)
    left: dict[str, list[dict]] = {}
    link_cells(run, all_items, comparison, cfg, left)
    _mark(run, all_items, cfg)
    _save_sort(path, loaded, all_items)
    moved = sum(1 for o in found.values() if o.explained)
    print(f"Saved {stored}: {moved} of {len(found)} items explained.")
    reported = set(found)
    for r in shared:
        sibling = _comparison_of(r)
        if r.found is None:
            print(f"Also {sibling}: not run; see above.")
            continue
        n = sum(1 for o in r.found.values() if o.explained)
        print(f"Also {sibling} (same rows): {n} of {len(r.found)} items explained.")
        reported |= set(r.found)
    _report(all_items, wanted or reported)
    for item_id, open_cells in left.items():
        print(f"{item_id}: the cells left open (local only, not masked):")
        print("\n".join(open_cell_lines(open_cells)))
    print(f"Saved {path}")
    return 0


def _comparison_of(ran: Ran) -> str:
    return ran.items[0][1].comparison_id
