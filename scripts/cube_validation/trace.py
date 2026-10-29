"""Trace each unmatched row of a run to the SQL step that drops it.

A Cube-only row is traced through the dashboard side's SQL, a dashboard-only
row through Cube's (`sqlsteps` finds the steps). At each level:

1. Each step is neutralized alone. A row one step brings back is attributed
   to it. A row several steps of one scope each bring back is attributed to
   them as one cause (`A / B`: either alone lets it through); across scopes
   it stays unattributed.
2. The rest are checked for presence: the level's SQL with every one of its
   own steps neutralized, its tables unchanged, with the row picks kept and
   then, for the rows still missing, dropped too. A row the first brings
   back is in the tables and dropped by several steps here; a pair of steps
   in one scope that alone brings it back is its cause (`A + B`), else it
   stays unattributed. A row only the second brings back is dropped by a
   row pick, here or above. Neither descends.
3. Only a row presence does not bring back is missing from a table this level
   reads. The trace then inlines that table's dbt compiled SQL, as of the
   moment, and repeats, at most `MAX_LEVELS` tables deep, into a table whose
   whole subtree with every step neutralized can bring the row back.

Every variant runs inside one query that rebuilds the unmatched rows the way
the run's reconcile did (`compare.trace_sql`), so no row leaves BigQuery; each
query returns group columns, a step id and a count.
"""

from __future__ import annotations

import itertools
import json
import time
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from google.api_core.exceptions import GoogleAPIError
from sqlglot.errors import SqlglotError

from . import compare, pipeline
from .bq import JOB_ID, CostCapError, Warehouse
from .compare import (
    DUPLICATE,
    MANY,
    NONE,
    PRESENT,
    STAND_IN,
    UNREPRODUCED,
    Group,
    many_ids,
)
from .config import Comparison, ViewConfig
from .cube_client import Cube, network_schools
from .moment import Build, changed_between
from .report import SUPPRESSED, RunResult, suppress
from .sqlsteps import Query, Step, TableRef, carry
from .timetravel import PROJECT, repin

MAX_LEVELS = 3
# BigQuery refuses a query longer than 1,024K characters.
MAX_QUERY_CHARS = 900_000
# Each pair variant copies the frame's whole SQL; BigQuery's planner refuses
# many copies of a long side SQL (`resourcesExceeded`) before reading a byte.
# This holds 4 copies of a 56K-character side SQL.
MAX_PAIR_QUERY_CHARS = 240_000
# A relaxed variant can multiply rows; BigQuery stops a query past this.
TIMEOUT_S = 1800
# Pairs of steps searched in one level's frame; past it the rows stay
# unattributed rather than buying a search that size.
MAX_PAIRS = 400
TRACE_MAX_MINUTES = 120
MANIFEST = (
    Path(__file__).resolve().parents[2] / "src/dbt/kipptaf/target/prod/manifest.json"
)
TRACED = ("cube_only", "dashboard_only")
_MATERIALIZED = ("table", "incremental")


def compile_command(models: Iterable[str], ancestors: bool = False) -> str:
    """The command, run from the repository root, that writes compiled SQL.

    A compile writes compiled SQL only for the models it selects and drops
    it for every other model, so the command always names every model the
    trace needs; `ancestors` selects each model with all its parents
    (`+<model>`), for when no manifest says which those are.
    """
    names = sorted(models)
    select = " ".join(f"+{n}" for n in names) if ancestors else " ".join(names)
    return (
        "uv run dbt deps --project-dir src/dbt/kipptaf && "
        "uv run dbt compile --project-dir src/dbt/kipptaf "
        "--profiles-dir src/dbt/kipptaf --target prod --target-path target/prod "
        f"--select {select}"
    )


class Stopped(RuntimeError):
    """The trace stopped before it finished: a cap or its time limit.

    `found` holds the traces made so far; they are kept, not thrown away.
    """

    def __init__(self, reason: str, found: dict | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.found = found or {}


class TooComplex(Stopped):
    """BigQuery would not plan a query: too many or too long variants.

    A pair search catches it and skips only its rows; anywhere else it stops
    the bucket like any failed dry run.
    """


def _too_complex(exc: GoogleAPIError) -> bool:
    errors = getattr(exc, "errors", None) or [{}]
    return errors[0].get("reason") == "resourcesExceeded" or (
        "too complex" in str(exc).lower()
    )


@dataclass
class ItemTrace:
    """What the trace found for one row group.

    `steps` counts the rows each cause recovers: one step, steps of one scope
    each recovering it alone (`a/b`), or a pair of one scope recovering it
    together (`a+b`). The rest are unattributed: `many` recovered by steps of
    several scopes, `pairs_many` by several pairs, `needs_more` present but
    recovered by no single step or pair, `skipped` present but with more
    pairs than `MAX_PAIRS` to search, `picked` present once every step is
    neutralized but dropped by a row pick here or above, `stand_in` recovered
    only where a row pick after the step held another row that could stand
    in, `unreproduced`
    already returned by
    the unrelaxed SQL, `duplicates` a grain the other side holds twice,
    `unknown` behind a query that failed or a stop, and `none` missing below
    the deepest level, under `below`. `recovered` counts every row each
    step recovers, ambiguous ones included.
    """

    side: str
    n_rows: int
    steps: Counter = field(default_factory=Counter)
    labels: dict[str, str] = field(default_factory=dict)
    many: int = 0
    many_labels: tuple[str, ...] = ()
    pairs_many: int = 0
    needs_more: Counter = field(default_factory=Counter)
    skipped: Counter = field(default_factory=Counter)
    picked: Counter = field(default_factory=Counter)
    stand_in: Counter = field(default_factory=Counter)
    unreproduced: Counter = field(default_factory=Counter)
    duplicates: int = 0
    unknown: int = 0
    none: int = 0
    below: tuple[str, ...] = ()
    recovered: Counter = field(default_factory=Counter)
    failed: tuple[str, ...] = ()
    stopped: str = ""

    @property
    def unattributed(self) -> int:
        return self.n_rows - sum(self.steps.values())

    def _reasons(self) -> list[tuple[str, int]]:
        out = []
        if self.many:
            out.append(
                (
                    "recovered by steps in 2 or more scopes "
                    f"({', '.join(self.many_labels)})",
                    self.many,
                )
            )
        if self.pairs_many:
            out.append(("recovered by more than one pair of steps", self.pairs_many))
        out += [
            (f"needs 3 or more steps, or steps in 2 or more scopes, in {at}", n)
            for at, n in sorted(self.needs_more.items())
        ]
        out += [
            (f"pair search skipped: {why}", n)
            for why, n in sorted(self.skipped.items())
        ]
        out += [
            (f"a row pick drops it; the row is in the tables {at} reads", n)
            for at, n in sorted(self.picked.items())
        ]
        out += [
            (f"a row pick follows {at}; another row could stand in", n)
            for at, n in sorted(self.stand_in.items())
        ]
        out += [
            (f"already returned by the {t} SQL with no step neutralized", n)
            for t, n in sorted(self.unreproduced.items())
        ]
        if self.duplicates:
            out.append(("duplicate grain on the other side", self.duplicates))
        if self.unknown:
            out.append(("not traced: a trace query failed or stopped", self.unknown))
        if self.none:
            where = f" (below {', '.join(self.below)})" if self.below else ""
            out.append((f"recovered by no step{where}", self.none))
        return [(t, n) for t, n in out if n]

    @property
    def consistent(self) -> bool:
        """Every row is either attributed or has a reason it is not."""
        return sum(self.steps.values()) + sum(n for _, n in self._reasons()) == (
            self.n_rows
        )

    @property
    def proven(self) -> bool:
        return (
            self.n_rows > 0
            and self.unattributed == 0
            and self.consistent
            and not self.stopped
        )

    def cause(self) -> list[dict]:
        """Each cause with its rows, as triage.json records a proven cause."""
        return [
            {"side": self.side, "step": s, "label": self.labels[s], "n_rows": n}
            for s, n in self.steps.most_common()
        ]

    def shown_total(self) -> str:
        """The group's row count as the batch may print it next to the evidence."""
        parts = [n for _, n in self.steps.most_common()]
        if self.unattributed:
            parts.append(self.unattributed)
        return suppress(self.n_rows, parts)[0]

    def evidence(self) -> tuple[str, ...]:
        """Lines for the batch, with small counts and what reveals them masked."""
        causes = self.steps.most_common()
        parts = [n for _, n in causes]
        if self.unattributed:
            parts.append(self.unattributed)
        _, texts = suppress(self.n_rows, parts)
        lines = [
            f"{self.labels[s]}: {text} rows"
            for (s, _), text in zip(causes, texts, strict=False)
        ]
        if not self.consistent:
            lines.append("trace counts do not add up; trace it by hand")
        if self.unattributed:
            reasons = self._reasons()
            total, why = suppress(self.unattributed, [n for _, n in reasons])
            shown = texts[-1] if len(texts) > len(causes) else total
            if shown in ("<10", SUPPRESSED):
                # A hidden count hides its whole breakdown, or the breakdown
                # adds back up to it.
                total = shown
                why = ["<10" if n < 10 else SUPPRESSED for _, n in reasons]
            lines.append(
                f"{total} rows unattributed: "
                + "; ".join(f"{t} {r}" for (r, _), t in zip(reasons, why, strict=True))
            )
            lines += [f"a trace query failed ({f})" for f in self.failed]
            if self.stopped:
                lines.append(f"trace stopped: {self.stopped}")
        return tuple(lines)

    def leads(self) -> tuple[str, ...]:
        """`evidence`, each cause worded as a lead to test, never as a cause.

        A step whose relaxing brings rows back is where to look first; the
        session proves the cause (`triage confirm`).
        """
        causes = self.steps.most_common()
        parts = [n for _, n in causes]
        if self.unattributed:
            parts.append(self.unattributed)
        total, texts = suppress(self.n_rows, parts)
        lines = [
            f"lead: relaxing {self.labels[s]} brings back {text} of {total} rows"
            for (s, _), text in zip(causes, texts, strict=False)
        ]
        return tuple(lines) + self.evidence()[len(causes) :]


def item_key(g: Group) -> tuple:
    return (g.comparison_id, g.bucket, g.dims)


@dataclass
class TraceResult:
    """Each traced group's trace, and why the trace stopped early, if it did.

    `stops` holds each stopped bucket's own reason, by (comparison id,
    bucket); a stop in one bucket never stops another. `stopped` is set only
    when the trace stopped before any bucket's items were traced.
    """

    items: dict[tuple, ItemTrace]
    stopped: str = ""
    stops: dict[tuple[str, str], str] = field(default_factory=dict)


class Manifest:
    """The dbt manifest's materialized models, by `dataset.table`."""

    def __init__(self, path: Path) -> None:
        self.path = path
        nodes = json.loads(path.read_text())["nodes"]
        self._nodes = {k: v for k, v in nodes.items() if k.startswith("model.")}
        self._by_relation = {
            (v.get("schema"), v.get("alias") or v.get("name")): v
            for v in self._nodes.values()
            if v.get("database") in (PROJECT, None)
        }

    @classmethod
    def load(cls, path: Path, roots: Iterable[TableRef]) -> Manifest:
        """Read the manifest, refusing when there is none.

        Raises:
            pipeline.Refusal: No manifest at `path`; the message prints the
                command that writes one with every model the trace may need.
        """
        if not path.is_file():
            raise pipeline.Refusal(
                f"no dbt manifest at {path}. From the repository root, run: "
                + compile_command({t.name for t in roots}, ancestors=True)
            )
        return cls(path)

    def model(self, dataset: str, name: str) -> dict | None:
        """The materialized model behind a table, or None (a source, a view)."""
        node = self._by_relation.get((dataset, name))
        if node is None or node["config"].get("materialized") not in _MATERIALIZED:
            return None
        return node

    def parents(self, node: dict) -> list[dict]:
        """The materialized models `node` reads, through any views between."""
        out, todo, seen = [], list(node["depends_on"]["nodes"]), set()
        while todo:
            key = todo.pop()
            if key in seen or key not in self._nodes:
                continue
            seen.add(key)
            parent = self._nodes[key]
            if parent["config"].get("materialized") in _MATERIALIZED:
                out.append(parent)
            else:
                todo += parent["depends_on"]["nodes"]
        return out

    def require_compiled(self, tables: Iterable[TableRef], levels: int) -> None:
        """Refuse unless every model a trace may descend into has compiled SQL.

        Raises:
            pipeline.Refusal: Some have none; the message prints the command
                that compiles every model the trace needs, so following it
                never strips another's.
        """
        frontier = [m for t in tables if (m := self.model(t.dataset, t.name))]
        wanted: dict[str, dict] = {}
        for _ in range(levels):
            nxt = []
            for node in frontier:
                if node["name"] not in wanted:
                    wanted[node["name"]] = node
                    nxt += self.parents(node)
            frontier = nxt
        missing = sorted(n for n, v in wanted.items() if not v.get("compiled_code"))
        if missing:
            raise pipeline.Refusal(
                f"{self.path} has no compiled SQL for {', '.join(missing)}; the "
                "trace descends into them. From the repository root, run: "
                + compile_command(wanted)
            )


@dataclass
class _Frame:
    """One level of a side's SQL: the side itself, or a table inlined into it."""

    query: Query
    table: tuple[str, str] | None = None
    parent: _Frame | None = None
    level: int = 0

    def full(self, sql: str) -> str:
        """The side's whole rows SQL with this frame's SQL replaced by `sql`."""
        frame, text = self, sql
        while frame.parent is not None and frame.table is not None:
            text = frame.parent.query.inline({frame.table: text})
            frame = frame.parent
        return text

    def full_relaxed(self, sql: str, picks: bool = True) -> str:
        """As `full`, with every step of every frame above neutralized too.

        With `picks`, their row picks are dropped as well.
        """
        frame, text = self, sql
        while frame.parent is not None and frame.table is not None:
            text = frame.parent.query.relaxed_all({frame.table: text}, picks=picks)
            frame = frame.parent
        return text

    def full_marked(self, sql: str, marks: list[str]) -> tuple[str, list[str] | None]:
        """As `full`, with each row pick above that reads this frame marked too.

        Returns:
            The SQL and every mark, `marks` first; None marks when a pick
            above cannot be marked in full.
        """
        frame, text = self, sql
        while frame.parent is not None and frame.table is not None:
            text, more = frame.parent.query.inline_marked(
                {frame.table: text}, len(marks)
            )
            if more is None:
                return text, None
            marks = marks + more
            frame = frame.parent
        return text, marks

    @property
    def name(self) -> str:
        return self.table[1] if self.table else ""


@dataclass
class _Side:
    """What one bucket's trace needs from the run."""

    cfg: ViewConfig
    comparison: Comparison
    sides: pipeline.RowSides
    build: Build
    bucket: str

    @property
    def side(self) -> str:
        return "dashboard" if self.bucket == "cube_only" else "cube"

    def grain(self) -> list[str]:
        grain = self.comparison.rows.grain if self.comparison.rows else []
        if self.side == "dashboard":
            return [p.dashboard for p in grain]
        return [f"{self.cfg.view}__{p.cube}" for p in grain]

    def root_sql(self) -> str:
        if self.side == "dashboard":
            return self.sides.dashboard.sql
        return self.sides.cube_rows_sql

    def rows(self, sql: str) -> str:
        """A variant as rows under this side's reconcile names."""
        if self.side == "dashboard":
            return sql
        return pipeline.wrap_cube(
            sql,
            self.cfg.view,
            self.sides.columns,
            pipeline._date_cubes(self.cfg),
            None,
        )

    def query(self, variants, exclude, combine: bool, include=()) -> str:
        if self.comparison.rows is None:
            raise pipeline.Refusal(f"comparison {self.comparison.id!r} has no rows")
        return compare.trace_sql(
            pipeline.wrap_cube(
                self.sides.cube_rows_sql,
                self.cfg.view,
                self.sides.columns,
                pipeline._date_cubes(self.cfg),
                None,
            ),
            self.sides.dashboard.sql,
            self.comparison.rows,
            pipeline.group_dims(self.comparison),
            pipeline._filter_flags(self.comparison),
            bucket=self.bucket,
            side=self.side,
            variants=variants,
            exclude=exclude,
            include=include,
            combine=combine,
        )


def _failure(exc: GoogleAPIError) -> str:
    """A BigQuery error as its job and reason: its message can quote values."""
    errors = getattr(exc, "errors", None) or [{}]
    reason = errors[0].get("reason") or type(exc).__name__
    return f"job {getattr(exc, JOB_ID, '') or '?'}, {reason}"


class _Meter:
    """The whole trace's dry-run running total and its time limit."""

    def __init__(self, deadline: float | None) -> None:
        self.total = 0.0
        self.deadline = deadline

    def check(self) -> None:
        if self.deadline is not None and time.monotonic() > self.deadline:
            raise Stopped("the trace passed its time limit (--trace-max-minutes)")


class _Runner:
    """Prices and runs one bucket's queries, reading each result by item."""

    def __init__(self, wh: Warehouse, side: _Side, meter: _Meter) -> None:
        self.wh = wh
        self.side = side
        self.meter = meter
        self.label = f"{side.comparison.id} {side.bucket}"
        self.failures: list[str] = []

    def _run(self, queries: list[str], what: str) -> list[dict] | None:
        """Run `queries`, or return None when one fails at run time."""
        self.meter.check()
        try:
            usd = sum(self.wh.estimate(q) for q in queries)
        except GoogleAPIError as exc:
            # After paid queries, a dry run that fails stops the bucket like
            # a cap, keeping what it found.
            why = Stopped if not _too_complex(exc) else TooComplex
            raise why(f"{what}: the dry run failed ({_failure(exc)})") from exc
        self.wh.refuse_past_caps(usd)
        self.meter.total += usd
        print(
            f"Trace {self.label}, {what}: {len(queries)} "
            f"quer{'y' if len(queries) == 1 else 'ies'}, ${usd:.2f} (dry run); "
            f"${self.meter.total:.2f} so far."
        )
        out = []
        for q in queries:
            self.meter.check()
            try:
                out += self.wh.rows(q, timeout_s=TIMEOUT_S)
            except GoogleAPIError as exc:
                # A neutralized step can fail only at run time (a cast, a
                # date overflow). Its message can quote a row's values, so
                # only the job and the reason are kept.
                note = f"{what}: {_failure(exc)}"
                print(f"Trace query failed, {note}")
                self.failures.append(note)
                return None
        return out

    def _key(self, row: dict) -> tuple:
        dims = tuple(
            (p.cube, "" if row[p.cube] is None else str(row[p.cube]))
            for p in pipeline.group_dims(self.side.comparison)
        )
        return (self.side.comparison.id, row["bucket"], dims)

    def plan(
        self,
        variants: list[tuple[str, str]],
        exclude: list[str],
        include: list[str],
        max_chars: int | None = None,
    ) -> tuple[list[str], bool]:
        """The queries `level` runs first: 1 combined, or per-step batches.

        Each query holds at most `max_chars` characters (`MAX_QUERY_CHARS` by
        default), except a batch of 1 variant longer than that alone.

        Returns:
            The queries, and whether they are the 1 combined query.
        """
        max_chars = max_chars or MAX_QUERY_CHARS
        whole = self.side.query(variants, exclude, True, include)
        if len(whole) <= max_chars:
            return [whole], True
        base = len(self.side.query([], exclude, False, include))
        # Each variant also costs its CTE and its line in `hits`.
        first = variants[0] if variants else ("", "")
        extra = len(self.side.query([first], exclude, False, include)) - base
        extra -= len(first[1])
        batches: list[list[tuple[str, str]]] = [[]]
        size = base
        for v in variants:
            if batches[-1] and size + len(v[1]) + extra > max_chars:
                batches.append([])
                size = base
            batches[-1].append(v)
            size += len(v[1]) + extra + len(v[0])
        return [self.side.query(b, exclude, False, include) for b in batches], False

    def level(
        self,
        variants: list[tuple[str, str]],
        exclude: list[str],
        what: str,
        include: list[str] | None = None,
        pairs: bool = False,
    ) -> tuple[dict[tuple, Counter], dict[tuple, Counter]] | None:
        """Each item's rows by the one step that recovers them, and each step's hits.

        With `pairs`, each query holds at most `MAX_PAIR_QUERY_CHARS`.

        Returns:
            Per item, rows by step id (a `MANY` id lists the steps, or
            `NONE`, `DUPLICATE`, an `UNREPRODUCED` or `PRESENT` id); and per
            item, every row each variant recovers. None when a query failed.

        Raises:
            TooComplex: With `pairs`, the shared-steps query is too long, or
                BigQuery would not plan a query.
        """
        include = include or []
        max_chars = (
            min(MAX_QUERY_CHARS, MAX_PAIR_QUERY_CHARS) if pairs else MAX_QUERY_CHARS
        )
        queries, whole = self.plan(variants, exclude, include, max_chars)
        if whole:
            rows = self._run(queries, what)
            return None if rows is None else self._read(rows)

        # Too long for one query: count each step's rows apart, then count
        # once more over only the steps that share an item.
        rows = self._run(queries, f"{what}, by step")
        if rows is None:
            return None
        hits: dict[tuple, Counter] = {}
        in_play: dict[tuple, int] = {}
        dupes: dict[tuple, int] = {}
        for r in rows:
            key = self._key(r)
            n = int(r["n_rows"])
            if r["step_id"] == NONE:
                in_play[key] = n
            elif r["step_id"] == DUPLICATE:
                dupes[key] = n
            else:
                hits.setdefault(key, Counter())[r["step_id"]] += n
        found: dict[tuple, Counter] = {
            k: Counter({DUPLICATE: n}) for k, n in dupes.items()
        }
        shared: set[str] = set()
        for key, total in in_play.items():
            h = hits.get(key, Counter())
            if len(h) <= 1:
                found.setdefault(key, Counter()).update(h)
                found[key][NONE] += total - sum(h.values())
            else:
                shared |= set(h)
        if shared:
            subset = [v for v in variants if v[0] in shared]
            again = self.side.query(subset, exclude, True, include)
            combined = None
            if pairs and len(again) > max_chars:
                raise TooComplex(f"{what}, shared steps: the query is too long")
            if len(again) <= max_chars:
                rows = self._run([again], f"{what}, shared steps")
                combined = None if rows is None else self._read(rows)[0]
            if combined is None:
                return None
            for key in in_play:
                if NONE not in found.get(key, {}) and key in combined:
                    counts = Counter(combined[key])
                    counts.pop(DUPLICATE, None)
                    found.setdefault(key, Counter()).update(counts)
        return found, hits

    def _read(
        self, rows: list[dict]
    ) -> tuple[dict[tuple, Counter], dict[tuple, Counter]]:
        found: dict[tuple, Counter] = {}
        hits: dict[tuple, Counter] = {}
        for r in rows:
            key = self._key(r)
            step = r["step_id"]
            if step.startswith("+"):
                hits.setdefault(key, Counter())[step[1:]] += int(r["n_rows"])
            else:
                found.setdefault(key, Counter())[step] += int(r["n_rows"])
        return found, hits


def _pairs(steps: list[Step]) -> list[tuple[Step, Step]]:
    """Every pair of steps that share a scope."""
    by_scope: dict[str, list[Step]] = {}
    for s in steps:
        by_scope.setdefault(s.scope, []).append(s)
    return [p for group in by_scope.values() for p in itertools.combinations(group, 2)]


class _Bucket:
    """One comparison bucket's trace, level by level."""

    def __init__(
        self,
        side: _Side,
        groups: list[Group],
        *,
        wh: Warehouse,
        manifest: Manifest | None,
        levels: int,
        end_tables: set[str],
        moved: dict[str, bool],
        meter: _Meter,
    ) -> None:
        self.side = side
        self.out = {item_key(g): ItemTrace(side.side, g.n_rows) for g in groups}
        self.root = _Frame(
            Query(side.root_sql(), frozenset(side.grain()), side.grain()[0])
        )
        self.wh = wh
        self.manifest = manifest
        self.levels = levels
        self.end_tables = end_tables
        self.moved = moved
        self.runner = _Runner(wh, side, meter)
        self.kids: dict[int, list[_Frame]] = {}
        self.blocked: set[str] = set()
        self.steps: dict[str, Step] = {}

    # --- what a level runs ----------------------------------------------------

    def variants(self, frames: list[_Frame]) -> list[tuple[str, str]]:
        """Each frame's unrelaxed SQL, then each of its steps neutralized alone."""
        side = self.side
        out = []
        for frame in frames:
            # A row the unrelaxed SQL returns is no step's to explain: a
            # table's build differs from its SQL, or the regeneration changed
            # what the SQL means.
            out.append(
                (
                    f"{UNREPRODUCED}{frame.name or side.side}",
                    side.rows(frame.full(frame.query.sql())),
                )
            )
            for step in frame.query.steps(side.side, frame.name):
                self.steps[step.id] = step
                out += self._guarded(frame, [step], step.id)
        return out

    def _guarded(self, frame: _Frame, steps: list[Step], step_id: str):
        """The variants for `steps` neutralized together, split at any row pick.

        Where a row pick follows the steps, in this frame or any above, a row
        counts for them only when its pick held 1 candidate; the rest come
        back under a `STAND_IN` id. Where a pick cannot be marked, or its
        count cannot be carried to the output, every row does.
        """
        sql, marks = frame.query.relaxed_marked(steps)
        full, marks = (sql, None) if marks is None else frame.full_marked(sql, marks)
        if marks is None:
            return self._stand_in(frame, steps, step_id)
        if not marks:
            return [(step_id, self.side.rows(full))]
        split = carry(full, marks)
        if split is None:
            return self._stand_in(frame, steps, step_id)
        one, several = split
        return [
            (step_id, self.side.rows(one)),
            (f"{STAND_IN}{step_id}", self.side.rows(several)),
        ]

    def _stand_in(self, frame: _Frame, steps: list[Step], step_id: str):
        """Every row of the variant as a stand-in.

        The guard cannot see through a pick that follows the steps. The SQL
        is the plain relaxed one, so no mark reaches the output.
        """
        full = frame.full(frame.query.relaxed_many(steps))
        return [(f"{STAND_IN}{step_id}", self.side.rows(full))]

    def first_queries(self) -> list[str]:
        """The level-0 queries, split as they will run, to price up front."""
        return self.runner.plan(self.variants([self.root]), [], [])[0]

    # --- descent --------------------------------------------------------------

    def children(self, frame: _Frame) -> list[_Frame]:
        """The materialized tables `frame` reads, each as the next frame down."""
        if id(frame) in self.kids:
            return self.kids[id(frame)]
        side, found = self.side, []
        for ref in frame.query.tables():
            node = self.manifest.model(ref.dataset, ref.name) if self.manifest else None
            if node is None or not node.get("compiled_code"):
                continue
            try:
                at = pipeline._as_of(node["compiled_code"], side.build.start, self.wh)
                sql = _one_moment(at, self.end_tables, self.moved, side.build, self.wh)
                child = _Frame(
                    Query(sql, ref.wanted),
                    (ref.dataset, ref.name),
                    frame,
                    frame.level + 1,
                )
                # Free, and it must run read in place: compiled SQL from
                # another checkout can name a column the table lacks, and a
                # WITH RECURSIVE runs only at the top of a query.
                self.wh.estimate(side.rows(child.full(child.query.sql())))
            except (pipeline.Refusal, SqlglotError) as exc:
                print(f"Trace cannot descend into {ref.name}: {type(exc).__name__}")
                self.blocked.add(ref.name)
                continue
            except GoogleAPIError as exc:
                errors = getattr(exc, "errors", None) or [{}]
                reason = errors[0].get("reason") or type(exc).__name__
                print(f"Trace cannot descend into {ref.name}: {reason}")
                self.blocked.add(ref.name)
                continue
            found.append(child)
        self.kids[id(frame)] = found
        return found

    def subtree(self, frame: _Frame) -> str:
        """`frame` with every step neutralized, down to the deepest level."""
        below = self.children(frame) if frame.level < self.levels else []
        return frame.query.relaxed_all(
            {k.table: self.subtree(k) for k in below if k.table}
        )

    # --- the trace ------------------------------------------------------------

    def _label(self, ids: list[str], joiner: str) -> str:
        return joiner.join(self.steps[i].label for i in ids)

    def _cause_label(self, step_id: str) -> str:
        """A step's or a pair's (`a+b`) label."""
        return self._label(step_id.split("+"), " + ")

    def _where(self, frame: _Frame) -> str:
        """A frame as the reasons name it: its table, or the side's own SQL."""
        return frame.name or f"the {self.side.side} SQL"

    def _fail(self, in_play: dict[tuple, int]) -> dict[tuple, int]:
        for key, n in in_play.items():
            self.out[key].unknown += n
        return {}

    def run(self) -> dict[tuple, ItemTrace]:
        try:
            self._run()
        except (Stopped, CostCapError) as exc:
            reason = exc.reason if isinstance(exc, Stopped) else str(exc)
            raise Stopped(reason, self.stop(reason)) from exc
        self._finish()
        return self.out

    def stop(self, reason: str) -> dict[tuple, ItemTrace]:
        """Mark every row not yet accounted for as stopped by `reason`."""
        for item in self.out.values():
            left = (
                item.n_rows
                - sum(item.steps.values())
                - sum(n for _, n in item._reasons())
            )
            if left > 0:
                item.unknown += left
                item.stopped = reason
        self._finish()
        return self.out

    def _finish(self) -> None:
        for item in self.out.values():
            if item.none:
                item.below = tuple(sorted(self.blocked))
            if item.unattributed:
                item.failed = tuple(self.runner.failures)

    def _run(self) -> None:
        side, out = self.side, self.out
        in_play = {key: item.n_rows for key, item in out.items()}
        frames = [self.root]
        exclude: list[str] = []
        for level in range(self.levels + 1):
            depth = "the side's own SQL" if level == 0 else f"tables {level} deep"
            variants = self.variants(frames)
            got = self.runner.level(variants, exclude, depth)
            if got is None:
                return self._end(self._fail(in_play))
            found, hits = got
            for key, counts in hits.items():
                if key in out:
                    out[key].recovered.update(
                        {s: n for s, n in counts.items() if s in self.steps}
                    )
            absent: dict[tuple, int] = {}
            for key, counts in found.items():
                if key not in out:
                    continue
                item = out[key]
                for step_id, n in counts.items():
                    if step_id == NONE:
                        absent[key] = n
                    elif step_id == DUPLICATE:
                        item.duplicates += n if level == 0 else 0
                    elif step_id.startswith(UNREPRODUCED):
                        item.unreproduced[step_id[1:]] += n
                    elif step_id.startswith(STAND_IN):
                        item.stand_in[self._cause_label(step_id[1:])] += n
                    elif step_id.startswith(MANY):
                        ids = many_ids(step_id)
                        if len({self.steps[i].scope for i in ids}) == 1:
                            cause = "/".join(ids)
                            item.steps[cause] += n
                            item.labels[cause] = self._label(ids, " / ")
                        else:
                            item.many += n
                            item.many_labels = tuple(
                                dict.fromkeys(
                                    item.many_labels
                                    + tuple(self.steps[i].label for i in ids)
                                )
                            )
                    else:
                        item.steps[step_id] += n
                        item.labels[step_id] = self.steps[step_id].label
            recovered = {s for key in out for s in hits.get(key, {})}
            exclude = exclude + [
                sql for step_id, sql in variants if step_id in recovered
            ]

            # Presence: a row its level's SQL brings back with every own step
            # neutralized is in the tables, dropped by several steps here.
            in_play = {k: n for k, n in absent.items() if n}
            if not in_play:
                return self._end({})
            # Every step of this frame and of every frame above it is
            # neutralized, the row picks kept, the tables unchanged: a row
            # this brings back is in the tables and dropped by several steps.
            gates = [
                (
                    f"{PRESENT}{i}",
                    side.rows(f.full_relaxed(f.query.relaxed_all(picks=False), False)),
                )
                for i, f in enumerate(frames)
            ]
            got = self.runner.level(gates, exclude, f"{depth}, presence")
            if got is None:
                return self._end(self._fail(in_play))
            found, _ = got
            missing: dict[tuple, int] = {}
            present: dict[int, dict[tuple, int]] = {}
            for key, counts in found.items():
                if key not in out:
                    continue
                for step_id, n in counts.items():
                    if step_id == NONE:
                        missing[key] = n
                    elif step_id.startswith(PRESENT):
                        present.setdefault(int(step_id[1:]), {})[key] = n
            for i, rows in present.items():
                self._search_pairs(frames[i], gates[i][1], rows, exclude, depth)
            exclude = exclude + [sql for _, sql in gates]

            # Then with the row picks dropped too: a row this brings back is
            # in the tables and dropped by a row pick, here or above.
            in_play = {k: n for k, n in missing.items() if n}
            if not in_play:
                return self._end({})
            picked = [
                (f"{PRESENT}{i}", side.rows(f.full_relaxed(f.query.relaxed_all())))
                for i, f in enumerate(frames)
            ]
            got = self.runner.level(picked, exclude, f"{depth}, row picks")
            if got is None:
                return self._end(self._fail(in_play))
            found, _ = got
            missing = {}
            for key, counts in found.items():
                if key not in out:
                    continue
                for step_id, n in counts.items():
                    if step_id == NONE:
                        missing[key] = n
                    elif step_id.startswith(PRESENT):
                        out[key].picked[self._where(frames[int(step_id[1:])])] += n
            exclude = exclude + [sql for _, sql in picked]

            in_play = {k: n for k, n in missing.items() if n}
            if not in_play or self.manifest is None:
                return self._end(in_play)
            if level == self.levels:
                self.blocked |= {
                    ref.name
                    for f in frames
                    for ref in f.query.tables()
                    if self.manifest.model(ref.dataset, ref.name)
                }
                return self._end(in_play)
            frames = self._descend(frames, exclude)
            if not frames:
                return self._end(in_play)
        return None

    def _search_pairs(
        self,
        frame: _Frame,
        gate: str,
        present: dict[tuple, int],
        exclude: list[str],
        depth: str,
    ) -> None:
        """Attribute rows present at `frame` to the one same-scope pair recovering them."""
        where = self._where(frame)
        steps = frame.query.steps(self.side.side, frame.name)
        pairs = _pairs(steps)
        if len(pairs) > MAX_PAIRS:
            for key, n in present.items():
                self.out[key].skipped[f"{len(pairs)} pairs in {where}"] += n
            return
        if not pairs:
            for key, n in present.items():
                self.out[key].needs_more[where] += n
            return
        variants = [
            v for a, b in pairs for v in self._guarded(frame, [a, b], f"{a.id}+{b.id}")
        ]
        try:
            got = self.runner.level(
                variants, exclude, f"{depth}, step pairs", [gate], pairs=True
            )
        except TooComplex as exc:
            # The pair search is a lead; one BigQuery will not plan costs
            # only its own rows, never the rest of the trace.
            print(f"Trace {self.runner.label}: pair search skipped, {exc.reason}")
            for key, n in present.items():
                self.out[key].skipped["query too complex"] += n
            return
        if got is None:
            self._fail(present)
            return
        found, _ = got
        for key, counts in found.items():
            if key not in present:
                continue
            item = self.out[key]
            for step_id, n in counts.items():
                if step_id == NONE:
                    item.needs_more[where] += n
                elif step_id.startswith(MANY):
                    item.pairs_many += n
                elif step_id.startswith(STAND_IN):
                    item.stand_in[self._cause_label(step_id[1:])] += n
                elif step_id != DUPLICATE:
                    a, b = step_id.split("+", 1)
                    item.steps[step_id] += n
                    item.labels[step_id] = self._label([a, b], " + ")

    def _end(self, in_play: dict[tuple, int]) -> None:
        for key, n in in_play.items():
            self.out[key].none += n

    def _descend(self, frames: list[_Frame], exclude: list[str]) -> list[_Frame]:
        """The tables a level down whose neutralized subtree brings back a row."""
        candidates = [k for f in frames for k in self.children(f)]
        # One query per table, so one whose relaxed build runs away (every
        # filter off can multiply rows) costs only itself.
        nxt = []
        for c in candidates:
            screen = self.side.rows(c.full(self.subtree(c)))
            if len(screen) > MAX_QUERY_CHARS:
                print(f"Trace cannot descend into {c.name}: its SQL is too long")
                self.blocked.add(c.name)
                continue
            got = self.runner.level(
                [("?", screen)], exclude, f"can {c.name} explain a row"
            )
            if got is None:
                self.blocked.add(c.name)
            elif any("?" in got[1].get(key, {}) for key in self.out):
                nxt.append(c)
        return nxt


def _one_moment(
    at, end_tables: set[str], moved: dict[str, bool], build: Build, wh: Warehouse
) -> str:
    """Read a descended table's SQL at the moment the rest of the query reads.

    It is expanded as of the build start, when the build read its inputs; a
    table the Cube side reads at the build end is moved there, after checking
    it did not change in between (BigQuery reads a table at 1 moment).

    Raises:
        pipeline.Refusal: Such a table changed during the build.
    """
    clash = sorted(at.tables & end_tables)
    unknown = [t for t in clash if t not in moved]
    changed = set(changed_between(wh, unknown, build.start, build.end))
    moved |= {t: t in changed for t in unknown}
    if bad := [t for t in clash if moved[t]]:
        raise pipeline.Refusal(
            f"cannot trace through {', '.join(bad)}: it changed during the build, "
            "and BigQuery reads a table at 1 moment per query"
        )
    return repin(at.sql, clash, build.start, build.end)


def _filter_traces(cfg: ViewConfig, groups: list[Group]) -> dict[tuple, ItemTrace]:
    """Rows a dashboard-only filter drops: the reconcile already proved each one."""
    by_id = {c.id: c for c in cfg.comparisons}
    out = {}
    for g in groups:
        comparison = by_id.get(g.comparison_id)
        column = g.value_of("dashboard_filter")
        entry = next(
            (
                e
                for e in (comparison.dashboard_filters if comparison else [])
                if e["dashboard"] == column
            ),
            None,
        )
        if entry is None:
            continue
        step = f"dashboard:filter:{column}"
        out[item_key(g)] = ItemTrace(
            "dashboard",
            g.n_rows,
            Counter({step: g.n_rows}),
            {step: f"dashboard filter {pipeline._dashboard_filter_sql(entry)}"},
        )
    return out


def trace_run(
    cfg: ViewConfig,
    run: RunResult,
    *,
    wh: Warehouse,
    cube: Cube,
    manifest_path: Path = MANIFEST,
    levels: int = MAX_LEVELS,
    max_minutes: float = TRACE_MAX_MINUTES,
) -> TraceResult:
    """Trace every open row group of a run to the steps that drop its rows.

    Call inside `wh.budget`. Every refusal (a comparison's SQL changed, a
    manifest or compiled model missing) comes before the first priced trace
    query. The level-0 total is printed before any trace query runs, and
    each later query's price before it runs, with a running total. A cap, the
    time limit or a failed dry run stops only the bucket it hits, keeping
    what that bucket found; the next bucket still runs.

    Args:
        cfg: The view's config.
        run: The run whose open groups to trace.
        wh: The warehouse.
        cube: Cube, to compile each comparison's rows query again.
        manifest_path: The dbt manifest with compiled SQL for the tables the
            trace descends into.
        levels: How many tables deep to descend.
        max_minutes: The whole trace's time limit.

    Returns:
        Per `item_key`, the trace of each traced group (the one-sided buckets
        of comparisons with `rows`, and dashboard-filtered groups), and each
        stopped bucket's reason.

    Raises:
        pipeline.Refusal: A comparison's SQL changed since the run, or the
            manifest or a model's compiled SQL is missing.
    """
    open_groups = run.applied.open
    out = _filter_traces(
        cfg, [g for g in open_groups if g.bucket == "dashboard_filtered"]
    )
    by_id = {c.id: c for c in cfg.comparisons}
    todo = [
        c
        for c in dict.fromkeys(g.comparison_id for g in open_groups)
        if c in by_id
        and by_id[c].rows is not None
        and any(g.comparison_id == c and g.bucket in TRACED for g in open_groups)
    ]
    if not todo:
        return TraceResult(out)
    meter = _Meter(time.monotonic() + max_minutes * 60 if max_minutes else None)
    schools = network_schools(wh)
    moved: dict[str, bool] = {}
    plans = []
    for cid in todo:
        comparison = by_id[cid]
        sides = pipeline.row_sides(
            cfg,
            comparison,
            wh=wh,
            cube=cube,
            build=run.moment,
            schools=schools,
            fingerprints=run.fingerprints.get(cid, {}),
        )
        shared = sides.cube.tables & sides.dashboard.tables
        for bucket in TRACED:
            groups = [
                g for g in open_groups if g.comparison_id == cid and g.bucket == bucket
            ]
            if groups:
                plans.append(
                    (_Side(cfg, comparison, sides, run.moment, bucket), groups, shared)
                )

    buckets = [
        _Bucket(
            side,
            groups,
            wh=wh,
            manifest=None,
            levels=levels,
            end_tables=set(side.sides.cube.tables - shared),
            moved=moved,
            meter=meter,
        )
        for side, groups, shared in plans
    ]
    if levels:
        roots = [t for b in buckets for t in b.root.query.tables()]
        manifest = Manifest.load(manifest_path, roots)
        manifest.require_compiled(roots, levels)
        for b in buckets:
            b.manifest = manifest

    # Each bucket is priced, and stops, on its own: one bucket's failure never
    # keeps another from being traced.
    usd, ready, stops = 0.0, [], {}
    for b in buckets:
        try:
            usd += sum(wh.estimate(q) for q in b.first_queries())
        except GoogleAPIError as exc:
            reason = f"level 0: the dry run failed ({_failure(exc)})"
            print(f"Trace {b.runner.label} stopped: {reason}")
            stops[(b.side.comparison.id, b.side.bucket)] = reason
            out |= b.stop(reason)
            continue
        ready.append(b)
    print(
        f"Trace: {len(ready)} bucket(s), level 0 costs ${usd:.2f} (dry run); "
        "each deeper level is priced before it runs."
    )
    for b in ready:
        try:
            out |= b.run()
        except Stopped as exc:
            out |= exc.found
            stops[(b.side.comparison.id, b.side.bucket)] = exc.reason
            print(f"Trace {b.runner.label} stopped: {exc.reason}")
    return TraceResult(out, stops=stops)


__all__ = [
    "ItemTrace",
    "Manifest",
    "Step",
    "Stopped",
    "TooComplex",
    "TraceResult",
    "compile_command",
    "item_key",
    "trace_run",
]
