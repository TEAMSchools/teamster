"""Prove row groups with stored classification queries: `triage confirm`.

The trace only leads. A person proves causes with ONE classification query per
comparison and bucket: a `CASE` in lineage order that names each unmatched
row's first failing model predicate, with an `UNEXPLAINED` else-bucket. It is
stored as SQL only, with no data, at
`<validation dir>/proofs/<view>/<comparison>__<bucket>.sql`, under a leading
comment block that maps each bucket to its side and plain words:

    -- cause C1 = dashboard: WPP assessments are left off the dashboard

The query reads the run's unmatched rows of its comparison and bucket through
the placeholder `{unmatched}`, which the tool fills from the run's reconcile:
`__row` (a row id), `item_key`, `side`, the group-by columns, the grain under
its Cube names, and `__rn` (the row's duplicate number on its grain). It
returns exactly `__row, cause`, one row per unmatched row. The tool counts:
its own outer query joins the proof back to `{unmatched}` and returns only
item keys, cause literals and counts, refusing a row the proof drops or
repeats and a cause that is no string literal of the proof. Every `triage`
re-runs every stored proof on the current run's rows; an item whose rows a
proof fully explains (no `UNEXPLAINED` row) goes to `cause`. A cell set goes
to `cause` when every differing cell's rows lie in groups in `cause`.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import sqlglot
from google.api_core.exceptions import GoogleAPIError
from sqlglot import exp
from sqlglot.errors import SqlglotError
from sqlglot.tokens import TokenType

from . import compare, decisions, pipeline, trace, triage
from .bq import CostCapError, ViewHistoryError, Warehouse
from .compare import Group
from .config import Comparison, ViewConfig, id_like
from .cube_client import Cube, CubeError, CubeRefusal, network_schools
from .moment import Build
from .report import RunResult, shown_counts
from .trace import TIMEOUT_S, TRACED, _failure

# The buckets a stored proof classifies: the one-sided rows the trace leads on,
# and rows both sides hold whose values differ.
PROVABLE = (*TRACED, "value_differs")

PLACEHOLDER = "{unmatched}"
UNEXPLAINED = "UNEXPLAINED"
COLUMNS = ("__row", "cause")
SIDES = ("cube", "dashboard")
# Trunk lints and formats every committed `.sql` file; a proof is not dbt SQL,
# and a reformat would only churn it. A proof with no QUALIFY or GROUP BY ALL
# gets a non-blocking `ignore-does-nothing` note for the second line.
HEADER = (
    "-- trunk-ignore-all(sqlfluff)",
    "-- trunk-ignore-all(sql-banned-syntax)",
    "-- fmt: off",
)
_BUCKET = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,63}")
_BLOCK = re.compile(
    r"--\s*cause\s+(?P<bucket>\S+)\s*=\s*(?P<side>\S+?)\s*:\s*(?P<words>.*\S)\s*"
)
_STRINGS = (
    TokenType.STRING,
    TokenType.RAW_STRING,
    TokenType.BYTE_STRING,
    TokenType.NATIONAL_STRING,
)


def proofs_dir(view_file: Path, view: str) -> Path:
    """Where a view's proofs live: beside its validation file."""
    return view_file.parent / "proofs" / view


def proof_path(directory: Path, comparison: str, bucket: str) -> Path:
    return directory / f"{comparison}__{bucket}.sql"


@dataclass(frozen=True)
class Proof:
    """One stored proof: its bucket map and its SQL."""

    path: Path
    comparison: str
    bucket: str
    causes: dict[str, tuple[str, str]]
    body: str

    @property
    def text(self) -> str:
        return compose(self.causes, self.body)

    @property
    def recorded(self) -> str:
        """The path `triage.json` records: relative to the validation file."""
        return "/".join(self.path.parts[-3:])

    @property
    def fingerprint(self) -> str:
        return fingerprint(self.causes, self.body)


def fingerprint(causes: dict[str, tuple[str, str]], body: str) -> str:
    """The proof's bucket map and its SQL, blind to comments, case and spacing."""
    text = json.dumps(
        [
            sorted((b, list(v)) for b, v in causes.items()),
            decisions.sql_fingerprint(body),
        ]
    )
    return hashlib.sha256(text.encode()).hexdigest()


def file_fingerprint(path: Path) -> str | None:
    """A stored proof file's fingerprint, or None when it is gone or unreadable."""
    try:
        return read_proof(path).fingerprint
    except (OSError, pipeline.Refusal):
        return None


def compose(causes: dict[str, tuple[str, str]], body: str) -> str:
    """The proof file: the lint opt-outs, its bucket map, then the SQL."""
    block = [f"-- cause {b} = {side}: {words}" for b, (side, words) in causes.items()]
    return "\n".join([*HEADER, *block]) + "\n\n" + body.strip() + "\n"


def split_block(text: str) -> tuple[dict[str, tuple[str, str]], str]:
    """A proof's leading `-- cause` block and the SQL after it.

    The lint opt-outs and blank lines above or inside the block are skipped.

    Raises:
        pipeline.Refusal: A line of the block names no side or no words.
    """
    causes: dict[str, tuple[str, str]] = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("-- cause"):
            bucket, side, words = _cause(line)
            causes[bucket] = (side, words)
        elif line and line not in HEADER:
            break
        i += 1
    return causes, "\n".join(lines[i:]).strip()


def _cause(line: str) -> tuple[str, str, str]:
    m = _BLOCK.fullmatch(line)
    if not m:
        raise pipeline.Refusal(
            "cannot read a `-- cause` line: write "
            "`-- cause <bucket> = <side>: <plain words>`"
        )
    return _checked(m["bucket"], m["side"], m["words"])


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
    if id_like(words):
        raise pipeline.Refusal(
            f"bucket {bucket}: the words hold an email or an ID-like number; "
            "a proof is committed, so name no student or staff member"
        )
    return bucket, side, words


def parse_cause_flag(flag: str) -> tuple[str, str, str]:
    """`<bucket>=<side>:<plain words>`, checked."""
    bucket, eq, rest = flag.partition("=")
    side, colon, words = rest.partition(":")
    if not eq or not colon:
        raise pipeline.Refusal("a --cause flag reads <bucket>=<side>:<plain words>")
    return _checked(bucket.strip(), side.strip(), words)


def read_proof(path: Path) -> Proof:
    """A stored proof, named `<comparison>__<bucket>.sql`."""
    comparison, sep, bucket = path.stem.rpartition("__")
    if not sep or bucket not in PROVABLE:
        raise pipeline.Refusal(
            f"{path.name}: name a proof <comparison>__<{'|'.join(PROVABLE)}>.sql"
        )
    causes, body = split_block(path.read_text())
    return Proof(path, comparison, bucket, causes, body)


# --- the checks -------------------------------------------------------------------


def grain_names(comparison: Comparison) -> set[str]:
    """Every name a grain column goes by, lowercased."""
    grain = comparison.rows.grain if comparison.rows else []
    return {n.lower() for p in grain for n in (p.cube, p.dashboard)}


def identifying(comparison: Comparison) -> set[str]:
    """The student column's names: a literal compared with one names a row."""
    grain = comparison.rows.grain if comparison.rows else []
    return {n.lower() for p in grain[:1] for n in (p.cube, p.dashboard)}


def _identifies(column: str, student: set[str]) -> bool:
    """A column whose value can name a student or staff member.

    The student grain column, a name, number or email column, or a student
    id or key. Another id (`assessment_id`) names no one, so a proof may
    compare it with a literal.
    """
    name = column.lower()
    return (
        name in student
        or name.endswith(("_number", "_name", "_email"))
        or ("student" in name and name.endswith(("_id", "_key")))
    )


def _id_like(column: str, student: set[str]) -> bool:
    """A column a cause may not select: any identifier, not only a person's."""
    return _identifies(column, student) or column.lower().endswith(triage._ID_SUFFIXES)


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
            f"the proof does not parse as BigQuery SQL: {type(exc).__name__}"
        ) from exc
    for token in tokens:
        texts = list(token.comments)
        if token.token_type in _STRINGS:
            texts.append(token.text)
        if any(id_like(t) for t in texts):
            raise pipeline.Refusal(
                "the proof holds an email or an ID-like number in a comment or "
                "a string; a proof is committed, so name no student or staff member"
            )


def check_sql(body: str, grain: set[str], student: set[str] = frozenset()) -> set[str]:
    """Refuse a proof that could return or name a row, before it runs.

    Args:
        body: The proof's SQL, without its `-- cause` block.
        grain: Every grain column name, lowercased.
        student: The student column's names, lowercased. No literal may be
            compared with them, nor with a column `_identifies` names a
            person by; `cause` may select no identifier column at all.

    Returns:
        The proof's string literals: the only values a `cause` may take.

    Raises:
        pipeline.Refusal: No `{unmatched}`; SQL that does not parse; an
            outer SELECT returning `*`, anything but `__row` and `cause`, or a
            grain or identifying column's value as `cause`; no string literal
            to name a cause; an ID-like value or an email in a comment or a
            string; or a literal compared with an identifying column.
    """
    if PLACEHOLDER not in body:
        raise pipeline.Refusal(f"the proof never reads {PLACEHOLDER}")
    _scan_text(body)
    try:
        tree = sqlglot.parse_one(body.replace(PLACEHOLDER, "__u"), read="bigquery")
    except SqlglotError as exc:
        raise pipeline.Refusal(
            f"the proof does not parse as BigQuery SQL: {type(exc).__name__}"
        ) from exc
    selects = list(_outer_selects(tree))
    causes: list[exp.Expression] = []
    if not selects:
        raise pipeline.Refusal("the proof is not a SELECT")
    for select in selects:
        names = []
        for projection in select.expressions:
            if isinstance(projection, exp.Star) or (
                isinstance(projection, exp.Column)
                and isinstance(projection.this, exp.Star)
            ):
                raise pipeline.Refusal("the proof selects *; return only __row, cause")
            name = projection.alias_or_name.lower()
            names.append(name)
            value = projection.unalias()
            if name == "__row" and not (
                isinstance(value, exp.Column) and value.name.lower() == "__row"
            ):
                raise pipeline.Refusal(
                    f"the proof's __row must be {PLACEHOLDER}'s own __row"
                )
            if name == "cause":
                causes.append(value)
            if name == "cause" and any(
                c in grain or _id_like(c, student) for c in _selected(value)
            ):
                raise pipeline.Refusal(
                    "the proof's cause selects a grain or identifying column; "
                    "name each cause with a string literal"
                )
        if sorted(names) != sorted(COLUMNS):
            raise pipeline.Refusal(
                f"the proof returns {len(names)} column(s) other than __row and "
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
                "the proof compares an identifying column with a literal: never "
                "name a row by its value"
            )
    literals = {lit.this for lit in tree.find_all(exp.Literal) if lit.is_string}
    if not literals:
        raise pipeline.Refusal(
            "the proof has no string literal; name each cause with one"
        )
    for value in causes:
        _check_default(value)
    for table in _unpinned(tree):
        print(
            f"warning: the proof reads {table} with no project and dataset, so it "
            "reads the table as it is now, not as of the run; write it "
            "`teamster-332318`.`<dataset>`.`<table>`"
        )
    return literals


def _check_default(value: exp.Expression) -> None:
    """Refuse a cause that is not a CASE ending in `ELSE 'UNEXPLAINED'`.

    A catch-all cause would file the rows of a new cause, in a later run,
    under an old one with no one looking.

    Raises:
        pipeline.Refusal: A bare cause, or a CASE (at any depth) with no ELSE
            or another one.
    """
    if not isinstance(value, exp.Case):
        raise pipeline.Refusal(
            f"the proof's cause must be a CASE ending in ELSE '{UNEXPLAINED}'"
        )
    for case in value.find_all(exp.Case):
        default = case.args.get("default")
        if not (
            isinstance(default, exp.Literal)
            and default.is_string
            and default.this == UNEXPLAINED
        ):
            raise pipeline.Refusal(
                f"every CASE of the proof's cause must end in ELSE '{UNEXPLAINED}', "
                "so a row of a new cause is never filed under an old one"
            )


def _unpinned(tree: exp.Expression) -> list[str]:
    """Tables the proof names without a project and dataset, CTEs aside."""
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
    cfg: ViewConfig,
    comparison: Comparison,
    sides: pipeline.RowSides,
    bucket: str,
    items: list[tuple[str, Group]],
) -> tuple[str, str]:
    """Every unmatched row of the bucket, as the run's reconcile finds them.

    Returns:
        The reconcile's CTEs, and the SELECT over them that returns `__row`
        (a row id from the grain keys and the duplicate number), `item_key`
        (the triage item id of the row's group, NULL for a row no open group
        holds), `side` (the side holding the row), the group-by columns as
        text, the grain under its Cube names (as the side holding the row
        types it), and `__rn`. A `value_differs` row's side reads `both`.
    """
    if comparison.rows is None:
        raise pipeline.Refusal(f"comparison {comparison.id!r} has no rows to prove")
    # A value-differing row is on both sides; its grain is read as Cube types it.
    side = "d" if bucket == "dashboard_only" else "c"
    held = {"cube_only": "cube", "dashboard_only": "dashboard"}.get(bucket, "both")
    grain = comparison.rows.grain
    extra = [
        f"{side}.{p.cube if side == 'c' else p.dashboard} AS __g{i}"
        for i, p in enumerate(grain)
    ]
    dims = pipeline.group_dims(comparison)
    ctes, _ = compare._joined(
        pipeline.wrap_cube(
            sides.cube_rows_sql,
            cfg.view,
            sides.columns,
            pipeline._date_cubes(cfg),
            None,
        ),
        sides.dashboard.sql,
        comparison.rows,
        dims,
        pipeline._filter_flags(comparison),
        keys=True,
        extra=extra,
    )
    whens = []
    for item_id, g in items:
        nulls = set(g.nulls)
        test = " AND ".join(
            f"{column} IS NULL"
            if column in nulls
            else f"{column} = {pipeline._lit(value)}"
            for column, value in g.dims
        )
        whens.append(f"WHEN {test or 'TRUE'} THEN {pipeline._lit(item_id)}")
    key = f"CASE {' '.join(whens)} END" if whens else "CAST(NULL AS STRING)"
    keys = ", ".join(f"__k{i}" for i in range(len(grain)))
    columns = [
        f"FARM_FINGERPRINT(TO_JSON_STRING(STRUCT({keys}, __rn))) AS __row",
        f"{key} AS item_key",
        f"'{held}' AS side",
        *(p.cube for p in dims),
        *(f"__g{i} AS {p.cube}" for i, p in enumerate(grain)),
        "__rn",
    ]
    # trunk-ignore(bandit/B608): identifiers are validated in config.py; values are bound literals
    select = f"SELECT {', '.join(columns)}\nFROM joined WHERE bucket = '{bucket}'"
    return ctes, select


def proof_query(ctes: str, select: str, body: str, literals: set[str]) -> str:
    """The proof inside the tool's own counting query.

    Only item keys, cause literals and counts come back: per item and cause,
    the rows, the rows the proof dropped (`missed`) or repeated (`doubled`),
    the rows whose cause is no string literal of the proof (`bad`), and the
    proof's rows with a `__row` `{unmatched}` lacks (`stray`).
    """
    allowed = ", ".join(pipeline._lit(v) for v in sorted(literals))
    proof = body.replace(PLACEHOLDER, "__u")
    return (
        f"{ctes},\n__u AS (\n{select}\n),\n__p AS (\n{proof}\n),\n"
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


# --- one proof's outcome -----------------------------------------------------------


@dataclass
class Outcome:
    """What one proof found for one item."""

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
        """Why the proof does not prove the item, with exact counts."""
        seen = self.counted + self.unexplained
        if seen != self.n_rows:
            return f"proof {name} saw {seen} of the item's {self.n_rows} rows"
        return f"proof {name} leaves {self.unexplained} rows unexplained"


def outcomes(
    rows: list[dict], proof: Proof, items: list[tuple[str, Group]], literals: set[str]
) -> dict[str, Outcome]:
    """Read the counting query's result per item.

    Raises:
        pipeline.Refusal: The proof dropped or repeated a row, gave a row a
            cause that is no string literal of it, returned a `__row`
            `{unmatched}` lacks, or named a cause literal the bucket map
            lacks. Each refusal names counts and literals, never a value.
    """
    out = {item_id: Outcome(g.n_rows, Counter()) for item_id, g in items}
    totals: Counter = Counter()
    unmapped: set[str] = set()
    for r in rows:
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
        "bad": "rows got a cause that is no string literal of the proof",
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


def run_proof(
    wh: Warehouse,
    cfg: ViewConfig,
    comparison: Comparison,
    sides: pipeline.RowSides,
    proof: Proof,
    items: list[tuple[str, Group]],
    build: Build,
) -> dict[str, Outcome]:
    """Check, pin, price and run a proof on the run's rows. Call inside `wh.budget`.

    The proof's own tables are read as of the build start, as the dashboard
    side is (`timetravel.as_of`); `{unmatched}` is already pinned.

    Raises:
        pipeline.Refusal: The proof fails a check (see `check_sql` and
            `outcomes`), cannot be read as of the moment, or BigQuery refuses
            it; only its job id and reason are kept.
        CostCapError: It would pass the run's or the day's cap.
    """
    literals = check_sql(proof.body, grain_names(comparison), identifying(comparison))
    body = pipeline._as_of(proof.body, build.start, wh).sql
    ctes, select = unmatched_sql(cfg, comparison, sides, proof.bucket, items)
    sql = proof_query(ctes, select, body, literals)
    try:
        usd = wh.estimate(sql)
        wh.refuse_past_caps(usd)
        print(f"Proof {proof.path.name}: ${usd:.2f} (dry run).")
        rows = wh.rows(sql, timeout_s=TIMEOUT_S)
    except GoogleAPIError as exc:
        raise pipeline.Refusal(
            f"{proof.path.name}: BigQuery refused it ({_failure(exc)})"
        ) from exc
    return outcomes(rows, proof, items, literals)


# --- re-sorting triage items -------------------------------------------------------


def _proof_lines(proof: Proof, outcome: Outcome, posted: bool) -> list[str]:
    ranked = outcome.counts.most_common()
    _, texts = shown_counts(outcome.n_rows, [n for _, n in ranked], posted)
    return [
        f"proof {proof.path.name}: {proof.causes[b][1]}: {t} rows"
        for (b, _), t in zip(ranked, texts, strict=True)
    ]


def _kept(lines: list[str]) -> list[str]:
    """An item's evidence without any earlier proof's lines."""
    return [line for line in lines if not line.startswith("proof ")]


def apply_outcomes(items: list[dict], proof: Proof, found: dict[str, Outcome]) -> None:
    """Move each fully explained item to `cause`; note the rest in place."""
    for item in items:
        outcome = found.get(item["id"])
        if outcome is None:
            continue
        evidence = _kept(item.get("evidence") or [])
        posted = _kept(item.get("evidence_posted") or item.get("evidence") or [])
        if outcome.explained:
            also = [line for line in evidence if line.startswith("also covers: ")]
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
                evidence=_proof_lines(proof, outcome, False) + also,
                evidence_posted=_proof_lines(proof, outcome, True) + also,
            )
            continue
        # A bucket's groups reach `cause` only through its proof.
        item.update(suggestion="investigate", cause=None, proof=None)
        item["evidence"] = [outcome.gap_line(proof.path.name), *evidence]
        item["evidence_posted"] = [
            f"proof {proof.path.name} does not explain every row",
            *posted,
        ]


def note(items: list[dict], ids: set[str], line: str, name: str) -> None:
    """Add why proof `name` did not run to each listed item's evidence.

    The posted copy is a fixed line: a refusal's text stays local.
    """
    for item in items:
        if item["id"] in ids:
            evidence = item.get("evidence") or []
            posted = item.get("evidence_posted") or evidence
            item["evidence"] = [line, *evidence]
            item["evidence_posted"] = [
                f"proof {name} not run; see the terminal",
                *posted,
            ]


def _bucket_items(run: RunResult, comparison: str, bucket: str):
    return [
        (item.id, g)
        for item, g in triage._entries(run)
        if isinstance(g, Group) and g.comparison_id == comparison and g.bucket == bucket
    ]


def _counts_rows(comparison: Comparison | None) -> bool:
    """A comparison whose rows carry no value column counts them: each row is
    1 toward its cell."""
    return bool(comparison and comparison.rows and not comparison.rows.values)


def _in_cut(g: Group, comparison: Comparison | None, cut: str) -> bool:
    """Whether a group's columns allow its rows under a cell's cut.

    A cut filter on a column the group does not split by allows any value;
    for a count measure the size check then catches rows outside the cut.
    """
    if comparison is None:
        return True
    try:
        chosen = {**comparison.defaults, **json.loads(cut or "{}")}
    except json.JSONDecodeError:
        return True
    for caption, value in chosen.items():
        pair = comparison.filters.get(caption)
        held = g.value_of(pair.cube) if pair else None
        if held is None:
            continue
        values = value if isinstance(value, list) else [value]
        if pipeline._key(held) not in {pipeline._key(v) for v in values}:
            return False
    return True


_SIGN = {"cube_only": 1, "dashboard_filtered": 1, "dashboard_only": -1}


def link_cells(
    run: RunResult,
    items: list[dict],
    comparison: str | None = None,
    cfg: ViewConfig | None = None,
) -> dict[str, tuple[int, int, float]]:
    """Move each cell set whose differing cells' rows all lie in proven groups.

    A cell's rows lie in the open groups of its comparison whose columns agree
    with the cell's dims and its cut. A cell no open group agrees with, or one
    a group outside `cause` agrees with, is not linked. For a comparison that
    counts its rows, the cell's difference (Cube minus dashboard) must also
    equal the linked groups' net rows (Cube-only and dashboard-filtered rows
    add, dashboard-only rows take away); otherwise the cell is not linked.

    Returns:
        Per cell-set item id: the differing cells not linked, all of them, and
        the summed gap between the cells' differences and their proven rows.
    """
    entries = triage._entries(run)
    by_id = {i["id"]: i for i in items}
    by_cmp = {c.id: c for c in (cfg.comparisons if cfg else [])}
    out = {}
    for item, _ in entries:
        if item.kind != "cells" or (comparison and item.comparison != comparison):
            continue
        spec = by_cmp.get(item.comparison)
        counts = _counts_rows(spec)
        groups = [
            (i.id, g)
            for i, g in entries
            if isinstance(g, Group) and g.comparison_id == item.comparison
        ]
        cells = [c for c in run.diff_cells if c["comparison"] == item.comparison]
        unlinked, used, gap = 0, {}, 0.0
        for cell in cells:
            match = [
                (gid, g)
                for gid, g in groups
                if _in_cut(g, spec, cell.get("cut", "{}"))
                and all(
                    g.value_of(col) is None
                    or pipeline._key(g.value_of(col)) == pipeline._key(value)
                    for col, value in cell["dims"]
                )
            ]
            proven = [gid for gid, _ in match if by_id[gid]["suggestion"] == "cause"]
            if not match or len(proven) < len(match):
                unlinked += 1
                continue
            if counts:
                net = sum(_SIGN.get(g.bucket, 0) * g.n_rows for _, g in match)
                differs = (cell.get("cube") or 0) - (cell.get("dashboard") or 0)
                if abs(differs - net) > 1e-9:
                    unlinked += 1
                    gap += abs(differs - net)
                    continue
            used |= dict.fromkeys(proven)
        out[item.id] = (unlinked, len(cells), gap)
        target = by_id[item.id]
        if cells and not unlinked:
            merged: dict[tuple, dict] = {}
            for gid in used:
                for c in by_id[gid]["cause"] or []:
                    k = (c["side"], c["step"], c["label"])
                    entry = merged.setdefault(k, {**c, "n_rows": 0})
                    entry["n_rows"] += c["n_rows"] or 0
            line = (
                f"every differing cell's rows lie in proven groups: {', '.join(used)}"
            )
            target.update(
                suggestion="cause",
                cause=list(merged.values()),
                proof={"kind": "cells", "groups": list(used)},
                evidence=[line],
                evidence_posted=[line],
            )
        else:
            if target.get("suggestion") == "cause":
                target.update(suggestion="investigate", cause=None, proof=None)
            if not cells:
                line = posted = "the run lists no differing cells to link; `run` again"
            else:
                line = (
                    f"{unlinked} of {len(cells)} differing cells have rows outside "
                    "proven groups"
                )
                posted = line
                if gap:
                    line += f"; their differences exceed the proven rows by {gap:g}"
                    posted += "; their differences exceed the proven rows"
            target["evidence"] = [line, *_unlinked(target.get("evidence"))]
            target["evidence_posted"] = [
                posted,
                *_unlinked(target.get("evidence_posted")),
            ]
    return out


def _unlinked(lines: list[str] | None) -> list[str]:
    """Evidence without an earlier link line."""
    return [
        e
        for e in lines or []
        if "differing cells have rows" not in e and "no differing cells" not in e
    ]


@dataclass
class Ran:
    """One stored proof's run: its outcomes per item, or why it did not run."""

    proof: Proof
    items: list[tuple[str, Group]]
    found: dict[str, Outcome] | None = None
    why: str = ""


def run_stored(
    cfg: ViewConfig,
    run: RunResult,
    directory: Path,
    *,
    wh: Warehouse,
    cube: Cube,
) -> list[Ran]:
    """Run every stored proof of the view on the run's rows. Call inside `wh.budget`.

    A proof that cannot run (a failed check, a cap, a BigQuery or Cube error,
    its SQL no longer the run's) keeps why and moves nothing; the rest still
    run. Each comparison's row SQL is rebuilt once.
    """
    by_id = {c.id: c for c in cfg.comparisons}
    schools: set[str] | None = None
    sides: dict[str, pipeline.RowSides] = {}
    out = []
    for path in sorted(directory.glob("*__*.sql")) if directory.is_dir() else []:
        try:
            proof = read_proof(path)
        except (OSError, pipeline.Refusal) as exc:
            print(f"Proof {path.name} skipped: {exc}")
            continue
        comparison = by_id.get(proof.comparison)
        bucket_items = _bucket_items(run, proof.comparison, proof.bucket)
        if comparison is None or not bucket_items:
            continue
        ran = Ran(proof, bucket_items)
        try:
            if schools is None:
                schools = network_schools(wh)
            if comparison.id not in sides:
                sides[comparison.id] = pipeline.row_sides(
                    cfg,
                    comparison,
                    wh=wh,
                    cube=cube,
                    build=run.moment,
                    schools=schools,
                    fingerprints=run.fingerprints.get(comparison.id, {}),
                )
            ran.found = run_proof(
                wh,
                cfg,
                comparison,
                sides[comparison.id],
                proof,
                bucket_items,
                run.moment,
            )
        except (
            pipeline.Refusal,
            CostCapError,
            ViewHistoryError,
            CubeError,
            CubeRefusal,
        ) as exc:
            ran.why = f"proof {path.name} not run: {exc}"
        except GoogleAPIError as exc:
            ran.why = f"proof {path.name} not run ({_failure(exc)})"
        if ran.why:
            print(ran.why)
        out.append(ran)
    return out


def explained(runs: list[Ran]) -> set[tuple]:
    """The `trace.item_key` of every group a proof fully explains."""
    return {
        trace.item_key(g)
        for r in runs
        for item_id, g in r.items
        if r.found and r.found[item_id].explained
    }


def apply_runs(
    run: RunResult, items: list[dict], runs: list[Ran], cfg: ViewConfig
) -> None:
    """Sort the items by the proofs' runs, then link cell sets."""
    for r in runs:
        if r.found is None:
            note(items, {i for i, _ in r.items}, r.why, r.proof.path.name)
        else:
            apply_outcomes(items, r.proof, r.found)
    link_cells(run, items, cfg=cfg)


# --- the command -------------------------------------------------------------------


def _load_triage(run: RunResult, run_json: Path) -> tuple[Path, dict]:
    found = run_json.parent / "triage.json"
    again = f"run `triage` for {run.moment.start:%Y-%m-%d %H:%M} UTC first"
    if not found.exists():
        raise pipeline.Refusal(f"{run.view}: no triage of the latest run; {again}")
    try:
        loaded = json.loads(found.read_text())
    except json.JSONDecodeError as exc:
        raise pipeline.Refusal(
            f"{run.view}: triage.json is unreadable; {again}"
        ) from exc
    if not isinstance(loaded, dict) or loaded.get("moment") != triage._moment(run):
        raise pipeline.Refusal(f"{run.view}: triage.json is of another moment; {again}")
    if set(triage.open_keys(run)) - set(loaded.get("open") or []):
        raise pipeline.Refusal(
            f"{run.view}: the latest run has open items its triage lacks; {again}"
        )
    return found, loaded


def _mark(run: RunResult, items: list[dict], cfg: ViewConfig) -> None:
    """Refresh the decision marks after a re-sort, as `triage` writes them."""
    for item in items:
        item.pop("decisions", None)
        item.pop("decided", None)
        for key in ("evidence", "evidence_posted"):
            item[key] = [
                line
                for line in item.get(key) or []
                if not line.startswith(("decision ", "decisions "))
            ]
    triage.mark_decided(run, items, cfg.decisions, note=True)


def _save_triage(path: Path, loaded: dict, items: list[dict]) -> None:
    loaded["items"] = sorted(
        items, key=lambda i: triage.SUGGESTIONS.index(i["suggestion"])
    )
    path.write_text(json.dumps(loaded, indent=1))


def _report(items: list[dict], wanted: set[str] | None) -> None:
    for item in items:
        if wanted and item["id"] not in wanted:
            continue
        print(f"- {item['id']}: {item['suggestion']}")
        for line in item.get("evidence") or []:
            print(f"    {line}")


def run_confirm(
    cfg: ViewConfig,
    view_file: Path,
    *,
    wh: Warehouse,
    cube: Cube,
    max_usd: float,
    cache_root: Path,
    comparison: str,
    bucket: str | None = None,
    sql: Path | None = None,
    causes: list[str] | None = None,
    items: list[str] | None = None,
    cells: bool = False,
) -> int:
    """Run a new or edited proof once, save it, and re-sort the triage.

    With `cells`, runs no query: confirms the comparison's cell set when every
    differing cell's rows lie in groups in `cause`.

    Args:
        cfg: The view's config.
        view_file: Its validation file; proofs are saved beside it.
        wh: The warehouse.
        cube: Cube, to rebuild the run's row SQL.
        max_usd: The cap for this command.
        cache_root: The local cache holding the run and its triage.
        comparison: The comparison the proof covers.
        bucket: `cube_only` or `dashboard_only`.
        sql: The proof's SQL; it may carry a `-- cause` block. Defaults to
            the stored proof, to re-run it after an edit.
        causes: `<bucket>=<side>:<plain words>` per bucket, added to (and
            replacing entries of) the SQL's own block.
        items: Triage item ids to print; every item of the bucket is proven
            either way.
        cells: Confirm the comparison's cell set instead.

    Returns:
        0.

    Raises:
        pipeline.Refusal: No triage of the latest run; an unknown comparison
            or bucket; a proof that fails a check; or, with `cells`, a
            differing cell whose rows are not all in proven groups.
        CostCapError: The proof would pass a cap.
    """
    run, run_json = pipeline.latest_run(cfg, cache_root)
    path, loaded = _load_triage(run, run_json)
    all_items = loaded.get("items", [])
    target = next((c for c in cfg.comparisons if c.id == comparison), None)
    if target is None:
        raise pipeline.Refusal(f"{cfg.view}: no comparison {comparison!r}")
    wanted = set(items or []) or None

    if cells:
        linked = link_cells(run, all_items, comparison, cfg)
        if not linked:
            raise pipeline.Refusal(f"{comparison}: no open cell set to confirm")
        for item_id, (unlinked, total, gap) in linked.items():
            if unlinked:
                over = (
                    f"; their differences exceed the proven rows by {gap:g}"
                    if gap
                    else ""
                )
                raise pipeline.Refusal(
                    f"{item_id}: {unlinked} of {total} differing cells have rows "
                    f"outside groups in `cause`{over}; prove those groups first"
                )
        _mark(run, all_items, cfg)
        _save_triage(path, loaded, all_items)
        _report(all_items, set(linked))
        print(f"Saved {path}")
        return 0

    if bucket not in PROVABLE:
        raise pipeline.Refusal(f"--bucket must be one of {', '.join(PROVABLE)}")
    stored = proof_path(proofs_dir(view_file, cfg.view), comparison, bucket)
    source = sql or stored
    if not source.is_file():
        raise pipeline.Refusal(f"{source}: no such proof; pass --sql <file>")
    block, body = split_block(source.read_text())
    for flag in causes or []:
        b, side, words = parse_cause_flag(flag)
        block[b] = (side, words)
    proof = Proof(stored, comparison, bucket, block, body)
    bucket_items = _bucket_items(run, comparison, bucket)
    if not bucket_items:
        raise pipeline.Refusal(f"{comparison} {bucket}: no open row group to prove")
    if wanted and (unknown := wanted - {i for i, _ in bucket_items}):
        raise pipeline.Refusal(
            f"--items: {len(unknown)} id(s) are no open item of {comparison} {bucket}"
        )

    with wh.budget(max_usd):
        sides = pipeline.row_sides(
            cfg,
            target,
            wh=wh,
            cube=cube,
            build=run.moment,
            schools=network_schools(wh),
            fingerprints=run.fingerprints.get(comparison, {}),
        )
        found = run_proof(wh, cfg, target, sides, proof, bucket_items, run.moment)

    stored.parent.mkdir(parents=True, exist_ok=True)
    stored.write_text(proof.text)
    apply_outcomes(all_items, proof, found)
    link_cells(run, all_items, comparison, cfg)
    _mark(run, all_items, cfg)
    _save_triage(path, loaded, all_items)
    moved = sum(1 for o in found.values() if o.explained)
    print(f"Saved {stored}: {moved} of {len(found)} items proven.")
    _report(all_items, wanted or set(found))
    print(f"Saved {path}")
    return 0
