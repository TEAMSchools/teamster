"""Each comparison's latest result: the stale check, `run.json` composed from
the results, and the saved run the other commands read and `reapply` writes."""

from __future__ import annotations

import dataclasses
import json
from collections import Counter
from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from . import checkpoints, coverage, decisions, latest, reconcile, report, sort
from .bq import Warehouse
from .config import Comparison, Decision, ViewConfig
from .cube_client import Cube, CubeError
from .decisions import Applied
from .moment import Build
from .pipeline import (
    SQL_COMPARE,
    SQL_ERRORS,
    Cell,
    Refusal,
    Sides,
    Skip,
    checkpoint_fingerprint,
    comparison_cuts,
    cut_label,
    dashboard_filter_sql,
    group_dims,
    group_from_json,
    measure_expression,
    member_name,
    scope_cube_filters,
    side_fingerprints,
    sql_broken,
    unique,
    verdict,
)
from .rebuild import reshape_text
from .reconcile import CellDiff, Gap, Group
from .report import MeasureResult, RunResult

# How a run result names each Cube scope operator.
_SCOPE_WORDS = {"equals": "in", "notEquals": "not in", **SQL_COMPARE}


DIFFERING = ("differs", "cube_only", "dashboard_only")


def candidate_causes(
    comparison: Comparison, cells: list[Cell], decimals: int, cube_expr: str
) -> list[str]:
    """What the differing cells suggest, for the analyst to check, not a verdict.

    Patterns (blank against 0, 1 display unit apart), where the cells cluster
    (a cut, a dim value), and both definitions side by side. A dim that is part
    of the row grain never shows, so no student's value does.
    """
    n = len(cells)
    patterns: Counter = Counter()
    unit = Decimal(1).scaleb(-decimals)
    for c in cells:
        if c.cube is None:
            patterns[
                "Cube is blank where the dashboard shows 0"
                if c.dashboard == 0
                else "Cube is blank where the dashboard shows a value"
            ] += 1
        elif c.dashboard is None:
            patterns[
                "Cube shows 0 where the dashboard is blank"
                if c.cube == 0
                else "Cube shows a value where the dashboard is blank"
            ] += 1
        elif (
            abs(
                reconcile._half_up(c.dashboard, decimals)
                - reconcile._half_up(c.cube, decimals)
            )
            == unit
        ):
            patterns[f"1 display unit apart at {decimals} decimals"] += 1
        else:
            patterns["values differ beyond rounding"] += 1
    out = [
        f"{k} {'cell' if k == 1 else 'cells'}: {pattern}"
        for pattern, k in patterns.most_common()
    ]
    cuts = Counter(c.cut for c in cells)
    top_cut, k = cuts.most_common(1)[0]
    if 2 * k >= n and (len(cuts) > 1 or top_cut != cut_label({})):
        out.append(f"{k} of {n} in cut {top_cut}")
    for dim in group_dims(comparison):
        values = Counter(dict(c.dims).get(dim.cube) for c in cells)
        value, k = values.most_common(1)[0]
        if value is not None and 2 * k >= n:
            out.append(f"{k} of {n} have {dim.cube} = {value}")
    query = comparison.sheet_query or " ".join(
        (comparison.sheet_query_sql or "").split()
    )
    out.append(
        f"Cube computes `{comparison.measure}` as {cube_expr}; the sheet query is "
        f"{query}"
    )
    if comparison.definitions:
        out.append(
            f"Recorded definitions: dashboard {comparison.definitions['dashboard']}; "
            f"Cube {comparison.definitions['cube']}"
        )
    return out


def row_group_cause(n_groups: int) -> str:
    """The cause line a row-level comparison adds: its row groups, or none."""
    return (
        f"{n_groups} row groups on this comparison (see Sort) may explain part of it"
        if n_groups
        else "every row matches on the grain and values, so the 2 definitions or "
        "their filters differ"
    )


def _cell_diffs(
    cfg: ViewConfig,
    comparisons: list[Comparison],
    sides: "Sides",
    cube: Cube,
    older: frozenset[str] = frozenset(),
    checks: dict[str, set[tuple[str, str]]] | None = None,
) -> tuple[list[CellDiff], set[Cell]]:
    """Each comparison's differing cells, with candidate causes.

    A cell `coverage.placed` finds no group in is a formula difference: every
    row in it matched on both sides. So is a cell holding groups whose
    `(cut, key)` is in `checks` under its comparison: the formula check found
    it still differs on matched rows alone. Those cells make the comparison's
    `formula` diff; the rest, holding groups or unplaceable, its `cells` diff.
    A cell that cannot be placed is never a formula difference. A comparison
    in `older` (not compared by this process) composes its older cells even
    when Cube can no longer compile its measure.

    Returns:
        The diffs, and the formula cells, which `_diff_cells` marks so later
        steps read this split instead of placing the cells again.
    """
    out = []
    formula_cells: set[Cell] = set()
    for comparison in comparisons:
        differing = [
            c for c in sides.cells
            if c.comparison == comparison.id and c.verdict in DIFFERING
        ]  # fmt: skip
        if not differing:
            continue
        member = member_name(cfg.view, comparison.measure)
        try:
            compiled = cube.compiled({"measures": [member]}).sql
        except CubeError:
            if comparison.id not in older:
                raise
            expr = "a measure Cube cannot compile today"
        else:
            expr = measure_expression(compiled, cfg.view, comparison.measure)
        checked = (checks or {}).get(comparison.id, set())
        formula: list[Cell] = []
        cells: list[Cell] = []
        matched_only = 0
        for c in differing:
            inside = coverage.placed(_coverage_cell(c), sides.groups, comparison)
            on_matched = bool(inside) and (c.cut, c.key) in checked
            matched_only += on_matched
            (formula if inside == [] or on_matched else cells).append(c)
        formula_cells.update(formula)
        if cells:
            causes = candidate_causes(comparison, cells, comparison.decimals or 0, expr)
            if comparison.rows is not None:
                groups = [g for g in sides.groups if g.comparison_id == comparison.id]
                causes.append(row_group_cause(len(groups)))
            out.append(
                CellDiff(
                    comparison.id,
                    dict(Counter(c.verdict for c in cells)),
                    tuple(causes),
                )
            )
        if formula:
            free = len(formula) - matched_only
            causes = [
                *([f"{free} differing cells hold no unmatched row"] if free else []),
                *(
                    [f"{matched_only} {sort.MATCHED_LABEL} only"]
                    if matched_only
                    else []
                ),
                *candidate_causes(comparison, formula, comparison.decimals or 0, expr),
            ]
            out.append(
                CellDiff(
                    comparison.id,
                    dict(Counter(c.verdict for c in formula)),
                    tuple(causes),
                    kind="formula",
                    matched_only=matched_only,
                )
            )
    return out, formula_cells


def _coverage_cell(c: Cell) -> dict:
    """A cell as `coverage` reads it, the shape `run.json` saves it in."""
    return {"cut": c.cut, "dims": [list(d) for d in c.dims]}


NEVER_COMPARED = "never compared"
ENTRY_CHANGED = "its entry or rebuild check changed"


def composed_results(cfg: ViewConfig, run: RunResult) -> dict[str, latest.Latest]:
    """The results `compare` was composed from, as `stale_comparisons` reads them.

    Built from the run itself, not from `latest/`: a run stopped after
    keeping a newer result, before composing, still holds the older one.
    A comparison the run lacks is left out, so it reads as never compared.
    """
    return {
        c.id: latest.Latest(
            moment=run.moment_of(c.id),
            # The entry is checked first, so today's entry stands in for the
            # one the run compared whenever this fingerprint is read.
            fingerprint=checkpoint_fingerprint(c, run.fingerprints[c.id]),
            entry=run.entries.get(c.id, ""),
            ran_at="",
            data={"fingerprints": {c.id: run.fingerprints[c.id]}},
            fact=run.fact,
        )
        for c in cfg.comparisons
        if c.id in run.fingerprints and c.id not in run.missing
    }


def stale_comparisons(
    cfg: ViewConfig,
    comparisons: list[Comparison],
    results: dict[str, latest.Latest],
    *,
    wh: Warehouse,
    cube: Cube,
    schools: set[str],
    now: datetime,
) -> dict[str, str]:
    """Each confirmed comparison whose latest result is missing or stale, and why.

    A result is stale when its `checkpoint_fingerprint` differs from today's:
    its entry or rebuild check changed, or either side's SQL did (Cube's
    compiled query, or the dashboard's sheet query and the views it reads).
    The fingerprints mask the moment, so a new build alone, or changed data,
    is not stale. A comparison whose SQL cannot be built today, a member Cube
    no longer compiles included, is named with why, and the others are still
    checked. Compiles and expands only; no query bills.
    """
    build = Build(now, now, "now")
    out: dict[str, str] = {}
    for c in comparisons:
        if not c.confirmed:
            continue
        held = results.get(c.id)
        if held is None:
            out[c.id] = NEVER_COMPARED
            continue
        if latest.entry_fingerprint(c) != held.entry:
            out[c.id] = ENTRY_CHANGED
            continue
        try:
            today = side_fingerprints(
                cfg, c, wh=wh, cube=cube, build=build, schools=schools
            )
        except SQL_ERRORS as exc:
            out[c.id] = sql_broken(exc)
            continue
        if checkpoint_fingerprint(c, today) == held.fingerprint:
            continue
        was = held.data.get("fingerprints", {}).get(c.id, {})
        why = [
            text
            for side, text in (
                ("cube", "Cube's SQL changed"),
                ("dashboard", "the dashboard SQL changed"),
            )
            if was.get(side) != today[side]
        ]
        out[c.id] = " and ".join(why) or ENTRY_CHANGED
    return out


def _clauses(comparison: Comparison, groups: list[Group], sides: Sides) -> list[str]:
    if comparison.id not in sides.sql:
        return []
    by_cube = {d.cube: d.dashboard for d in comparison.dims}
    columns = unique(
        name
        for g in groups
        if g.comparison_id == comparison.id
        for column, _ in g.dims
        for name in (column, by_cube.get(column, column))
    )
    if not columns:
        return []
    dash_sql, cube_sql = sides.sql[comparison.id]
    return unique(
        reconcile.clauses_for(columns, dash_sql)
        + reconcile.clauses_for(columns, cube_sql)
    )


def _open_counts(
    comparisons: list[Comparison],
    open_groups: list[Group],
    open_gaps: list[Gap],
    open_cells: list[CellDiff],
) -> tuple[Counter, Counter, Counter]:
    """Open groups, gaps and cell differences per measure."""
    measure_of = {c.id: c.measure for c in comparisons}
    groups = Counter(measure_of.get(g.comparison_id) for g in open_groups)
    gaps = Counter(
        measure
        for g in open_gaps
        for measure in {measure_of.get(c) for c in g.comparisons}
    )
    cells = Counter(measure_of.get(d.comparison_id) for d in open_cells)
    return groups, gaps, cells


def _measures(
    comparisons: list[Comparison],
    cells: list[Cell],
    open_groups: list[Group],
    open_gaps: list[Gap],
    open_cells: list[CellDiff],
) -> list[MeasureResult]:
    """One result per measure: its cell counts, open items and verdict."""
    counts: dict[str, Counter] = {}
    for comparison in comparisons:
        mine = [c for c in cells if c.comparison == comparison.id]
        counts.setdefault(comparison.measure, Counter()).update(c.verdict for c in mine)
    groups, gaps, open_cell_counts = _open_counts(
        comparisons, open_groups, open_gaps, open_cells
    )
    return [
        MeasureResult(
            measure,
            verdict(
                dict(found),
                groups.get(measure, 0),
                gaps.get(measure, 0),
                open_cell_counts.get(measure, 0),
            ),
            dict(found),
            groups.get(measure, 0),
            gaps.get(measure, 0),
            open_cell_counts.get(measure, 0),
        )
        for measure, found in counts.items()
    ]


def _extra_sections(cells: list[Cell]) -> str:
    out = ["## Cells", ""]
    out += [
        f"- {c.comparison} {c.cut} {c.key}: dashboard {c.dashboard}, "
        f"Cube {c.cube} ({c.verdict})"
        for c in cells
    ] or ["None."]
    return "\n".join(out) + "\n"


def _browser_cuts(comparisons: list[Comparison]) -> list[str]:
    """Cuts no rebuild check's REST export covered: parameter cuts, and cuts
    added since.

    A rebuild check written before checks recorded their cuts cannot say which
    it covered, so the comparison is listed to rebuild again.
    """
    out = []
    for comparison in comparisons:
        recorded = comparison.rebuild_check.cuts if comparison.rebuild_check else None
        if recorded is None:
            out.append(
                f"{comparison.id}: cuts unknown (the rebuild check records none); "
                "re-run `rebuild-sheet`"
            )
            continue
        out += [
            f"{comparison.id}: {cut_label(cut)} (no export matched it)"
            for cut in comparison_cuts(comparison)
            if cut_label(cut) not in recorded
        ]
    return out


def _gaps(comparisons: list[Comparison]) -> tuple[list[Gap], list[str]]:
    """Missing cuts and filters across the rebuild checks, one per kind and
    field.

    Also lists each comparison whose rebuild check predates them.
    """
    found: dict[tuple[str, str], dict[str, Any]] = {}
    unknown = []
    for comparison in comparisons:
        proof = comparison.rebuild_check
        if proof is None or proof.missing_cuts is None or proof.missing_filters is None:
            unknown.append(
                f"{comparison.id}: missing cuts and filters unknown (the rebuild "
                "check predates them); re-run `rebuild-sheet`"
            )
            continue
        restricting = set(proof.restricting_filters or [])
        for kind, names in (
            ("cut", proof.missing_cuts),
            ("filter", proof.missing_filters),
        ):
            for name in names:
                entry = found.setdefault(
                    (kind, name),
                    {"sheets": [], "comparisons": [], "restricting": False},
                )
                if comparison.sheet and comparison.sheet not in entry["sheets"]:
                    entry["sheets"].append(comparison.sheet)
                entry["comparisons"].append(comparison.id)
                entry["restricting"] |= kind == "filter" and name in restricting
    gaps = [
        Gap(kind, name, tuple(e["sheets"]), tuple(e["comparisons"]), e["restricting"])
        for (kind, name), e in sorted(found.items())
    ]
    return gaps, unknown


def last_run(cfg: ViewConfig, cache_root: Path) -> dict | None:
    """The view's last readable `run.json` of `cfg.fact`, or None.

    A run saved before runs recorded their fact is no fact's run (`_saved_run`).
    """
    try:
        return _saved_run(cfg, cache_root)[0]
    except Refusal:
        return None


def composed_from(
    data: dict | None,
    comparisons: list[Comparison],
    results: dict[str, latest.Latest],
) -> bool:
    """Whether `data` (`last_run`) was composed from exactly `results`: every
    comparison's moment, entry and SQL fingerprints, and as `missing` the
    comparisons with no result (a skipped one's)."""
    if data is None:
        return False
    held = [c for c in comparisons if c.id in results]
    none = [c.id for c in comparisons if c.id not in results]
    return (data.get("missing") or []) == none and all(
        (data.get("moments") or {}).get(c.id) == results[c.id].moment.to_json()
        and (data.get("entries") or {}).get(c.id) == results[c.id].entry
        and (data.get("fingerprints") or {}).get(c.id)
        == results[c.id].data.get("fingerprints", {}).get(c.id)
        for c in held
    )


def compose_run(
    cfg: ViewConfig,
    comparisons: list[Comparison],
    results_dir: Path,
    *,
    cube: Cube,
    cube_host: str,
    totals: list[str],
    cache_root: Path,
    build: Build,
    folder: Path,
    cost: float,
    skipped: Iterable[Skip] = (),
    compared: Iterable[str] = (),
    echo: bool = True,
) -> RunResult:
    """Compose, print and save `run.json` in `folder` from every confirmed
    comparison's latest result, in config order; `build` and `cost` are the
    folder's, and `skipped` what this process skipped, whose older results
    compose like the rest. Compiles Cube's measure only; no query bills. Only
    the comparisons in `compared` (this process compared them) refuse when
    Cube cannot compile their measure; the rest compose their older cells.
    A result's formula check (`latest.add_formula_check`) files its cells
    only when it checked that very result. `echo` False saves without
    printing.

    Raises:
        Refusal: Two decisions claim one item (`decisions.apply`).
    """
    results = latest.read_all(results_dir, cfg.fact)
    composed = [c for c in comparisons if c.id in results]
    left_out = [c.id for c in comparisons if c.id not in results]
    sides = Sides(moved={f: False for f in cfg.also_facts})
    for c in composed:
        sides.merge(Sides.from_json(results[c.id].data))
    changed = sorted(
        {t for c in composed for t in results[c.id].data.get("changed_dims", [])}
    )

    gaps, gaps_unknown = _gaps(comparisons)
    skipped = list(skipped)
    now = set(compared)
    checks = {
        cid: cells
        for cid, held in results.items()
        if (cells := _formula_cells(held)) is not None
    }
    cell_diffs, formula_cells = _cell_diffs(
        cfg,
        comparisons,
        sides,
        cube,
        frozenset(c.id for c in comparisons) - now,
        checks,
    )
    try:
        applied = decisions.apply(
            cfg.decisions,
            sides.groups,
            sides.fingerprints,
            gaps=gaps,
            cell_diffs=cell_diffs,
        )
    except ValueError as exc:
        raise Refusal(str(exc)) from exc

    clauses = {c.id: _clauses(c, applied.open, sides) for c in comparisons}
    result = RunResult(
        view=cfg.view,
        moment=build,
        cube_host=cube_host,
        fact=cfg.fact,
        measures=_unvalidated(
            _measures(
                comparisons,
                sides.cells,
                applied.open,
                applied.open_gaps,
                applied.open_cells,
            ),
            comparisons,
            left_out,
        ),
        applied=applied,
        live_sources=sorted(sides.live),
        changed_dims=changed,
        scopes=[
            f"{c.id}: {f['member']} is set"
            if f["operator"] == "set"
            else (
                f"{c.id}: {f['member']} {_SCOPE_WORDS[f['operator']]} "
                f"{', '.join(map(str, f['values']))}"
            )
            for c in comparisons
            for f in scope_cube_filters(cfg.view, c)
        ],
        dashboard_filters=[
            f"{c.id}: {dashboard_filter_sql(e)}"
            for c in comparisons
            for e in c.dashboard_filters
        ],
        cost_usd=cost,
        proofs={
            c.id: c.rebuild_check.matched_at for c in comparisons if c.rebuild_check
        },
        browser_cuts=_browser_cuts(comparisons),
        totals=totals,
        reshaped={c.id: reshape_text(c.shelves) for c in comparisons if c.shelves},
        clauses={k: v for k, v in clauses.items() if v},
        fingerprints=sides.fingerprints,
        decisions_fingerprint=decisions.decisions_fingerprint(cfg.decisions),
        gaps_unknown=gaps_unknown,
        diff_cells=_diff_cells(sides, formula_cells),
        cell_sql=sides.cell_sql,
        cell_sql_usd=sides.cell_sql_usd,
        moments={c.id: results[c.id].moment for c in composed},
        entries={c.id: results[c.id].entry for c in composed},
        missing=left_out,
        skipped=[dataclasses.asdict(s) for s in skipped],
    )
    text = report.render_local(result) + "\n" + _extra_sections(sides.cells)
    if echo:
        print(text)
    saved = report.save_local(result, text, root=cache_root)
    checkpoints.write_text(saved.with_name("run.json"), _run_json(result))
    checkpoints.finish(folder)
    if echo:
        print(f"Saved {saved}")
    return result


def _formula_cells(held: latest.Latest) -> set[tuple[str, str]] | None:
    """The cells the result's formula check files as formula, or None when it
    has no check of that very result, read as `sort` reads it to reuse it
    (`sort._stored_check`): a check that cannot be read counts as none."""
    check = sort._stored_check(held)
    return None if check is None else set(check.formula)


def recompose(
    cfg: ViewConfig, cache_root: Path, run: RunResult, run_json: Path, *, cube: Cube
) -> RunResult:
    """Compose the saved run again from the same latest results, quietly.

    For a formula check just kept beside them: the run keeps its moment,
    host, caveats, cost and skips, and compares nothing.

    Raises:
        Refusal: `run_json` is not composed from exactly the latest results,
            so composing would replace the run with another; or two
            decisions claim one item (`decisions.apply`).
    """
    confirmed = [c for c in cfg.comparisons if c.confirmed]
    results_dir = latest.folder(cache_root / cfg.view, cfg.fact)
    if not composed_from(
        json.loads(run_json.read_text()),
        confirmed,
        latest.read_all(results_dir, cfg.fact),
    ):
        # Not `formula.NOT_COMPOSED`: `formula` imports this module.
        raise Refusal("the run is not composed from the latest results")
    return compose_run(
        cfg,
        confirmed,
        results_dir,
        cube=cube,
        cube_host=run.cube_host,
        totals=run.totals,
        cache_root=cache_root,
        build=run.moment,
        folder=run_json.parent,
        cost=run.cost_usd,
        skipped=[Skip(**s) for s in run.skipped],
        compared=(),
        echo=False,
    )


NOT_COMPARED = "not compared yet"


def _unvalidated(
    measures: list[MeasureResult], comparisons: list[Comparison], missing: list[str]
) -> list[MeasureResult]:
    """`measures` with any measure of a comparison not compared yet read as
    `NOT_COMPARED`: its cells are unknown, so it cannot be validated."""
    short = {c.measure for c in comparisons if c.id in missing}
    return [
        dataclasses.replace(m, verdict=NOT_COMPARED) if m.measure in short else m
        for m in measures
    ]


def _diff_cells(sides: Sides, formula: set[Cell]) -> list[dict]:
    """Every cell that neither passes nor is dashboard-filtered, for run.json.

    `kind` names the item holding it: `formula` for a cell in `formula`
    (`_cell_diffs`), else `cells`. A run saved before it reads as `cells`.
    """
    return [
        {
            "comparison": c.comparison,
            "cut": c.cut,
            "key": c.key,
            "dims": [list(d) for d in c.dims],
            "dashboard": c.dashboard,
            "cube": c.cube,
            "n_students": sides.students.get(c.comparison, {}).get(
                (c.cut, tuple(v for _, v in c.dims))
            ),
            "kind": "formula" if c in formula else "cells",
        }
        for c in sides.cells
        if c.verdict not in ("pass", "dashboard_filtered")
    ]


def _run_json(result: RunResult) -> str:
    """`run.json`'s text. A cell difference's `matched_only` is left out at 0,
    so a run no formula check filed a cell in saves as it did before the
    check; `_cell_diff` reads it back as 0."""
    data = dataclasses.asdict(result)
    applied = data["applied"]
    for diff in [*applied["open_cells"], *(d for _, d in applied["quiet_cells"])]:
        if not diff["matched_only"]:
            del diff["matched_only"]
    return json.dumps(data, default=_json_default, indent=1)


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


def _gap(data: dict) -> Gap:
    return Gap(
        **{
            **data,
            "sheets": tuple(data["sheets"]),
            "comparisons": tuple(data["comparisons"]),
        }
    )


def _cell_diff(data: dict) -> CellDiff:
    """A run saved before formula differences split off holds `cells` only."""
    return CellDiff(
        **{**data, "causes": tuple(data["causes"]), "kind": data.get("kind", "cells")}
    )


def _run_from_json(data: dict) -> RunResult:
    applied = data["applied"]
    return RunResult(
        view=data["view"],
        moment=Build.from_json(data["moment"]),
        measures=[MeasureResult(**m) for m in data["measures"]],
        applied=Applied(
            open=[group_from_json(g) for g in applied["open"]],
            quiet=[(Decision(**d), group_from_json(g)) for d, g in applied["quiet"]],
            reconfirm=[Decision(**d) for d in applied["reconfirm"]],
            no_longer_needed=[Decision(**d) for d in applied["no_longer_needed"]],
            partly_stale=[
                (Decision(**d), list(v)) for d, v in applied.get("partly_stale", [])
            ],
            open_gaps=[_gap(g) for g in applied.get("open_gaps", [])],
            open_cells=[_cell_diff(d) for d in applied.get("open_cells", [])],
            quiet_cells=[
                (Decision(**d), _cell_diff(c))
                for d, c in applied.get("quiet_cells", [])
            ],
            quiet_gaps=[
                (Decision(**d), _gap(g)) for d, g in applied.get("quiet_gaps", [])
            ],
            causes=[Decision(**d) for d in applied.get("causes", [])],
        ),
        live_sources=data["live_sources"],
        changed_dims=data["changed_dims"],
        scopes=data["scopes"],
        cost_usd=data["cost_usd"],
        proofs=data["proofs"],
        browser_cuts=data["browser_cuts"],
        totals=data.get("totals", []),
        reshaped=data.get("reshaped", {}),
        clauses=data["clauses"],
        fingerprints=data.get("fingerprints", {}),
        decisions_fingerprint=data.get("decisions_fingerprint", ""),
        gaps_unknown=data.get("gaps_unknown", []),
        dashboard_filters=data.get("dashboard_filters", []),
        diff_cells=data.get("diff_cells", []),
        cell_sql=data.get("cell_sql", {}),
        cell_sql_usd=data.get("cell_sql_usd", {}),
        cube_host=data.get("cube_host", ""),
        fact=data.get("fact", ""),
        moments={k: Build.from_json(v) for k, v in data.get("moments", {}).items()},
        entries=data.get("entries", {}),
        missing=data.get("missing", []),
        skipped=data.get("skipped", []),
    )


# What `reapply` rebuilds the run's full findings from; a run saved without
# any of them predates re-applying.
_REAPPLY_KEYS = (
    "open",
    "quiet",
    "open_gaps",
    "quiet_gaps",
    "open_cells",
    "quiet_cells",
)


def _saved_run(cfg: ViewConfig, cache_root: Path) -> tuple[dict, Path]:
    """The latest `run.json` of `cfg.fact` as JSON, and its path.

    The latest run is the `run.json` of the fact the command was given
    (`--fact-dataset` names a dev build's) written last, whatever moment it
    read; of 2 written at once, the later-named folder's. A run saved before
    runs recorded their fact is no fact's run: it never stands in for one.

    Raises:
        Refusal: The view has no saved run of `cfg.fact`; the message names
            the fact of the latest run there is, if any, else says the saved
            run is an older validator's.
    """
    saved = sorted(
        (cache_root / cfg.view).glob("*/run.json"),
        key=lambda p: (p.stat().st_mtime, p),
        reverse=True,
    )
    other, legacy = None, None
    for path in saved:
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        fact = data.get("fact") if isinstance(data, dict) else None
        if not fact:
            legacy = legacy or path
        elif fact == cfg.fact:
            return data, path
        else:
            other = other or fact
    if other:
        raise Refusal(
            f"{cfg.view}: no saved run of {cfg.fact}; the latest run read "
            f"{other}, which this command does not use. `compare` it, or pass "
            "--fact-dataset to read that build"
        )
    if legacy:
        raise _older(cfg, legacy)
    raise Refusal(f"{cfg.view}: no saved run; `compare` it first")


def _older(cfg: ViewConfig, run_json: Path) -> Refusal:
    return Refusal(
        f"{cfg.view}: the saved run {run_json} was written by an older "
        "validator; `compare` it again"
    )


def _require_nulls(data: dict) -> None:
    """Refuse a run saved before groups recorded which values were NULL.

    Such a run reads a NULL group-by value as empty text, so an explanation
    finds none of that group's rows: the run, not the explanation, is at fault.
    """
    applied = data.get("applied") or {}
    groups = [*applied.get("open", []), *(g for _, g in applied.get("quiet", []))]
    if any("nulls" not in g for g in groups):
        moment = (data.get("moment") or {}).get("start", "<moment>")
        raise Refusal(
            "this run predates NULL-aware groups; run again "
            f"(`compare --moment {moment}`)"
        )


def _reapplicable(cfg: ViewConfig, cache_root: Path) -> tuple[RunResult, Path]:
    """The latest saved run, refused when it lacks what re-applying reads."""
    data, run_json = _saved_run(cfg, cache_root)
    if "fingerprints" not in data or any(
        k not in data.get("applied", {}) for k in _REAPPLY_KEYS
    ):
        raise _older(cfg, run_json)
    try:
        return _run_from_json(data), run_json
    except (KeyError, TypeError) as exc:
        raise _older(cfg, run_json) from exc


def _apply_saved(cfg: ViewConfig, saved: RunResult) -> Applied:
    """Sort everything the saved run found by the file's decisions."""
    was = saved.applied
    try:
        return decisions.apply(
            cfg.decisions,
            was.open + [g for _, g in was.quiet],
            saved.fingerprints,
            gaps=was.open_gaps + [g for _, g in was.quiet_gaps],
            cell_diffs=was.open_cells + [d for _, d in was.quiet_cells],
        )
    except ValueError as exc:
        raise Refusal(str(exc)) from exc


def check_claims(cfg: ViewConfig, cache_root: Path) -> None:
    """Refuse decisions that would claim one item twice in the saved run.

    Called before decisions are written, since a file whose decisions overlap
    makes both `compare` and `reapply` refuse. With no saved run this validator
    can re-apply to, there is nothing to check against and nothing refuses.

    Raises:
        Refusal: Two decisions claim the same group, gap or formula
            difference, or a cause decision disagrees with the `group`
            decision closing a group its explanation covers (`sort.check_closed`).
    """
    try:
        saved, run_json = _reapplicable(cfg, cache_root)
    except Refusal:
        return
    applied = _apply_saved(cfg, saved)
    _check_closed(cfg, dataclasses.replace(saved, applied=applied), run_json)


def _check_closed(cfg: ViewConfig, run: RunResult, run_json: Path) -> None:
    try:
        sort.check_closed(run, run_json, cfg.decisions)
    except Refusal as exc:
        raise Refusal(f"{cfg.view}: {exc}") from exc


def reapply(cfg: ViewConfig, cache_root: Path) -> RunResult:
    """Apply the file's decisions to the view's latest saved run, offline.

    Recording a decision changes no data, so the saved run's groups, gaps,
    cell differences and SQL fingerprints are re-sorted by the current
    decisions as `compare` would sort them; a decision whose fingerprints differ
    from the run's still lands in `reconfirm`. Rewrites `run.json` and
    `result.md` and runs no query. The verdict is read again from the cells
    and the open counts. Clauses stay as the run computed them, over the
    groups open then, so a group a deleted decision reopens may show no clause
    until the next `compare`.

    Raises:
        Refusal: The view has no saved run, the run predates what re-applying
            needs, two decisions claim the same item, or a cause decision
            disagrees with the `group` decision closing a group its explanation
            covers (`sort.check_closed`). Nothing is rewritten.
    """
    saved, run_json = _reapplicable(cfg, cache_root)
    applied = _apply_saved(cfg, saved)
    _check_closed(cfg, dataclasses.replace(saved, applied=applied), run_json)

    groups, gaps, cells = _open_counts(
        cfg.comparisons, applied.open, applied.open_gaps, applied.open_cells
    )
    result = dataclasses.replace(
        saved,
        applied=applied,
        measures=_unvalidated(
            [
                dataclasses.replace(
                    m,
                    verdict=verdict(
                        m.cells,
                        groups.get(m.measure, 0),
                        gaps.get(m.measure, 0),
                        cells.get(m.measure, 0),
                    ),
                    open_groups=groups.get(m.measure, 0),
                    open_gaps=gaps.get(m.measure, 0),
                    open_cells=cells.get(m.measure, 0),
                )
                for m in saved.measures
            ],
            cfg.comparisons,
            saved.missing,
        ),
        decisions_fingerprint=decisions.decisions_fingerprint(cfg.decisions),
    )
    # The cells section needs every cell the run held; decisions
    # never change them, so the saved report's copy is kept.
    old = run_json.with_name("result.md")
    old_text = old.read_text() if old.exists() else ""
    at = old_text.find("\n## Cells\n")
    tail = old_text[at + 1 :] if at != -1 else ""
    text = report.render_local(result) + ("\n" + tail if tail else "")
    checkpoints.write_text(
        report.save_local(result, text, root=cache_root).with_name("run.json"),
        _run_json(result),
    )
    return result


def latest_run(cfg: ViewConfig, cache_root: Path) -> tuple[RunResult, Path]:
    """Return the view's latest saved run and the `run.json` it came from.

    The latest run is the `run.json` of `cfg.fact` written last, whatever
    moment it read (`_saved_run`).

    Raises:
        Refusal: The view has no saved run of `cfg.fact`, its saved run is
            in a shape this validator cannot read or predates NULL-aware
            groups, or its decisions changed since the run (a run saved
            before runs recorded them counts as changed).
    """
    data, run_json = _saved_run(cfg, cache_root)
    try:
        run_result = _run_from_json(data)
    except (KeyError, TypeError) as exc:
        raise _older(cfg, run_json) from exc
    _require_nulls(data)
    if run_result.decisions_fingerprint != decisions.decisions_fingerprint(
        cfg.decisions
    ):
        raise Refusal(
            f"{cfg.view}: the decisions changed since the saved run "
            f"{run_json}; `reapply` it, or `compare` it again with --all"
        )
    return run_result, run_json
