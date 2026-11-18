"""`compare`: check, price and run each comparison's queries, skipping the
ones that cannot run, and keep each finished one as its latest result."""

from __future__ import annotations

import dataclasses
import functools
import re
import uuid
from collections.abc import Callable, Iterable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from google.api_core.exceptions import GoogleAPIError

from . import checkpoints, coverage, latest, reconcile, report, saved, tableau
from .bq import CostCapError, Warehouse, job_failure
from .config import Comparison, ViewConfig
from .cube_client import Cube, network_schools
from .moment import (
    WINDOW,
    Build,
    MomentError,
    changed_between,
    fact_builds,
    fingerprint_sql,
    pick_moment,
)
from .pipeline import (
    SQL_BROKEN,
    SQL_ERRORS,
    Cell,
    Expand,
    Refusal,
    RowSides,
    Sides,
    Skip,
    cell_query,
    checkpoint_fingerprint,
    comparison_cuts,
    cut_flags,
    cut_label,
    dashboard_predicate,
    dashboard_ref,
    dashboard_rows_sql,
    date_cubes,
    expanded_fingerprints,
    inline_unmatched,
    reconcile_args,
    row_pairs,
    row_query,
    sheet_query,
    sheet_query_fingerprint,
    side_fingerprints,
    sql_broken,
    unique,
    value_key,
    wrap_cube,
)
from .rebuild import TABLEAU_ANSWERED, missing_members, workbook_check
from .report import RunResult
from .results import (
    ENTRY_CHANGED,
    NEVER_COMPARED,
    compose_run,
    composed_from,
    last_run,
    stale_comparisons,
)
from .timetravel import repin, utc_literal

# What varies between 2 runs skipped for the same reason: a BigQuery job id,
# and a UTC time (`utc_literal`, or ISO).
_JOB_ID = re.compile(r"\bjob [^\s,)]+")
_UTC_TIME = re.compile(
    r"\d{4}-\d\d-\d\d[ T]\d\d:\d\d:\d\d(?:\.\d+)?(?:[+-]\d\d:\d\d|Z)?"
)


def _skip_keys(skips: Iterable[Skip]) -> list[tuple[str, str]]:
    """Each skip as its comparison and its reason with job ids and times masked,
    so the same skip twice keys alike and a changed reason does not."""
    return [
        (s.comparison, _UTC_TIME.sub("<time>", _JOB_ID.sub("job ?", s.why)))
        for s in skips
    ]


def _say_skips(skips: list[Skip]) -> None:
    for s in skips:
        print(f"Skipping {s.comparison}: {s.why.rstrip('.')}.")


def _refuse_all_skipped(
    cfg: ViewConfig, comparisons: list[Comparison], skips: list[Skip]
) -> None:
    """Refuse when every one of `comparisons` is skipped: nothing would run.

    Raises:
        Refusal: Every comparison is in `skips`.
    """
    if {c.id for c in comparisons} <= {s.comparison for s in skips}:
        raise Refusal(
            f"{cfg.view}: every comparison was skipped; see the reasons above"
        )


def _students_sql(cfg: ViewConfig, comparison: Comparison, student: str) -> str:
    """Return distinct `student` values per cell, one `UNION ALL` branch per cut.

    Each branch reads exactly the rows its cut's cells come from: the cut's
    predicate with the `dashboard_filters`, grouped by the dims as
    `sheet_query_sql` groups them. `__cut` is the cut's index in `comparison_cuts`.
    """
    # trunk-ignore(bandit/B608): identifiers are validated in config.py and values are bound or literal-escaped
    rows = f"SELECT * FROM {dashboard_ref(comparison)}"
    dates = date_cubes(cfg)
    dims = [
        f"DATE({d.dashboard}) AS {d.dashboard}" if d.cube in dates else d.dashboard
        for d in comparison.dims
    ]
    group = (
        " GROUP BY " + ", ".join(str(i + 2) for i in range(len(dims))) if dims else ""
    )
    count = f"COUNT(DISTINCT {student}) AS n_students"
    return " UNION ALL ".join(
        # trunk-ignore(bandit/B608): identifiers are validated in config.py and values are bound or literal-escaped
        f"(SELECT {', '.join([f'{i} AS __cut', *dims, count])} FROM ({rows}) "
        f"WHERE {dashboard_predicate(comparison, cut)}{group})"
        for i, cut in enumerate(comparison_cuts(comparison))
    )


def _number(value: Any) -> float | None:
    return None if value is None else float(value)


def _by_key(rows: Iterable[dict], key, value, where: str) -> dict:
    """Index rows by cell key, refusing 2 rows that land on one cell."""
    out: dict = {}
    for r in rows:
        k = key(r)
        if k in out:
            raise Refusal(
                f"{where}: 2 rows share the cell {', '.join(k) or '(total)'}; "
                "the dims do not pick out one cell"
            )
        out[k] = value(r)
    return out


def _cells(
    comparison: Comparison,
    cut: dict[str, Any],
    dash_rows: list[dict],
    cube_rows: list[dict],
    decimals: int,
    unfiltered_rows: list[dict] | None = None,
) -> list[Cell]:
    """Compare a cut's cells. A Cube-only cell that the sheet query without the
    `dashboard_filters` reproduces reads `dashboard_filtered`: the sheet's
    dashboard-only filter drops it, so it is explained, not a difference.
    """
    where = f"{comparison.id} {cut_label(cut)}"
    dash = _by_key(
        dash_rows,
        lambda r: tuple(value_key(r[d.dashboard]) for d in comparison.dims),
        lambda r: _number(r["value"]),
        f"{where} dashboard",
    )
    cube = _by_key(
        cube_rows,
        lambda r: tuple(value_key(r[d.cube]) for d in comparison.dims),
        lambda r: _number(r["value"]),
        f"{where} Cube",
    )
    unfiltered = (
        _by_key(
            unfiltered_rows,
            lambda r: tuple(value_key(r[d.dashboard]) for d in comparison.dims),
            lambda r: _number(r["value"]),
            f"{where} dashboard without its dashboard-only filters",
        )
        if unfiltered_rows is not None
        else {}
    )
    cells = []
    for key in sorted(dash.keys() | cube.keys()):
        label = ", ".join(
            f"{d.cube}={v}" for d, v in zip(comparison.dims, key, strict=True)
        )
        verdict = reconcile.cell_verdict(dash.get(key), cube.get(key), decimals)
        if (
            verdict == "cube_only"
            and key in unfiltered
            and reconcile.cell_verdict(unfiltered[key], cube[key], decimals) == "pass"
        ):
            verdict = "dashboard_filtered"
        cells.append(
            Cell(
                comparison.id,
                cut_label(cut),
                label or "(total)",
                dash.get(key),
                cube.get(key),
                verdict,
                tuple((d.cube, v) for d, v in zip(comparison.dims, key, strict=True)),
            )
        )
    return cells


def save_script(
    cfg: ViewConfig,
    comparison: Comparison,
    sides: RowSides,
    table: str,
    labels: dict[str, str] | None,
) -> list[str]:
    """The reconcile that also saves the comparison's unmatched rows to `table`.

    With `labels`, the table carries them and expires after
    `saved.SAVED_DAYS`; without (an offline test on DuckDB), it is a plain
    table.
    """
    args, kwargs = reconcile_args(cfg, comparison, sides)
    return reconcile.reconcile_script(
        *args,
        **kwargs,
        table=table,
        labels=labels,
        expire_days=saved.SAVED_DAYS if labels is not None else None,
    )


@dataclasses.dataclass(frozen=True)
class _CutPlan:
    """One cut's cell queries: the dashboard's, Cube's wrapped one, and the
    dashboard's again without its `dashboard_filters` when it has any."""

    label: str
    dash_sql: str
    cube_sql: str
    unfiltered_sql: str | None


@dataclasses.dataclass
class _Plan:
    """Everything comparing one comparison will run, built before any of it
    bills (`_plan_one`), so `compare` can price the whole run first.

    `shared` lists the tables both sides' rows read. `moved` holds whether
    each changed during the build; it is empty until `_compare_all` has
    fingerprinted them, after the price.
    """

    comparison: Comparison
    fingerprints: dict[str, str]
    cuts: list[_CutPlan]
    rows: RowSides | None
    # The save script's rows as 1 query (`inline_unmatched`), to price it.
    unmatched_sql: str | None
    shared: list[str]
    students_sql: str | None
    cube_tables: set[str]
    live: set[str]
    moved: dict[str, bool] = dataclasses.field(default_factory=dict)

    def queries(self) -> list[str]:
        """Every query that bills, in the order `_execute` reads their prices:
        each cut's dashboard, Cube and unfiltered queries, the unmatched rows,
        the student count.

        The save script's temp table cannot be dry-run before it exists, so
        its join (`inline_unmatched`) stands in for it; the script's reads of
        that table still run under `Warehouse.rows`' billing cap.
        """
        out: list[str] = []
        for cut in self.cuts:
            out += [cut.dash_sql, cut.cube_sql]
            if cut.unfiltered_sql is not None:
                out.append(cut.unfiltered_sql)
        if self.unmatched_sql is not None:
            out.append(self.unmatched_sql)
        if self.students_sql is not None:
            out.append(self.students_sql)
        return out


def _plan_one(
    cfg: ViewConfig,
    comparison: Comparison,
    *,
    wh: Warehouse,
    cube: Cube,
    build: Build,
    schools: set[str],
) -> _Plan:
    """Compile, expand and fingerprint one comparison's queries; run none that
    bills.

    Only view history runs here, since it decides which queries exist. Whether
    a table both sides read changed during the build is a priced scan, so
    `_compare_all` answers it after the price (`_settle_moved`).
    """
    dates = date_cubes(cfg)
    dims = [d.cube for d in comparison.dims]
    ex = Expand(cfg, cube, schools, wh)
    cube_sql, at = ex.cube_sql, ex.at
    fingerprints = expanded_fingerprints(cfg, comparison, ex, build)
    cube_tables: set[str] = set()
    live: set[str] = set()
    cuts: list[_CutPlan] = []
    for cut in comparison_cuts(comparison):
        cube_at = at(cube_sql(cell_query(cfg.view, comparison, cut)), build.end)
        dash_at = at(sheet_query(cfg, comparison, cut), build.start)
        cube_tables |= cube_at.tables
        live |= cube_at.live | dash_at.live
        unfiltered = None
        if comparison.dashboard_filters:
            # The sheet query again without them, to name the cells they drop.
            unfiltered = at(
                sheet_query(cfg, comparison, cut, with_filters=False), build.start
            ).sql
        cuts.append(
            _CutPlan(
                cut_label(cut),
                dash_at.sql,
                wrap_cube(cube_at.sql, cfg.view, dims, dates, comparison.measure),
                unfiltered,
            )
        )

    rows, unmatched_sql, students_sql = None, None, None
    shared: list[str] = []
    if comparison.rows is not None:
        cube_at = at(cube_sql(row_query(cfg.view, comparison), rows=True), build.end)
        dash_at = at(dashboard_rows_sql(cfg, comparison), build.start)
        cube_tables |= cube_at.tables
        live |= cube_at.live | dash_at.live
        shared = sorted(cube_at.tables & dash_at.tables)
        # Unchanged between start and end (`_settle_moved` skips otherwise),
        # so the Cube side reads its shared tables at the start: BigQuery
        # refuses 1 table at 2 moments.
        rows = RowSides(
            cube=cube_at,
            dashboard=dash_at,
            cube_rows_sql=repin(cube_at.sql, shared, build.end, build.start),
            columns=unique(p.cube for p in row_pairs(comparison)),
        )
        unmatched_sql = inline_unmatched(cfg, comparison, rows)
        # Only a student column counts students; without one in the grain,
        # every cell's `n_students` stays None, so none is an example cell.
        student = next(
            (
                p.dashboard
                for p in comparison.rows.grain
                if "student" in p.dashboard.lower()
            ),
            None,
        )
        if student:
            students_sql = at(_students_sql(cfg, comparison, student), build.start).sql
    return _Plan(
        comparison=comparison,
        fingerprints=fingerprints,
        cuts=cuts,
        rows=rows,
        unmatched_sql=unmatched_sql,
        shared=shared,
        students_sql=students_sql,
        cube_tables=cube_tables,
        live=live,
    )


def _settle_moved(
    plan: _Plan, known: dict[str, bool], changed: set[str]
) -> Skip | None:
    """Fill `plan.moved` for every table both sides read, from `known` (a held
    checkpoint's answer, or a second fact) else `changed`.

    Returns:
        A skip when such a table changed during the build: BigQuery reads a
        table at 1 moment per query, so the rows cannot be reconciled.
    """
    plan.moved = {t: known.get(t, t in changed) for t in plan.shared}
    if both_moved := [t for t in plan.shared if plan.moved[t]]:
        return Skip(
            plan.comparison.id,
            f"both sides read {', '.join(both_moved)}, which changed during the "
            "build; BigQuery reads a table at 1 moment per query, so the rows "
            "cannot be reconciled at this build",
        )
    return None


def _execute(
    cfg: ViewConfig,
    plan: _Plan,
    *,
    wh: Warehouse,
    build: Build,
    prices: list[float],
) -> Sides:
    """Run a plan's queries; return its comparison's slice of the run.

    The rows are reconciled in one job that also saves the unmatched ones to
    the scratch dataset (`save_script`), labelled with the view, the moment,
    the comparison and its `checkpoint_fingerprint`.

    Args:
        prices: Each of `plan.queries()`'s dry-run prices, in its order; a
            cut's 2 cell prices are kept as its `cell_sql_usd`. One left over
            means `queries()` and this function no longer agree.
    """
    comparison = plan.comparison
    sides = Sides(
        cube_tables=set(plan.cube_tables), live=set(plan.live), moved=dict(plan.moved)
    )
    sides.fingerprints[comparison.id] = plan.fingerprints
    price = iter(prices)
    for cut, step in zip(comparison_cuts(comparison), plan.cuts, strict=True):
        sides.cell_sql.setdefault(comparison.id, {})[step.label] = [
            step.dash_sql,
            step.cube_sql,
        ]
        sides.cell_sql_usd.setdefault(comparison.id, {})[step.label] = [
            next(price),
            next(price),
        ]
        cube_rows = wh.rows(step.cube_sql)
        dash_rows = wh.rows(step.dash_sql)
        unfiltered = None
        if step.unfiltered_sql is not None:
            next(price)
            unfiltered = wh.rows(step.unfiltered_sql)
        sides.cells += _cells(
            comparison, cut, dash_rows, cube_rows, comparison.decimals or 0, unfiltered
        )

    if plan.rows is not None:
        next(price)  # the unmatched rows, which stood in for the save script
        flags = cut_flags(comparison) or []
        result = wh.script(
            save_script(
                cfg,
                comparison,
                plan.rows,
                saved.table_sql(saved.table_id(cfg.view, build, comparison.id)),
                saved.labels(
                    cfg.view,
                    build,
                    comparison.id,
                    checkpoint_fingerprint(comparison, plan.fingerprints),
                ),
            )
        )
        sides.groups += reconcile.groups_from(
            comparison.id, result, [label for label, _, _ in flags]
        )
        sides.sql[comparison.id] = (plan.rows.dashboard.sql, plan.rows.cube.sql)
    if plan.students_sql is not None:
        next(price)
        cuts = comparison_cuts(comparison)
        sides.students[comparison.id] = {
            (
                cut_label(cuts[int(r["__cut"])]),
                tuple(value_key(r[d.dashboard]) for d in comparison.dims),
            ): r["n_students"]
            for r in wh.rows(plan.students_sql)
        }
    if next(price, None) is not None:
        raise RuntimeError("prices left over: plan.queries() changed")
    return sides


def _unmatched_totals(comparisons: list[Comparison]) -> list[str]:
    """Comparisons whose rebuild check skipped the export's total rows, or
    cannot say."""
    out = []
    for comparison in comparisons:
        skipped = (
            comparison.rebuild_check.totals_skipped
            if comparison.rebuild_check
            else None
        )
        if skipped is None:
            out.append(
                f"{comparison.id}: totals not matched: unknown (the rebuild check "
                "records no count); re-run `rebuild-sheet`"
            )
        elif skipped > 0:
            out.append(f"{comparison.id}: totals not matched: {skipped} rows")
    return out


def _say_caveats(comparisons: list[Comparison], skips: list[Skip]) -> list[str]:
    """Print what the confirmed `comparisons` leave unchecked, and return the
    totals lines for `run.json`.

    Called once every skip is known. A skipped comparison keeps its latest
    result, which leaves its sheet's total rows unchecked just as before, so it
    keeps its totals line (`_unmatched_totals`) when it has a rebuild check; one
    skipped for having none already says to run `rebuild-sheet`. Only a
    comparison compared in this run gets an uncoverable-cells line.
    """
    gone = {s.comparison for s in skips}
    kept = [c for c in comparisons if c.id not in gone]
    totals = _unmatched_totals(
        [c for c in comparisons if c.id not in gone or c.rebuild_check]
    )
    for line in totals:
        print(f"{line}.")
    for comparison in kept:
        if why := coverage.unplaceable(comparison):
            print(
                f"Comparison {comparison.id}: its cells cannot be covered ({why}); "
                "its differing cells stay open."
            )
    return totals


def _moved_fact_skips(
    cfg: ViewConfig, build: Build, changed: set[str], reads: dict[str, set[str]]
) -> list[Skip]:
    """Skip each comparison whose Cube SQL reads a fact in `cfg.also_facts`
    that is among the `changed` tables.

    The moment is a build of `cfg.fact`: the dashboard is read at its start and
    Cube at its end, so a second fact must hold still in between, or Cube's
    answer mixes 2 moments of it. A second fact has no build of its own to
    pick, so only this check applies to it.

    Args:
        reads: Per comparison id, the tables its Cube SQL reads.
    """
    moved = [f for f in cfg.also_facts if f in changed]
    out = []
    for cid, tables in reads.items():
        if facts := [f for f in moved if f in tables]:
            out.append(
                Skip(
                    cid,
                    f"{', '.join(facts)} changed during the build of {cfg.fact} "
                    f"({utc_literal(build.start)} to {utc_literal(build.end)}); "
                    "Cube reads it at the build end and the dashboard's inputs "
                    "are read at the start, so pick another build with `--moment`",
                )
            )
    return out


# The keys a comparison needs before `compare` can build its queries.
_NEEDED = ("dashboard_view", "decimals")


def _early_skips(
    cfg: ViewConfig, comparisons: list[Comparison], *, tbl: tableau.Tableau, cube: Cube
) -> list[Skip]:
    """The comparisons `compare` skips before any query, in the order found.

    A comparison is skipped when it lacks a key a run needs (`_NEEDED`), it
    has no rebuild check, its sheet query changed since the check, it maps a
    member Cube's `/meta` lacks (`missing_members`), or its workbook changed
    since the check or Tableau errs on it (`workbook_check`). Each check reads
    only the comparisons no earlier check skipped.
    """
    skips: list[Skip] = []

    def left() -> list[Comparison]:
        gone = {s.comparison for s in skips}
        return [c for c in comparisons if c.id not in gone]

    for c in comparisons:
        if missing := [k for k in _NEEDED if getattr(c, k) in (None, "")]:
            skips.append(Skip(c.id, f"it has no {', '.join(missing)}"))
        elif c.rebuild_check is None:
            skips.append(Skip(c.id, "no rebuild check; run `rebuild-sheet` first"))
        elif c.rebuild_check.sheet_query_fingerprint != sheet_query_fingerprint(cfg, c):
            skips.append(
                Skip(
                    c.id,
                    "the sheet query is not the one its rebuild check covers; run "
                    "`rebuild-sheet` again",
                )
            )
    meta = cube.meta()
    for c in left():
        if missing := missing_members(cfg, [c], meta):
            members = ", ".join(line.removeprefix(f"{c.id}: ") for line in missing)
            skips.append(
                Skip(
                    c.id,
                    f"Cube's model has no member for {members}; fix the mapping, "
                    "then run `rebuild-sheet` again",
                )
            )
    remaining = left()
    stale = workbook_check(cfg, remaining, tbl=tbl, cube=cube)
    for c in remaining:
        if lines := [
            s.removeprefix(f"{c.id}: ") for s in stale if s.startswith(f"{c.id}: ")
        ]:
            what = (
                "the workbook could not be checked"
                if lines[0].startswith(TABLEAU_ANSWERED)
                else "workbook changed since its rebuild check"
            )
            skips.append(Skip(c.id, f"{what}: {'; '.join(lines)}"))
    return skips


def _bigquery_skip(comparison: str, what: str, exc: GoogleAPIError) -> Skip:
    """A skip for a BigQuery error: fixed words with the job and reason code,
    never BigQuery's message, which can quote values."""
    return Skip(
        comparison,
        f"{what} failed in BigQuery ({job_failure(exc)}); compare it again later",
    )


def _sql_skips(
    cfg: ViewConfig,
    comparisons: list[Comparison],
    *,
    wh: Warehouse,
    cube: Cube,
    schools: set[str],
    now: datetime,
) -> list[Skip]:
    """Each of `comparisons` whose SQL cannot be built today, as
    `stale_comparisons` words it. Compiles and expands only; no query bills."""
    build = Build(now, now, "now")
    out = []
    for c in comparisons:
        try:
            side_fingerprints(cfg, c, wh=wh, cube=cube, build=build, schools=schools)
        except SQL_ERRORS as exc:
            out.append(Skip(c.id, sql_broken(exc)))
    return out


# A stopped run resumes on its own within this long of its last checkpoint;
# after it, only with `--resume`, up to time travel's reach.
AUTO_RESUME = timedelta(hours=24)
RESUME_LIMIT = timedelta(days=7)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _run_folder(
    cfg: ViewConfig,
    wh: Warehouse,
    *,
    now: datetime,
    requested: datetime | None,
    resume: bool,
    restart: bool,
    cache_root: Path,
    clock: Callable[[], datetime],
    selected: list[Comparison],
) -> tuple[Path, Build]:
    """The run folder and moment for this `compare`: an unfinished run's, or new.

    With `requested`, the moment is the build it names; its folder's
    checkpoints are reused only when that run is unfinished. Otherwise an
    unfinished run of the view resumes on its own when its last checkpoint is
    under `AUTO_RESUME` old, with `resume` up to `RESUME_LIMIT`, and never past
    it. `restart` clears an unfinished run and starts a new one. A folder a new
    run lands in starts with no checkpoints.

    Raises:
        Refusal: `resume` with nothing to resume, an unfinished run that needs
            `--resume` or `--restart`, or one too old to resume.
    """

    def resuming(u: checkpoints.Unfinished, build: Build) -> None:
        # Only the comparisons this run compares: the others keep their result.
        ids = {c.id for c in selected}
        saved_ids = set(checkpoints.read_all(u.folder)) & ids
        print(
            f"Resuming the unfinished run of {utc_literal(build.start)} to "
            f"{utc_literal(build.end)}: {len(saved_ids)} of {len(ids)} "
            f"comparisons saved, the last at {utc_literal(u.last_at)}."
        )

    if requested is not None:
        build = pick_moment(
            fact_builds(wh, cfg.fact, since=now - WINDOW), now, requested, cfg.fact
        )
        folder = report.run_dir(cache_root, cfg.view, build)
        there = checkpoints.unfinished(folder)
        if restart or there is None or there.fact != cfg.fact:
            checkpoints.clear(folder, keep_spend_of=None if restart else cfg.fact)
        else:
            resuming(there, build)
        return folder, build

    unfinished = checkpoints.find_unfinished(cache_root, cfg.view, cfg.fact)
    if unfinished is not None and restart:
        checkpoints.clear(unfinished.folder)
        unfinished = None
    if unfinished is None and resume:
        raise Refusal(f"no unfinished run of {cfg.view} to resume")
    if unfinished is not None:
        age = clock() - unfinished.last_at
        stamp = report.run_stamp(unfinished.moment)
        if age > RESUME_LIMIT:
            raise Refusal(
                f"{cfg.view}: an unfinished run of {stamp} stopped more than 7 days "
                "ago, past time travel; pass --restart to start a new run"
            )
        if age >= AUTO_RESUME and not resume:
            raise Refusal(
                f"{cfg.view}: an unfinished run of {stamp} stopped "
                f"{age.total_seconds() / 3600:.0f} hours ago; pass --resume to "
                "finish it at that moment, or --restart to start a new run"
            )
        try:
            build = pick_moment([unfinished.moment], now, None, cfg.fact)
        except MomentError as exc:
            raise Refusal(
                f"{cfg.view}: the unfinished run of {stamp} cannot resume: {exc}; "
                "pass --restart to start a new run"
            ) from exc
        resuming(unfinished, build)
        return unfinished.folder, build

    build = pick_moment(
        fact_builds(wh, cfg.fact, since=now - WINDOW), now, None, cfg.fact
    )
    folder = report.run_dir(cache_root, cfg.view, build)
    checkpoints.clear(folder, keep_spend_of=None if restart else cfg.fact)
    return folder, build


ALL_CURRENT = (
    "Every comparison's latest result is current; pass --all to compare every one "
    "again."
)
OTHERS_CURRENT = (
    "Every comparison not skipped has a current latest result; pass --all to "
    "compare every one again."
)


def compare(
    cfg: ViewConfig,
    *,
    wh: Warehouse,
    cube: Cube,
    now: datetime,
    requested: datetime | None,
    max_usd: float,
    cache_root: Path,
    tbl: tableau.Tableau,
    cube_host: str = "",
    resume: bool = False,
    restart: bool = False,
    clock: Callable[[], datetime] = _utcnow,
    ticker: report.Ticker | None = None,
    only: list[str] | None = None,
    every: bool = False,
) -> RunResult | None:
    """Compare a view's comparisons at one fact build and print the validation.

    A validation is each confirmed comparison's latest result, each at its own
    moment (`latest`). `only` compares those comparisons; `every` compares
    every confirmed one; with neither, only those `stale_comparisons` names,
    each printed with its why first. With none, it says so and returns None
    without writing, unless the last `run.json` of `cfg.fact` was composed
    from other results (a run stopped after keeping them): that is composed
    again, at no cost. Each comparison compared replaces its latest result of
    `cfg.fact`'s dataset (`latest.folder`) as it finishes; `run.json` in this
    run's folder is then composed from every confirmed comparison's latest
    result there.

    `cube_host` is printed with `cfg.fact` so the result says what it was
    compared against. A problem with one comparison skips it instead of
    stopping the run: each skip prints `Skipping <id>: <why>.`, the rest are
    compared, and the skipped one keeps its latest result. Before any query,
    a confirmed comparison is skipped when it lacks a key it needs, has no
    rebuild check, its sheet query or workbook changed since the check, or it
    maps a member Cube lacks, or Tableau errs on its workbook
    (`_early_skips`); before the price, when its SQL cannot be built today
    (`_sql_skips`) or at the run's moment, or a dry run it needs fails; after
    the price, when its Cube SQL reads a fact in `also_facts` that changed
    during the build, both sides' rows read a table that did, or one of its
    queries fails in BigQuery, whose spend stays counted (`_compare_all`). A
    BigQuery error is skipped as its job and reason code, never its message,
    which can quote values; only a cap (`CostCapError`) stops the run. The
    skips are kept in `run.json` as `skipped`. Every query a comparison bills
    is priced before the first one runs (`_compare_all`), and `ticker` prints
    a line as each comparison finishes. Each comparison it finishes is
    checkpointed in the run folder; a stopped run started again skips them
    (`_run_folder` says when it resumes). A checkpoint whose comparison entry
    or SQL changed is compared again. `cost_usd` adds what every process spent
    on this run's folder.

    Raises:
        Refusal: `only` names no confirmed comparison; every confirmed
            comparison, or every one `only` names, is skipped; or an
            unfinished run needs `--resume` or `--restart` (`_run_folder`).
        CostCapError: The priced queries would pass `max_usd` or the day's
            cap.
        MomentError: No usable build in the 7-day window.
        CubeRefusal: Cube's SQL would not match a raw rebuild.
    """
    if resume and requested is not None:
        raise Refusal("`--moment` picks the moment itself; drop `--resume`")
    if only and every:
        raise Refusal("`--comparison` and `--all` pick the comparisons; pass one")
    comparisons = [c for c in cfg.comparisons if c.confirmed]
    for skipped in (c for c in cfg.comparisons if not c.confirmed):
        print(f"Skipping comparison {skipped.id!r}: not confirmed.")
    if not comparisons:
        raise Refusal(f"{cfg.view}: no confirmed comparison to run")
    if only and (unknown := sorted(set(only) - {c.id for c in comparisons})):
        raise Refusal(
            f"--comparison: {', '.join(unknown)} is no confirmed comparison of "
            f"{cfg.view}"
        )
    # Every confirmed comparison, before the run folder or any query; a member
    # the model dropped would refuse only after every query ran.
    skips = _early_skips(cfg, comparisons, tbl=tbl, cube=cube)
    _say_skips(skips)
    _refuse_all_skipped(cfg, comparisons, skips)
    ready = [c for c in comparisons if c.id not in {s.comparison for s in skips}]
    for comparison in ready:
        if comparison.rebuild_check:
            print(
                f"Rebuild check for {comparison.id}: matched "
                f"{comparison.rebuild_check.matched_at}."
            )

    results_dir = latest.folder(cache_root / cfg.view, cfg.fact)

    def compose(**kwargs) -> RunResult:
        return compose_run(
            cfg,
            comparisons,
            results_dir,
            cube=cube,
            cube_host=cube_host,
            totals=_say_caveats(comparisons, skips),
            cache_root=cache_root,
            **kwargs,
        )

    with wh.budget(max_usd):
        schools = network_schools(wh)
        sql_skips = functools.partial(
            _sql_skips, cfg, wh=wh, cube=cube, schools=schools, now=now
        )
        results: dict[str, latest.Latest] = {}
        if only:
            selected = [c for c in ready if c.id in only]
            broken = sql_skips(selected)
        elif every:
            selected = ready
            broken = sql_skips(selected)
        else:
            results = latest.read_all(results_dir, cfg.fact)
            whys = stale_comparisons(
                cfg,
                ready,
                results,
                wh=wh,
                cube=cube,
                schools=schools,
                now=now,
            )
            broken = [
                Skip(cid, why)
                for cid, why in whys.items()
                if why.startswith(SQL_BROKEN)
            ]
            for cid, why in whys.items():
                if not why.startswith(SQL_BROKEN):
                    print(f"Comparison {cid}: {why}.")
            selected = [c for c in ready if c.id in whys]
            # Only a result to compare against made `stale_comparisons` build
            # the SQL; build the rest's too.
            broken += sql_skips(
                [c for c in selected if whys[c.id] in (NEVER_COMPARED, ENTRY_CHANGED)]
            )
        # Before the run folder and the price: a skipped comparison's queries
        # are neither priced nor run.
        _say_skips(broken)
        skips += broken
        _refuse_all_skipped(cfg, comparisons, skips)
        selected = [c for c in selected if c.id not in {s.comparison for s in broken}]
        if not selected and only:
            raise Refusal(
                f"{cfg.view}: every comparison asked for was skipped; see the "
                "reasons above"
            )
        if not selected:
            last = last_run(cfg, cache_root)
            if not composed_from(last, comparisons, results):
                # A run stopped after keeping its results, before composing.
                print(
                    "Composing run.json again from the latest results: the last "
                    "one predates them. Nothing is compared."
                )
            elif _skip_keys(
                Skip(**s) for s in (last or {}).get("skipped", [])
            ) != _skip_keys(skips):
                # So `ask-owner` lists what is skipped now.
                print(
                    "Composing run.json again to record the comparisons skipped. "
                    "Nothing is compared."
                )
            else:
                _say_caveats(comparisons, skips)
                print(OTHERS_CURRENT if skips else ALL_CURRENT)
                return None
            newest = max((r.moment for r in results.values()), key=lambda m: m.end)
            folder = report.run_dir(cache_root, cfg.view, newest)
            return compose(
                build=newest,
                folder=folder,
                cost=checkpoints.total_spend(folder),
                skipped=skips,
            )
        folder, build = _run_folder(
            cfg,
            wh,
            now=now,
            requested=requested,
            resume=resume,
            restart=restart,
            cache_root=cache_root,
            clock=clock,
            selected=selected,
        )
        process = f"{clock().isoformat()}-{uuid.uuid4().hex[:8]}"
        checkpoints.start(folder, build, process, cfg.fact)
        try:
            skips += _compare_all(
                cfg,
                selected,
                wh=wh,
                cube=cube,
                build=build,
                folder=folder,
                process=process,
                clock=clock,
                schools=schools,
                results_dir=results_dir,
                ticker=ticker,
            )
        finally:
            checkpoints.record_spend(folder, process, wh.spent)
        cost = checkpoints.total_spend(folder)
    _refuse_all_skipped(cfg, comparisons, skips)
    gone = {s.comparison for s in skips}
    return compose(
        build=build,
        folder=folder,
        cost=cost,
        skipped=skips,
        compared=[c.id for c in selected if c.id not in gone],
    )


def _compare_all(
    cfg: ViewConfig,
    comparisons: list[Comparison],
    *,
    wh: Warehouse,
    cube: Cube,
    build: Build,
    folder: Path,
    process: str,
    clock: Callable[[], datetime],
    schools: set[str],
    results_dir: Path,
    ticker: report.Ticker | None = None,
) -> list[Skip]:
    """Compare each of `comparisons` at `build` and keep each one's result as
    its latest (`latest.write`); return the comparisons it skipped. Call
    inside `wh.budget`.

    A comparison with a checkpoint whose fingerprint still holds is taken from
    it; the rest are planned (`_plan_one`). Before anything that bills, every
    table fingerprint the run needs (the second facts, the tables both sides'
    rows read, Cube's dimension tables) and every planned query is dry-run one
    at a time, and the total is refused when it would pass a cap. The
    fingerprints then run before any comparison query: a comparison whose
    Cube SQL reads a second fact that changed during the build
    (`_moved_fact_skips`), or whose 2 sides' rows both read a table that did
    (`_settle_moved`), is skipped, its priced queries left unrun and its
    latest result kept. The comparisons are compared one at a time, each
    checkpointed (with the spend so far) as it finishes, so a stop loses at
    most the one in progress. Each result keeps the dimension tables it read
    that changed during the build (`changed_dims`). A held checkpoint is kept
    as the latest result only when no later moment's result has replaced it
    since. A comparison whose SQL cannot be built at `build`, whose dry run
    or a table scan it needs fails, or one of whose queries fails in BigQuery
    is skipped and the rest run.

    Raises:
        CostCapError: The priced total would pass the run's or the day's cap,
            or a query would.
    """
    kept = checkpoints.read_all(folder)
    slices: dict[str, tuple[str, Sides]] = {}
    plans: list[_Plan] = []
    skips: list[Skip] = []
    for comparison in comparisons:
        try:
            if comparison.id in kept:
                fingerprint, data = kept[comparison.id]
                now = checkpoint_fingerprint(
                    comparison,
                    side_fingerprints(
                        cfg, comparison, wh=wh, cube=cube, build=build, schools=schools
                    ),
                )
                if now == fingerprint:
                    slices[comparison.id] = (fingerprint, Sides.from_json(data))
                    continue
                print(
                    f"Comparison {comparison.id}: its config or SQL changed since "
                    "its saved result; comparing it again."
                )
            plans.append(
                _plan_one(
                    cfg, comparison, wh=wh, cube=cube, build=build, schools=schools
                )
            )
        except SQL_ERRORS as exc:
            # Built at the run's moment, which `_sql_skips` did not check.
            skips.append(Skip(comparison.id, sql_broken(exc)))

    # One dry run at a time; one that fails skips the comparison it prices.
    prices: list[list[float]] = []
    for plan in list(plans):
        try:
            prices.append([wh.estimate(sql) for sql in plan.queries()])
        except GoogleAPIError as exc:
            plans.remove(plan)
            skips.append(_bigquery_skip(plan.comparison.id, "its dry run", exc))

    # The second facts have their own check below, and a held checkpoint
    # already answered its shared tables, so neither joins `shared`.
    known = {f: False for f in cfg.also_facts}
    for _, held in slices.values():
        known |= held.moved
    cube_tables = set().union(
        *(p.cube_tables for p in plans), *(h.cube_tables for _, h in slices.values())
    )
    dims = sorted(cube_tables - {cfg.fact, *cfg.also_facts})
    shared = sorted({t for p in plans for t in p.shared if t not in known})
    # Each table once, at both ends of the build, whichever checks need it.
    scanned = unique([*cfg.also_facts, *shared, *dims])
    scan_usd = 0.0
    for t in list(scanned):
        try:
            scan_usd += sum(
                wh.estimate(fingerprint_sql(t, ts)) for ts in (build.start, build.end)
            )
        except GoogleAPIError as exc:
            # Unscanned, so every comparison that reads it is skipped.
            scanned.remove(t)
            readers = [
                p.comparison.id for p in plans if t in p.cube_tables | set(p.shared)
            ]
            readers += [cid for cid, (_, h) in slices.items() if t in h.cube_tables]
            skips += [
                _bigquery_skip(cid, f"the dry run of a scan of {t}", exc)
                for cid in readers
            ]
    gone = {s.comparison for s in skips}
    slices = {cid: v for cid, v in slices.items() if cid not in gone}
    priced = [
        (p, pr)
        for p, pr in zip(plans, prices, strict=True)
        if p.comparison.id not in gone
    ]
    plans, prices = [p for p, _ in priced], [pr for _, pr in priced]
    _say_skips(skips)
    said = len(skips)
    total = scan_usd + sum(map(sum, prices))
    n = 2 * len(scanned) + sum(map(len, prices))
    print(
        f"Compare: {n} queries, ${total:.2f} (dry run), plus the save script's "
        "temp-table reads, capped per query."
    )
    wh.refuse_past_caps(total)

    changed = set(changed_between(wh, scanned, build.start, build.end))
    skips += _moved_fact_skips(
        cfg,
        build,
        changed,
        {p.comparison.id: p.cube_tables for p in plans}
        | {cid: held.cube_tables for cid, (_, held) in slices.items()},
    )
    gone = {s.comparison for s in skips}
    slices = {cid: v for cid, v in slices.items() if cid not in gone}
    kept_plans = []
    for plan, priced in zip(plans, prices, strict=True):
        if plan.comparison.id in gone:
            continue
        if skip := _settle_moved(plan, known, changed):
            skips.append(skip)
        else:
            kept_plans.append((plan, priced))
    _say_skips(skips[said:])

    def keep(comparison: Comparison, fingerprint: str, one: Sides) -> None:
        latest.write(
            results_dir,
            comparison.id,
            latest.Latest(
                moment=build,
                fingerprint=fingerprint,
                entry=latest.entry_fingerprint(comparison),
                ran_at=clock().isoformat(),
                data={
                    **one.to_json(),
                    "changed_dims": [t for t in dims if t in changed & one.cube_tables],
                },
                fact=cfg.fact,
            ),
        )

    by_id = {c.id: c for c in comparisons}
    stored = latest.read_all(results_dir, cfg.fact)
    for cid, (fingerprint, held) in slices.items():
        if cid not in stored or stored[cid].moment.end <= build.end:
            keep(by_id[cid], fingerprint, held)
    for plan, priced in kept_plans:
        comparison = plan.comparison
        try:
            one = _execute(cfg, plan, wh=wh, build=build, prices=priced)
        except CostCapError:
            raise
        except GoogleAPIError as exc:
            # Its spend stays counted; the rest still run, so a resume does
            # not stop at it again.
            skip = _bigquery_skip(comparison.id, "a query", exc)
            _say_skips([skip])
            skips.append(skip)
            checkpoints.record_spend(folder, process, wh.spent)
            continue
        fingerprint = checkpoint_fingerprint(comparison, plan.fingerprints)
        checkpoints.write(folder, comparison.id, fingerprint, one.to_json(), clock())
        keep(comparison, fingerprint, one)
        checkpoints.record_spend(folder, process, wh.spent)
        if ticker is not None:
            ticker.say("compare", comparison.id, wh.spent)
    return skips
