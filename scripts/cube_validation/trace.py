"""Trace each unmatched row of a run to the one SQL step that drops it.

A Cube-only row is traced through the dashboard side's SQL, a dashboard-only
row through Cube's: each step of that side (`sqlsteps`) is neutralized alone,
and a row is attributed to a step when that step alone brings it back, by the
comparison's grain. A row no step at one level recovers may be missing from
a table the side reads: the trace then inlines that table's dbt compiled SQL,
as of the moment, and traces its steps, at most `MAX_LEVELS` tables deep.

Every relaxed variant runs inside one query that rebuilds the unmatched rows
the way the run's reconcile did (`compare.trace_sql`), so no row leaves
BigQuery; each query returns group columns, a step id and a count.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import sqlglot
from google.api_core.exceptions import GoogleAPIError

from . import compare, pipeline
from .bq import Warehouse
from .compare import MANY, NONE, UNREPRODUCED, Group
from .config import Comparison, ViewConfig
from .cube_client import Cube, network_schools
from .moment import Build, changed_between
from .report import RunResult, mask
from .sqlsteps import Query, Step, TableRef
from .timetravel import PROJECT, repin

MAX_LEVELS = 2
# BigQuery refuses a query longer than 1,024K characters.
MAX_QUERY_CHARS = 900_000
# A relaxed variant can multiply rows; BigQuery stops a query past this.
TIMEOUT_S = 600
MANIFEST = (
    Path(__file__).resolve().parents[2] / "src/dbt/kipptaf/target/prod/manifest.json"
)
TRACED = ("cube_only", "dashboard_only")
_MATERIALIZED = ("table", "incremental")


def compile_command(models: Iterable[str]) -> str:
    """The command, run from the repository root, that writes compiled SQL."""
    return (
        "uv run dbt deps --project-dir src/dbt/kipptaf && "
        "uv run dbt compile --project-dir src/dbt/kipptaf "
        "--profiles-dir src/dbt/kipptaf --target prod --target-path target/prod "
        f"--select {' '.join(sorted(models))}"
    )


@dataclass
class ItemTrace:
    """What the trace found for one row group.

    `steps` counts the rows each step alone recovers; `many` the rows more
    than one step recovers, and `recovered` every row each step recovers,
    ambiguous ones included; `unreproduced` per table the rows its own SQL
    already returns, so its steps prove nothing for them; `none` the rows no
    step recovers; `below` the tables the trace stopped above; `failed` the
    queries that failed at run time.
    """

    side: str
    n_rows: int
    steps: Counter = field(default_factory=Counter)
    labels: dict[str, str] = field(default_factory=dict)
    many: int = 0
    recovered: Counter = field(default_factory=Counter)
    unreproduced: Counter = field(default_factory=Counter)
    none: int = 0
    below: tuple[str, ...] = ()
    failed: tuple[str, ...] = ()

    @property
    def unattributed(self) -> int:
        return self.n_rows - sum(self.steps.values())

    @property
    def proven(self) -> bool:
        return self.n_rows > 0 and self.unattributed == 0

    def cause(self) -> list[dict]:
        """Each step with its rows, as triage.json records a proven cause."""
        return [
            {"side": self.side, "step": s, "label": self.labels[s], "n_rows": n}
            for s, n in self.steps.most_common()
        ]

    def evidence(self) -> tuple[str, ...]:
        """Lines for the batch, counts masked below 10."""
        lines = [
            f"{self.labels[s]}: {mask(n)} rows" for s, n in self.steps.most_common()
        ]
        if self.unattributed:
            why = []
            if self.many:
                shared = ", ".join(
                    self.labels[s] if s in self.labels else str(s)
                    for s, _ in self.recovered.most_common()
                    if not str(s).startswith(UNREPRODUCED)
                )
                why.append(
                    f"{mask(self.many)} recovered by more than one step ({shared})"
                )
            why += [
                f"{mask(n)} already returned by the {t} SQL with no step neutralized"
                for t, n in sorted(self.unreproduced.items())
            ]
            if self.none:
                where = f" (below {', '.join(self.below)})" if self.below else ""
                why.append(f"{mask(self.none)} recovered by no step{where}")
            lines.append(
                f"{mask(self.unattributed)} rows unattributed: {'; '.join(why)}"
            )
            lines += [f"a trace query failed ({f})" for f in self.failed]
        return tuple(lines)


def item_key(g: Group) -> tuple:
    return (g.comparison_id, g.bucket, g.dims)


class Manifest:
    """The dbt manifest's materialized models, by `dataset.table`."""

    def __init__(self, path: Path) -> None:
        self.path = path
        if not path.is_file():
            raise pipeline.Refusal(
                f"no dbt manifest at {path}; produce it with: {compile_command([])}"
            )
        nodes = json.loads(path.read_text())["nodes"]
        self._nodes = {k: v for k, v in nodes.items() if k.startswith("model.")}
        self._by_relation = {
            (v.get("schema"), v.get("alias") or v.get("name")): v
            for v in self._nodes.values()
            if v.get("database") in (PROJECT, None)
        }

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
                that writes it.
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
                + compile_command(missing)
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

    def query(self, variants, exclude, combine: bool) -> str:
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
            combine=combine,
        )


class _Runner:
    """Prices and runs a level's queries, reading each result by item."""

    def __init__(self, wh: Warehouse, side: _Side, label: str) -> None:
        self.wh = wh
        self.side = side
        self.label = label
        self.failures: list[str] = []

    def _run(self, queries: list[str], what: str) -> list[dict]:
        usd = sum(self.wh.estimate(q) for q in queries)
        print(
            f"Trace {self.label}, {what}: {len(queries)} "
            f"quer{'y' if len(queries) == 1 else 'ies'}, ${usd:.2f} (dry run)."
        )
        self.wh.refuse_past_caps(usd)
        out = []
        for q in queries:
            try:
                out += self.wh.rows(q, timeout_s=TIMEOUT_S)
            except GoogleAPIError as exc:
                # A neutralized step can fail only at run time (a cast, a
                # scalar subquery); the rows that query covers stay unexplained.
                note = f"{what}: {str(exc).splitlines()[0][:200]}"
                print(f"Trace query failed, {note}")
                self.failures.append(note)
        return out

    def _key(self, row: dict) -> tuple:
        dims = tuple(
            (p.cube, "" if row[p.cube] is None else str(row[p.cube]))
            for p in pipeline.group_dims(self.side.comparison)
        )
        return (self.side.comparison.id, row["bucket"], dims)

    def level(
        self, variants: list[tuple[str, str]], exclude: list[str], what: str
    ) -> tuple[dict[tuple, Counter], dict[tuple, Counter]]:
        """Each item's rows by the one step that recovers them, and each step's hits.

        Returns:
            Per item, rows by step id (or `MANY`, `NONE`, an `UNREPRODUCED`
            id); and per item, every row each variant recovers.
        """
        whole = self.side.query(variants, exclude, True)
        if len(whole) <= MAX_QUERY_CHARS:
            return self._read(self._run([whole], what))

        # Too long for one query: count each step's rows apart, then count
        # once more over only the steps that share an item.
        base = len(self.side.query([], exclude, False))
        batches: list[list[tuple[str, str]]] = [[]]
        size = base
        for v in variants:
            if batches[-1] and size + len(v[1]) > MAX_QUERY_CHARS:
                batches.append([])
                size = base
            batches[-1].append(v)
            size += len(v[1])
        rows = self._run(
            [self.side.query(b, exclude, False) for b in batches], f"{what}, by step"
        )
        hits: dict[tuple, Counter] = {}
        in_play: dict[tuple, int] = {}
        for r in rows:
            key = self._key(r)
            if r["step_id"] == NONE:
                in_play[key] = int(r["n_rows"])
            else:
                hits.setdefault(key, Counter())[r["step_id"]] += int(r["n_rows"])
        found: dict[tuple, Counter] = {}
        shared: set[str] = set()
        for key, total in in_play.items():
            h = hits.get(key, Counter())
            if len(h) <= 1 and not any(s.startswith(UNREPRODUCED) for s in h):
                found[key] = Counter(h)
                found[key][NONE] += total - sum(h.values())
            else:
                shared |= set(h)
        if shared:
            subset = [v for v in variants if v[0] in shared]
            again = self.side.query(subset, exclude, True)
            if len(again) > MAX_QUERY_CHARS:
                for key in in_play:
                    if key not in found:
                        found[key] = Counter({MANY: in_play[key]})
            else:
                combined, _ = self._read(self._run([again], f"{what}, shared steps"))
                for key in in_play:
                    if key not in found:
                        found[key] = combined.get(key, Counter({NONE: in_play[key]}))
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


def _trace_bucket(
    side: _Side,
    groups: list[Group],
    *,
    wh: Warehouse,
    manifest: Manifest | None,
    levels: int,
    end_tables: set[str],
    moved: dict[str, bool],
) -> dict[tuple, ItemTrace]:
    out = {item_key(g): ItemTrace(side.side, g.n_rows) for g in groups}
    root = _Frame(Query(side.root_sql(), frozenset(side.grain()), side.grain()[0]))
    if manifest is not None and levels:
        manifest.require_compiled(root.query.tables(), levels)
    runner = _Runner(wh, side, f"{side.comparison.id} {side.bucket}")
    kids: dict[int, list[_Frame]] = {}
    blocked: set[str] = set()

    def children(frame: _Frame) -> list[_Frame]:
        """The materialized tables `frame` reads, each as the next frame down."""
        if id(frame) not in kids:
            found = []
            for ref in frame.query.tables():
                node = manifest.model(ref.dataset, ref.name) if manifest else None
                if node is None or not node.get("compiled_code"):
                    continue
                try:
                    at = pipeline._as_of(node["compiled_code"], side.build.start, wh)
                except pipeline.Refusal as exc:
                    # Its rows stay unexplained, below it; the rest go on.
                    print(f"Trace cannot descend into {ref.name}: {exc}")
                    blocked.add(ref.name)
                    continue
                sql = _one_moment(at, end_tables, moved, side.build, wh)
                try:
                    child = _Frame(
                        Query(sql, ref.wanted),
                        (ref.dataset, ref.name),
                        frame,
                        frame.level + 1,
                    )
                    # Free, and it must run read in place: compiled SQL from
                    # another checkout can name a column the table lacks, and
                    # a WITH RECURSIVE runs only at the top of a query.
                    wh.estimate(side.rows(child.full(child.query.sql())))
                except (GoogleAPIError, sqlglot.errors.SqlglotError) as exc:
                    print(f"Trace cannot descend into {ref.name}: {exc}")
                    blocked.add(ref.name)
                    continue
                found.append(child)
            kids[id(frame)] = found
        return kids[id(frame)]

    def subtree(frame: _Frame) -> str:
        """`frame` with every step neutralized, down to the deepest level."""
        below = children(frame) if frame.level < levels else []
        return frame.query.relaxed_all({k.table: subtree(k) for k in below if k.table})

    frames = [root]
    exclude: list[str] = []
    for level in range(levels + 1):
        variants: list[tuple[str, str]] = []
        labels: dict[str, str] = {}
        for frame in frames:
            # The SQL regenerated with nothing neutralized: a row it returns
            # is no step's to explain (a table's build differs from its SQL,
            # or the regeneration changed what the SQL means).
            variants.append(
                (
                    f"{UNREPRODUCED}{frame.name or side.side}",
                    side.rows(frame.full(frame.query.sql())),
                )
            )
            for step in frame.query.steps(side.side, frame.name):
                labels[step.id] = step.label
                variants.append(
                    (step.id, side.rows(frame.full(frame.query.relaxed(step))))
                )
        found, hits = runner.level(
            variants,
            exclude,
            "the side's own SQL" if level == 0 else f"tables {level} deep",
        )
        left = False
        for key, counts in hits.items():
            if key in out:
                out[key].recovered.update(counts)
                for step_id in counts:
                    if step_id in labels:
                        out[key].labels[step_id] = labels[step_id]
        for key, counts in found.items():
            if key not in out:
                continue
            item = out[key]
            item.none = counts.get(NONE, 0)
            left = left or item.none > 0
            for step_id, n in counts.items():
                if step_id == NONE:
                    continue
                if step_id == MANY:
                    item.many += n
                elif step_id.startswith(UNREPRODUCED):
                    item.unreproduced[step_id[1:]] += n
                else:
                    item.steps[step_id] += n
                    item.labels[step_id] = labels[step_id]
        if not left or manifest is None:
            break
        if level == levels:
            blocked |= {
                ref.name
                for f in frames
                for ref in f.query.tables()
                if manifest.model(ref.dataset, ref.name)
            }
            break

        # Rows a variant here recovered stay explained here; descend only
        # into a table whose whole subtree, every step neutralized, brings
        # back a row still unexplained.
        recovered = {s for key in out for s in hits.get(key, {})}
        exclude += [sql for step_id, sql in variants if step_id in recovered]
        candidates = [k for f in frames for k in children(f)]
        if not candidates:
            break
        # One query per table, so one whose relaxed build runs away (every
        # filter off can multiply rows) costs only itself.
        frames = []
        for c in candidates:
            screen = side.rows(c.full(subtree(c)))
            if len(screen) > MAX_QUERY_CHARS:
                print(f"Trace cannot descend into {c.name}: its SQL is too long")
                blocked.add(c.name)
                continue
            failed = len(runner.failures)
            _, screened = runner.level(
                [("?", screen)], exclude, f"can {c.name} explain a row"
            )
            if len(runner.failures) > failed:
                blocked.add(c.name)
            elif any("?" in screened.get(key, {}) for key in out):
                frames.append(c)
        if not frames:
            break
    for item in out.values():
        if item.none:
            item.below = tuple(sorted(blocked))
        if item.unattributed:
            item.failed = tuple(runner.failures)
    return out


def _one_moment(
    at, end_tables: set[str], moved: dict[str, bool], build: Build, wh: Warehouse
) -> str:
    """Read a descended table's SQL at the moment the rest of the query reads.

    It is expanded as of the build start, when the build read its inputs; a
    table the Cube side reads at the build end is moved there, after checking
    it did not change in between (BigQuery reads a table at 1 moment).
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
) -> dict[tuple, ItemTrace]:
    """Trace every open row group of a run to the steps that drop its rows.

    Call inside `wh.budget`: every query is priced and counted there, and
    each level's dry-run total is printed and checked against the caps
    before it runs.

    Args:
        cfg: The view's config.
        run: The run whose open groups to trace.
        wh: The warehouse.
        cube: Cube, to compile each comparison's rows query again.
        manifest_path: The dbt manifest with compiled SQL for the tables the
            trace descends into.
        levels: How many tables deep to descend.

    Returns:
        Per `item_key`, the trace of each traced group: the one-sided buckets
        of comparisons with `rows`, and dashboard-filtered groups.

    Raises:
        pipeline.Refusal: A comparison's SQL changed since the run, or the
            manifest lacks compiled SQL for a table to descend into.
        CostCapError: A level would pass the run's or the day's cap.
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
        return out
    manifest = Manifest(manifest_path) if levels else None
    schools = network_schools(wh)
    moved: dict[str, bool] = {}
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
        end_tables = set(sides.cube.tables - shared)
        for bucket in TRACED:
            groups = [
                g for g in open_groups if g.comparison_id == cid and g.bucket == bucket
            ]
            if not groups:
                continue
            out |= _trace_bucket(
                _Side(cfg, comparison, sides, run.moment, bucket),
                groups,
                wh=wh,
                manifest=manifest,
                levels=levels,
                end_tables=end_tables,
                moved=moved,
            )
    return out


__all__ = ["ItemTrace", "Manifest", "Step", "compile_command", "item_key", "trace_run"]
