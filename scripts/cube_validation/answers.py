"""The owner's questions out, and the decisions that answer them back in.

Out: pick the example cell an owner checks by hand and pin each side's SQL to
it. The owner pastes these queries into the BigQuery console under their own
access, and the texts go into a GitHub issue, so the example is never one
person's row: every dimension is a reviewed column and at least `MASK_BELOW`
students stand behind it.

In: turn an approved triage batch, or the owner's answers comment, into
decisions. Their reasons are committed to git, so a note naming a person by
email or number is refused. This module runs no queries and writes no files;
it selects and formats saved data.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .config import _TASK, CALLS, Decision, ViewConfig, mask_digits
from .cube_client import _literal
from .decisions import cause_state
from .report import (
    _SEPARATED_DIGITS,
    MASK_BELOW,
    CauseAsk,
    RunResult,
    _is_identifier,
    _questions,
    _safe_reason,
    defined_comparisons,
    definition_text,
    question_parts,
    question_reason,
    without_sql,
)

# BigQuery keeps table history this long, so an as-of query stops working then.
TIME_TRAVEL_DAYS = 7

NO_REPRODUCE = (
    "no count query yet: the proof has no `-- reproduce {bucket}:` block for it"
)


@dataclass(frozen=True)
class ProofSource:
    """Where a view's stored proofs live, for an owner to reproduce a cause.

    `view_file` is the validation file as a command names it (repo-relative
    when known); `base` its directory, which proof paths are relative to;
    `blob` the branch URL of that directory, or None outside a GitHub clone.
    """

    view_file: str
    base: Path
    blob: str | None = None


# A hand check whose pinned SQL is longer on either side leaves it out: too
# long to paste into the BigQuery console, or to keep in the review file.
MAX_POSTED_SQL = 20_000
NO_EXAMPLE = (
    "no group cell with 10+ students differs; find an example under your own access"
)


@dataclass(frozen=True)
class HandCheck:
    comparison: str
    cut: str
    dims: tuple[tuple[str, str], ...]
    dashboard: float | None
    cube: float | None
    dashboard_sql: str
    cube_sql: str
    dashboard_usd: float
    cube_usd: float
    expires: datetime
    expired: bool
    # Where the owner reads the dashboard's number: the comparison's sheet, and
    # every filter to set there (the defaults with the cut's own values).
    workbook: str | None = None
    sheet: str | None = None
    filters: dict[str, Any] = field(default_factory=dict)
    # A cause's example that also holds other causes' rows.
    mixed: bool = False
    # The fewest students the cause surely has in the cell (`cell_causes`).
    cause_students: int | None = None


# The side whose rows a group's bucket counts, in `RunResult.cell_rows`.
_ROWS_SIDE = {
    "cube_only": "c",
    "dashboard_filtered": "c",
    "value_differs": "c",
    "dashboard_only": "d",
}


def cell_causes(
    run: RunResult,
    cfg: ViewConfig,
    comparison: str,
    items: list[dict],
    recorded: list[dict] | None = None,
) -> list[tuple[dict, dict[str, int]]]:
    """Each differing cell of a comparison, with the causes its rows carry and
    how many students each has in it.

    `recorded` is the triage's `cause_students` for the comparison: the
    proofs' own distinct-student counts per cause, cell and cut, used as
    they are. A triage saved before them gives None, and the count is then
    the floor below.

    A cell's rows lie in the groups whose columns agree with its dims and cut
    (`confirm._in_cut`, `confirm._in_cells`, as `--cells` links them); each
    group carries its triage item's causes (`triage.cause_key`), and a group
    with none carries `""`.

    A cause's students in a cell are not recorded: a group's `n_students`
    covers all its causes and every cut. So the count is a floor: the most
    students of one group that carries only that cause, splits by every one
    of the cell's dims with the cell's values, and has all its rows in the
    cell's cut (the run's per-cut sums, `RunResult.cell_rows`). A cause with
    no such group counts 0. Never a sum, which could count a student twice.

    Returns:
        `[(cell, {cause: students})]` in `run.diff_cells` order.
    """
    from . import compare, confirm, pipeline
    from . import triage as triage_mod

    spec = next((c for c in cfg.comparisons if c.id == comparison), None)
    single_cut = spec is not None and len(pipeline._cuts(spec)) == 1
    entries: dict[tuple, list[dict]] = {}
    for e in run.cell_rows.get(comparison) or []:
        key = (e["bucket"], frozenset((k, v) for k, v in e["dims"]))
        entries.setdefault(key, []).append(e)

    def whole_in(g, cell) -> bool:
        """Whether every row of `g` lies in `cell`: its dims and its cut."""
        mine = {
            k: (None if k in g.nulls else v)
            for k, v in g.dims
            if not k.startswith(compare.DASH_PREFIX) and k != "dashboard_filter"
        }
        for column, value in cell["dims"]:
            if column not in mine or pipeline._key(mine[column]) != pipeline._key(
                value
            ):
                return False
        side = _ROWS_SIDE.get(g.bucket)
        found = entries.get((g.bucket, frozenset(mine.items())), [])
        if side is None or len(found) != 1:
            return False
        (e,) = found
        cuts = e.get("cuts") or {}
        if not cuts:
            return single_cut and e[side]["rows"] > 0
        held = cuts.get(cell.get("cut", "{}"))
        return held is not None and 0 < held[side]["rows"] == e[side]["rows"]

    by_key = {
        item.get("key"): frozenset(
            triage_mod.cause_key(c.get("side", ""), c.get("label") or "")
            for c in item.get("cause") or []
        )
        or frozenset({""})
        for item in items
        if item.get("kind") == "group"
    }
    groups = [
        (key, g)
        for key, g in triage_mod._groups_by_key(run).items()
        if g.comparison_id == comparison
    ]
    counted: dict[tuple, dict[str, int]] = {}
    for e in recorded or []:
        key = (e["cut"], tuple(pipeline._key(v) for _, v in e["dims"]))
        counted.setdefault(key, {})[e["cause"]] = int(e["n"])
    out = []
    for cell in run.diff_cells:
        if cell["comparison"] != comparison:
            continue
        held: dict[str, int] = {}
        if recorded is not None:
            dims = {k: v for k, v in cell["dims"]}
            names = [p.cube for p in pipeline.group_dims(spec)] if spec else []
            key = (
                cell.get("cut", "{}"),
                tuple(pipeline._key(dims.get(n)) for n in names),
            )
            # Only a cell whose dims are the counted columns has a count.
            if set(dims) == set(names):
                held = dict(counted.get(key, {}))
        for key, g in groups:
            if not (
                confirm._in_cut(g, spec, cell.get("cut", "{}"))
                and any(confirm._in_cells(g, cell))
            ):
                continue
            causes = by_key.get(key, frozenset({""}))
            for cause in causes:
                held.setdefault(cause, 0)
            if recorded is None and len(causes) == 1 and whole_in(g, cell):
                (cause,) = causes
                held[cause] = max(held[cause], g.n_students)
        out.append((cell, held))
    return out


def example_cell(
    run: RunResult,
    comparison: str,
    cause: str | None = None,
    cells: list | None = None,
) -> dict | None:
    """Pick the differing cell an owner can check without seeing a person.

    Args:
        run: The saved run.
        comparison: The comparison id.
        cause: A cause question's cause (`triage.cause_key`): the cell must
            hold `MASK_BELOW` or more of its students (`cell_causes`), so the
            question's words cannot single one out; the most wins.
        cells: `cell_causes` for the comparison; without it, `cause` is
            not used.

    Returns:
        The cell with the largest absolute difference whose dims are all
        reviewed columns and whose `n_students` is at least `MASK_BELOW`; ties
        go to the lowest `key`. With `cause`, the cell where the cause holds
        the most students, then the largest difference, with
        `cause_students` and `mixed` (other causes' rows in it too). None
        when no cell qualifies.
    """
    ok = [
        c
        for c in run.diff_cells
        if c["comparison"] == comparison
        and not any(_is_identifier(column) for column, _ in c["dims"])
        and c["n_students"] is not None
        and c["n_students"] >= MASK_BELOW
        and c["dashboard"] is not None
        and c["cube"] is not None
    ]
    if cause is not None and cells is not None:
        held = {id(cell): causes for cell, causes in cells}
        sure = [
            (held[id(c)][cause], c)
            for c in ok
            if held.get(id(c), {}).get(cause, 0) >= MASK_BELOW
        ]
        if not sure:
            return None
        students, best = min(
            sure,
            key=lambda sc: (
                -sc[0],
                -abs(sc[1]["dashboard"] - sc[1]["cube"]),
                sc[1]["key"],
            ),
        )
        return {
            **best,
            "mixed": len(held[id(best)]) > 1,
            "cause_students": students,
        }
    if not ok:
        return None
    best = min(ok, key=lambda c: (-abs(c["dashboard"] - c["cube"]), c["key"]))
    return {**best, "mixed": False, "cause_students": None}


def _predicate(column: str, key: str) -> str:
    """Match a column against the text `pipeline._key` made of its value.

    `_key` writes NULL as '', numbers as plain decimals and booleans as
    True/False, so a bare `column = '7'` fails on a number and `= ''` misses a
    NULL. A date or text key compares as a string literal, which BigQuery
    coerces against a DATE or TIMESTAMP column.
    """
    if key == "":
        return f"{column} IS NULL"
    if key.lower() in ("true", "false"):
        return f"LOWER(CAST({column} AS STRING)) = {_literal(key.lower())}"
    try:
        number = Decimal(key)
    except InvalidOperation:
        number = None
    if number is not None and number.is_finite():
        return f"SAFE_CAST({column} AS NUMERIC) = {format(number.normalize(), 'f')}"
    return f"{column} = {_literal(key)}"


def _pinned(sql: str, pairs: list[tuple[str, str]]) -> str:
    """Wrap `sql` to the cell; unchanged for a total cell with no dims."""
    if not pairs:
        return sql
    where = " AND ".join(_predicate(name, value) for name, value in pairs)
    # trunk-ignore(bandit/B608): names come from validated config and values are literal-escaped
    return f"SELECT * FROM (\n{sql}\n) WHERE {where}"


def hand_check(
    run: RunResult,
    cfg: ViewConfig,
    comparison: str,
    now: datetime,
    cause: str | None = None,
    cells: list | None = None,
) -> HandCheck | None:
    """Wrap each side's saved as-of SQL to return just the example cell.

    The Cube side outputs Cube member names; the dashboard side outputs the
    dashboard column names, which `cfg` maps from the member names.

    Args:
        run: The saved run.
        cfg: The view's config, for the dashboard column names.
        comparison: The comparison id.
        now: The current time, to decide whether the as-of SQL still runs.
        cause: For a cause question, its cause; see `example_cell`.
        cells: `cell_causes` for the comparison, with `cause`.

    Returns:
        None when there is no example cell, no saved SQL or `cell_sql_usd`
        entry for its cut, or a dim the comparison does not map.
    """
    cell = example_cell(run, comparison, cause, cells)
    cmp = next((c for c in cfg.comparisons if c.id == comparison), None)
    sql = run.cell_sql.get(comparison, {}).get(cell["cut"]) if cell else None
    usd = run.cell_sql_usd.get(comparison, {}).get(cell["cut"]) if cell else None
    if not (cell and cmp and sql and usd):
        return None
    names = {d.cube: d.dashboard for d in cmp.dims}
    if any(member not in names for member, _ in cell["dims"]):
        return None
    cube_pairs = [(member, value) for member, value in cell["dims"]]
    dash_pairs = [(names[member], value) for member, value in cell["dims"]]
    expires = run.moment.start + timedelta(days=TIME_TRAVEL_DAYS)
    # The cut is `pipeline.cut_label` JSON; the round trip writes a YAML date
    # default as the text the issue's JSON block can carry.
    filters = json.loads(
        json.dumps({**cmp.defaults, **json.loads(cell["cut"])}, default=str)
    )
    return HandCheck(
        comparison=comparison,
        cut=cell["cut"],
        dims=tuple(cube_pairs),
        dashboard=cell["dashboard"],
        cube=cell["cube"],
        dashboard_sql=_pinned(sql[0], dash_pairs),
        cube_sql=_pinned(sql[1], cube_pairs),
        dashboard_usd=usd[0],
        cube_usd=usd[1],
        expires=expires,
        expired=now >= expires,
        workbook=cmp.workbook,
        sheet=cmp.sheet,
        filters=filters,
        mixed=cell["mixed"],
        cause_students=cell["cause_students"],
    )


def _covers(d: Decision, stub: dict) -> bool:
    """True when a triage item's stub is the item `d` covers, by its key fields.

    A cause decision names no item; the triage marks what it decides.
    """
    if d.cause:
        return False
    if d.missing_cut or d.missing_filter:
        return (d.missing_cut, d.missing_filter) == (
            stub.get("missing_cut", ""),
            stub.get("missing_filter", ""),
        )
    if stub.get("comparison") != d.comparison:
        return False
    if d.cells:
        return stub.get("cells") is True
    group = stub.get("group") or {}
    return group.get("column") == (d.group.get("column") or "") and bool(
        {str(v) for v in group.get("values", [])}
        & {str(v) for v in d.group.get("values", [])}
    )


def _cause_evidence(asks: list[tuple[str, CauseAsk]]) -> list[str]:
    """A cause question's evidence: its words, each part's counts, the leads.

    The counts are the bullet's own, each comparison's share of its groups'
    rows, so the issue never shows 2 totals whose difference is another
    cause's. The leads name the model docs on each comparison, never a member
    description.
    """
    d = asks[0][1].decision
    return [
        f"cause ({d.cause.get('side')} side): {d.cause.get('label')}",
        *dict.fromkeys(a.lead for _, a in asks if a.lead),
    ]


def _shown_number(x: float | None) -> str | None:
    """Mask a whole number under `MASK_BELOW`, whatever the measure is called.

    A measure's name does not say whether it counts people, so any whole value
    under 10 reads `<10`; a rate or other fraction prints as it is.
    """
    if x is None:
        return None
    if float(x).is_integer() and x < MASK_BELOW:
        return "<10"
    return f"{x:g}"


def _check_json(view: str, check: HandCheck) -> dict:
    """A hand check as JSON, its two numbers masked like the issue's counts.

    Two whole numbers that differ by under 10 both read `<masked>`: their
    difference would post a small count of the cell's students.
    """
    dashboard, cube = _shown_number(check.dashboard), _shown_number(check.cube)
    d, c = check.dashboard, check.cube
    if (
        d is not None
        and c is not None
        and float(d).is_integer()
        and float(c).is_integer()
        and 0 < abs(d - c) < MASK_BELOW
    ):
        dashboard = cube = "<masked>"
    return {
        "view": view,
        **asdict(check),
        "dims": [list(pair) for pair in check.dims],
        "dashboard": dashboard,
        "cube": cube,
        "expires": check.expires.isoformat(),
    }


def _cube_query(cfg: ViewConfig, check: HandCheck) -> dict:
    """The example cell as a Cube `load` query: its cut, with its dims pinned."""
    from . import pipeline

    comparison = next(c for c in cfg.comparisons if c.id == check.comparison)
    query = pipeline.cell_query(cfg.view, comparison, json.loads(check.cut or "{}"))
    query["filters"] = query["filters"] + [
        {
            "member": pipeline._member(cfg.view, member),
            "operator": "equals",
            "values": [value],
        }
        for member, value in check.dims
    ]
    return query


def reproduce_json(
    view: str,
    ask: CauseAsk,
    run: RunResult,
    cfg: ViewConfig,
    source: ProofSource | None,
    now: datetime,
    cells: list | None = None,
) -> dict:
    """How an owner reproduces one comparison's part of a cause question.

    `cells` is `cell_causes` for the comparison: the example cell is then one
    holding this cause's rows (`example_cell`).

    Returns:
        `comparison`, `cube` (the example cell as a `load` query and where to
        read the dashboard's, or None without an example cell), and `proofs`:
        per stored proof and cause bucket, its `reproduce` query on today's
        tables (None without one), the `confirm` command that re-proves it
        at the run's moment until `expires`, the `after` commands once that
        has passed, and the proof file's `path` and branch `url`.
    """
    from . import confirm

    cid = ask.decision.comparison
    check = hand_check(run, cfg, cid, now, _ask_cause(ask), cells)
    cube = None
    if check:
        # The hand check carries the pinned SQL; this is where to read the cell.
        where = _check_json(view, check)
        for key in ("dashboard_sql", "cube_sql", "dashboard_usd", "cube_usd"):
            where.pop(key)
        cube = {"query": _cube_query(cfg, check), "dashboard": where}
    file = source.view_file if source else f"<{view} validation file>"
    proofs = []
    for path, bucket in ask.proofs:
        stored = (source.base / path) if source else None
        try:
            proof = confirm.read_proof(stored) if stored else None
        except (OSError, confirm.pipeline.Refusal):
            proof = None
        proofs.append(
            {
                "bucket": bucket,
                "reproduce": _checked_reproduce(cfg, proof, bucket),
                "confirm": (
                    f"triage confirm {file} --comparison "
                    f"{proof.comparison if proof else cid} --bucket "
                    f"{proof.bucket if proof else '<bucket>'}"
                ),
                "after": [f"run {file}", f"triage {file}"],
                "expires": (
                    run.moment.start + timedelta(days=TIME_TRAVEL_DAYS)
                ).isoformat(),
                "path": path,
                "url": f"{source.blob}/{path}" if source and source.blob else None,
            }
        )
    return {"view": view, "comparison": cid, "cube": cube, "proofs": proofs}


def _checked_reproduce(cfg: ViewConfig, proof, bucket: str) -> str | None:
    """A proof's reproduce query for one bucket, checked again before it posts.

    `triage confirm` checks it, but the block is comment lines, which a
    proof's fingerprint ignores: an edit after confirm would post unchecked.
    A query that fails the check is left out, as if the proof had none.
    """
    from . import confirm

    sql = proof.reproduce.get(bucket) if proof else None
    comparison = next(
        (c for c in cfg.comparisons if proof and c.id == proof.comparison), None
    )
    if sql is None or comparison is None:
        return None
    try:
        confirm.check_reproduce(
            sql, confirm.grain_names(comparison), confirm.identifying(comparison)
        )
    except confirm.pipeline.Refusal:
        return None
    return sql


def _ask_cause(ask: CauseAsk) -> str:
    """A cause question's cause, as `cell_causes` names it."""
    from . import triage as triage_mod

    cause = ask.decision.cause
    return triage_mod.cause_key(cause.get("side", ""), cause.get("label") or "")


def _rank(check: HandCheck) -> tuple:
    """Order a cause's examples: the most of its students, then the widest gap."""
    gap = abs((check.dashboard or 0) - (check.cube or 0))
    return (-(check.cause_students or 0), -gap, check.comparison)


def merged_reproduce(
    parts: list[dict], examples: set[tuple[str, str]] | None = None
) -> dict:
    """A cause question's `reproduce_json` parts, each thing said once.

    Returns:
        `queries`: each distinct count query, as `bucket` and `sql`. `proofs`:
        per proof file and cause bucket, `bucket`, `query` (its index in
        `queries`, None without one), `path` (relative to the validation
        file's directory) and `confirm` (the commands that re-prove it, which
        the posted JSON leaves out). `blob`: the branch link `<blob>/<path>`
        opens a proof file at, or None. `cube`: per
        comparison with an example cell (only those in `examples`, as
        `(view, comparison)`, when given), its `view`, `comparison` and
        `query`; the question's hand check for that comparison says where to
        read the dashboard's number. `expires`, and `after` (the commands once
        it has passed, per validation file).
    """
    queries: list[dict] = []
    proofs: dict[tuple, dict] = {}
    cube, after, expires, blob = [], [], None, None
    for part in parts:
        shown = examples is None or (part["view"], part["comparison"]) in examples
        if part["cube"] and shown:
            cube.append(
                {
                    "view": part["view"],
                    "comparison": part["comparison"],
                    "query": part["cube"]["query"],
                }
            )
        for p in part["proofs"]:
            query = None
            if p["reproduce"]:
                entry = {"bucket": p["bucket"], "sql": p["reproduce"]}
                if entry not in queries:
                    queries.append(entry)
                query = queries.index(entry)
            if p["url"]:
                blob = p["url"][: -len(p["path"]) - 1]
            merged = proofs.setdefault(
                (p["path"], p["bucket"]),
                {
                    "bucket": p["bucket"],
                    "query": query,
                    "path": p["path"],
                    "confirm": [],
                },
            )
            if p["confirm"] not in merged["confirm"]:
                merged["confirm"].append(p["confirm"])
            after += [a for a in p["after"] if a not in after]
            expires = min(expires or p["expires"], p["expires"])
    return {
        "queries": queries,
        "proofs": list(proofs.values()),
        "blob": blob,
        "cube": cube,
        "expires": expires,
        "after": after,
    }


def questions_json(
    runs: list[RunResult],
    configs: list[ViewConfig],
    definitions: dict,
    triage: dict[str, dict],
    now: datetime,
    causes: dict[str, list[CauseAsk]] | None = None,
    sources: dict[str, ProofSource] | None = None,
) -> list[dict]:
    """List the review issue's questions for the owner's Claude session.

    Every string is text the issue's markdown shows, masked the same way:
    counts, the reason and definitions come from `report`, and triage evidence
    is scrubbed like the reason. A triage item's `stub` holds real values, so
    it is read here only to match items to decisions and never copied.

    Args:
        runs: The runs the issue renders.
        configs: Their views' configs, for each hand check's column names.
        definitions: Per view, per comparison id, `dashboard` and `cube` text.
        triage: Per view, its `triage.json`; a view without one has no
            evidence.
        now: The current time, to say whether the pinned SQL still runs.
        causes: Per view, the owner's cause questions (`triage.cause_asks`).
        sources: Per view, where its stored proofs live, for a cause
            question's `reproduce` block.

    Returns:
        One dict per question in the issue's order: `id` (`Q1`, ...),
        `reason`, `decisions` (ids), `views`, `definitions` (`dashboard` and
        `cube`, one `<comparison> in <view>: <text>` line each), `evidence`,
        `counts` (the masked parts of its bullet), `hand_checks` (one per
        comparison with an example cell, and per view 1 `none` entry listing
        the `comparisons` without one, to find an example locally; a cause
        question, one rule, has 1 example across its comparisons, or the
        `none` entries), and the
        earliest `moment` among its views with when its pinned SQL `expires`
        and whether it has `expired`; a cause question also has `reproduce`
        (`merged_reproduce` over the comparisons it covers).
    """
    by_run = {r.view: r for r in runs}
    by_cfg = {c.view: c for c in configs}
    held: dict[tuple[str, str], list] = {}

    def cells_of(view: str, cid: str) -> list:
        """`cell_causes` of a comparison, worked out once per review."""
        if (view, cid) not in held:
            loaded = triage.get(view, {})
            recorded = (
                loaded["cause_students"].get(cid, [])
                if "cause_students" in loaded
                else None
            )
            held[view, cid] = cell_causes(
                by_run[view], by_cfg[view], cid, loaded.get("items", []), recorded
            )
        return held[view, cid]

    out = []
    for n, q in enumerate(_questions(runs, causes), start=1):
        views = list(dict.fromkeys(view for view, _ in q["decisions"]))

        defs: dict[str, list[str]] = {"dashboard": [], "cube": []}
        for view in views:
            shown = defined_comparisons([q], view)
            for cid, sides in sorted(definitions.get(view, {}).items()):
                if cid in shown:
                    for side in defs:
                        defs[side].append(
                            f"`{cid}` in `{view}`: {definition_text(sides[side])}"
                        )

        items = [
            item
            for view, d in q["decisions"]
            for item in triage.get(view, {}).get("items", [])
            if _covers(d, item.get("stub") or {})
        ]
        lines = [line for item in items for line in item.get("evidence", [])]
        if "asks" in q:
            lines = _cause_evidence(q["asks"])
        evidence = list(
            dict.fromkeys(_safe_reason(line, q["hidden"]) for line in lines)
        )

        # A cause question's example holds that cause's rows.
        asked = {
            (view, ask.decision.comparison): _ask_cause(ask)
            for view, ask in q.get("asks", [])
        }
        found, none = [], {}
        for view, cid, _ in q["comparisons"]:
            cfg = by_cfg.get(view)
            cause = asked.get((view, cid))
            check = (
                hand_check(
                    by_run[view],
                    cfg,
                    cid,
                    now,
                    cause,
                    cells_of(view, cid) if cause else None,
                )
                if cfg
                else None
            )
            if check:
                found.append((view, check))
            else:
                none.setdefault(view, []).append(cid)
        if asked and found:
            # One rule asked once: one example, the cell holding the cause's
            # rows alone if any comparison has one, then the widest gap.
            found = [min(found, key=lambda vc: _rank(vc[1]))]
            none = {}
        checks = [_check_json(view, check) for view, check in found]
        checks = [
            without_sql(c)
            if max(len(c["dashboard_sql"]), len(c["cube_sql"])) > MAX_POSTED_SQL
            else c
            for c in checks
        ]
        checks += [
            {"none": NO_EXAMPLE, "view": view, "comparisons": cids}
            for view, cids in none.items()
        ]

        moment = min((by_run[v].moment for v in views), key=lambda m: m.start)
        expires = moment.start + timedelta(days=TIME_TRAVEL_DAYS)
        extra = {}
        if "asks" in q:
            extra["reproduce"] = merged_reproduce(
                [
                    reproduce_json(
                        view,
                        ask,
                        by_run[view],
                        by_cfg[view],
                        (sources or {}).get(view),
                        now,
                        cells_of(view, ask.decision.comparison),
                    )
                    for view, ask in q["asks"]
                    if view in by_cfg
                ],
                {(c["view"], c["comparison"]) for c in checks if "none" not in c},
            )
        out.append(
            {
                "id": f"Q{n}",
                "reason": question_reason(q),
                "decisions": [d.id for _, d in q["decisions"]],
                "views": views,
                "definitions": defs,
                "evidence": evidence,
                "counts": question_parts(q),
                "hand_checks": checks,
                "moment": {
                    "start": moment.start.isoformat(),
                    "end": moment.end.isoformat(),
                    "job_id": moment.job_id,
                },
                "expires": expires.isoformat(),
                "expired": now >= expires,
                **extra,
            }
        )
    return out


# --- decisions in ------------------------------------------------------------


class AnswerError(Exception):
    """An approved batch or an answers comment cannot be written as decisions.

    Raised before anything is written, so nothing from that batch or comment
    lands in any file.
    """


@dataclass(frozen=True)
class Answer:
    """One answer in the owner's comment, to the question with id `question`.

    `call` is one of `config.CALLS`; `domain_owner` is a free-text answer.
    `task` is the issue the owner's session opened for `fix_source`.
    """

    question: str
    decisions: tuple[str, ...]
    call: str
    note: str
    task: str = ""


# A fence may be indented, as under a list item.
_JSON_BLOCK = re.compile(
    r"^[ \t]*```json[ \t]*\n(.*?)^[ \t]*```[ \t]*$", re.MULTILINE | re.DOTALL
)
# Dates and school years (`2023-24`, `2023-2024`) are removed before the
# checks, so an owner may cite them.
_CITED_DATES = (
    re.compile(r"\d{4}-\d{2}-\d{2}"),
    re.compile(r"\b\d{4}-\d{4}\b"),
    re.compile(r"\b\d{4}-\d{2}\b"),
)
# What a note cannot carry into a committed reason, as (what, pattern, the
# fewest digits a match must hold). An ID or phone number refuses; a rate,
# a grade list or a count of a few digits does not. A person's name cannot be
# told from other words by code; both skills check for names before anything
# is posted or written.
NOTE_REFUSALS = (
    ("an email address", re.compile(r"\S+@\S+\.\w+"), 0),
    ("a run of 5 or more digits", re.compile(r"\d{5,}"), 0),
    ("a number of 7 or more digits", _SEPARATED_DIGITS, 7),
    ("5 or more digits joined by spaces or dashes", re.compile(r"\d[\d\s-]*\d"), 5),
)


def note_refusal(note: str) -> str | None:
    """Name what `note` carries that `NOTE_REFUSALS` keeps out, else None."""
    text = note
    for cited in _CITED_DATES:
        text = cited.sub("", text)
    for what, pattern, fewest in NOTE_REFUSALS:
        for match in pattern.finditer(text):
            if sum(ch.isdigit() for ch in match[0]) >= fewest:
                return what
    return None


def _text(entry: dict, key: str, where: str, *, required: bool = True) -> str:
    value = entry.get(key, "")
    if not isinstance(value, str) or (required and not value.strip()):
        raise AnswerError(f"{where}: `{key}` must be non-empty text")
    return value.strip()


def parse_answers(body: str) -> list[Answer]:
    """Read the answers from the one fenced `json` block of an answers comment.

    The block is a list of `{"question": "Q<n>", "decisions": [<id>, ...],
    "call": <call>, "note": <text>, "task": <link>}`; `task` is needed only for
    `fix_source` and refused on any other call.

    Raises:
        AnswerError: The comment has no or several `json` blocks, the block is
            not a non-empty list of answers, a call is not in `config.CALLS`,
            or a task is missing, misplaced, or not an https:// link or
            #<issue>.
    """
    # A comment body from GitHub often ends its lines with CRLF.
    blocks = _JSON_BLOCK.findall(body.replace("\r\n", "\n"))
    if len(blocks) != 1:
        raise AnswerError(
            f"the comment needs exactly 1 fenced json block; it has {len(blocks)}"
        )
    try:
        data = json.loads(blocks[0])
    except json.JSONDecodeError as exc:
        raise AnswerError(f"the json block is not JSON ({exc})") from exc
    if not isinstance(data, list) or not data:
        raise AnswerError("the json block must be a list of at least 1 answer")

    out = []
    for i, entry in enumerate(data):
        where = f"answer {i + 1}"
        if not isinstance(entry, dict):
            raise AnswerError(f"{where}: must be an object")
        question = where = _text(entry, "question", where)
        decisions = entry.get("decisions")
        if (
            not isinstance(decisions, list)
            or not decisions
            or not all(isinstance(d, str) and d for d in decisions)
        ):
            raise AnswerError(f"{where}: `decisions` must list at least 1 decision id")
        call = _text(entry, "call", where)
        if call not in CALLS:
            raise AnswerError(
                f"{where}: call must be one of {', '.join(CALLS)}; got {call!r}"
            )
        task = _text(entry, "task", where, required=False)
        if call == "fix_source" and not task:
            raise AnswerError(f"{where}: fix_source needs a task")
        if task and call != "fix_source":
            raise AnswerError(f"{where}: only fix_source takes a task; got {call}")
        if task and not _TASK.fullmatch(task):
            raise AnswerError(
                f"{where}: task must be an https:// link or #<issue>; got {task!r}"
            )
        out.append(
            Answer(
                question=question,
                decisions=tuple(decisions),
                call=call,
                note=_text(entry, "note", where, required=False),
                task=task,
            )
        )
    return out


@dataclass(frozen=True)
class Change:
    """What one answer does to one decision in the file at `path`."""

    path: str
    decision: str
    question: str
    call: tuple[str, str]
    task: tuple[str, str]
    reason: tuple[str, str]


def answer_changes(
    answers: list[Answer], configs: list[tuple[str, ViewConfig]]
) -> list[Change]:
    """Match each answer to its decisions and say what it changes.

    The new reason is `<old reason> Owner: <note>`, unless the reason already
    ends that way: recording the same comment twice adds the note once. The
    new task is the file's
    `tasks.cube_fix` for `fix_cube`, `tasks.dashboard_fix` for
    `fix_dashboard`, the answer's own task for `fix_source`, and unchanged for
    the others. A free-text (`domain_owner`) answer keeps its call.

    Args:
        answers: The parsed comment.
        configs: Each validation file's path and config.

    Raises:
        AnswerError: Any answer does not fit, which refuses the whole comment:
            a decision id is in none of the files or in several, is not a
            `domain_owner` decision, or is answered twice; a note carries what
            `NOTE_REFUSALS` keeps out; a free-text answer has no note; or a fix
            call's file has no `tasks:` entry for it.
    """
    out = []
    seen: set[str] = set()
    for a in answers:
        if what := note_refusal(a.note):
            raise AnswerError(
                f"{a.question}: the note has {what}; ask the owner to reword it"
            )
        if a.call == "domain_owner" and not a.note:
            raise AnswerError(f"{a.question}: a free-text answer needs its note")
        for decision_id in a.decisions:
            if decision_id in seen:
                raise AnswerError(
                    f"{a.question}: decision {decision_id!r} is answered twice"
                )
            seen.add(decision_id)
            found = [
                (path, cfg, d)
                for path, cfg in configs
                for d in cfg.decisions
                if d.id == decision_id
            ]
            if not found:
                raise AnswerError(
                    f"{a.question}: no decision {decision_id!r} in the files given"
                )
            if len(found) > 1:
                raise AnswerError(
                    f"{a.question}: decision {decision_id!r} is in "
                    f"{', '.join(path for path, _, _ in found)}; which is meant "
                    "is unclear"
                )
            ((path, cfg, d),) = found
            if d.call != "domain_owner":
                raise AnswerError(
                    f"{a.question}: decision {decision_id!r} is {d.call}, not "
                    "domain_owner; it no longer matches the question"
                )
            task = d.task
            key = {"fix_cube": "cube_fix", "fix_dashboard": "dashboard_fix"}.get(a.call)
            if key:
                if key not in cfg.tasks:
                    raise AnswerError(
                        f"{a.question}: {path} has no `tasks.{key}` for {a.call}; "
                        "add it first"
                    )
                task = cfg.tasks[key]
            elif a.call == "fix_source":
                task = a.task
            owner = f" Owner: {a.note}"
            reason = d.reason
            if a.note and not reason.endswith(owner):
                reason = reason.rstrip() + owner
            out.append(
                Change(
                    path=path,
                    decision=decision_id,
                    question=a.question,
                    call=(d.call, a.call),
                    task=(d.task, task),
                    reason=(d.reason, reason),
                )
            )
    return out


_STUB_KEYS = ("comparison", "group", "cells", "missing_cut", "missing_filter")


def _is_cause_item(item: dict) -> bool:
    """A proven row group, which cause decisions decide (`triage.decidable`)."""
    proof = item.get("proof") or {}
    return (
        item.get("kind") == "group"
        and item.get("suggestion") == "cause"
        and bool(item.get("cause"))
        and proof.get("kind") in ("query", "reconcile")
        and bool(proof.get("fingerprint"))
    )


def _file_cause(d: Decision) -> dict:
    """A cause decision from the file as the dict `write_decision` takes."""
    out: dict = {
        "id": d.id,
        "comparison": d.comparison,
        "cause": dict(d.cause),
        "call": d.call,
        "reason": d.reason,
    }
    if d.task:
        out["task"] = d.task
    if d.answer:
        out["answer"] = d.answer
    out["fingerprints"] = dict(d.fingerprints)
    return out


def _proofs_by_cause(items: list[dict]) -> dict[tuple, set[str]]:
    """Each cause's proof files across the triage's proven row groups."""
    out: dict[tuple, set[str]] = {}
    for item in items:
        if _is_cause_item(item):
            for c in item["cause"]:
                key = (
                    item["comparison"],
                    c.get("side"),
                    mask_digits(c.get("label", "")),
                )
                # A reconcile has no file; its filter's fingerprint stands in.
                proof = item["proof"]
                out.setdefault(key, set()).add(
                    proof.get("path") or proof["fingerprint"]
                )
    return out


def approved_decisions(
    approved: list,
    triage: dict,
    fingerprints: dict[str, dict[str, str]],
    existing: list[Decision] | tuple[Decision, ...] = (),
) -> list[dict]:
    """Turn an approved triage batch into decisions, in the file's key order.

    A proven row group (a stored proof's, or the reconcile's for a sheet
    filter) is decided on its causes, never on a column value: an entry
    decides one cause of one item, `{comparison, cause: {side, label}, call,
    reason, task, fingerprints}`, whose fingerprints are the comparison's and
    the proof's. An item with several causes takes one entry per cause, each
    naming it in `cause`, so each cause gets its own call; the item is
    decided once every cause is. A cause already decided keeps its decision,
    which must have the entry's call; entries on one cause merge into one
    decision. One whose SQL or proof changed since is re-approved on the
    current ones, unless the owner has answered it. A label's ID-shaped
    numbers are written `<n>`. No order of the entries changes the result.

    Every other item takes its key fields from the triage item's `stub`,
    which holds its real values. Either kind takes the comparison's
    `{cube, dashboard}` from the run's fingerprints. A missing cut or filter
    covers the view, so it takes neither a comparison nor fingerprints.

    Args:
        approved: `[{"id", "call", "reason", "task", "item", "cause"}]`;
            `item` is a triage item id, `task` may be empty, and `cause` (the
            cause's words) is needed only on an item with several causes.
        triage: The view's `triage.json`, marked by `triage.mark_decided`.
        fingerprints: The latest run's fingerprints per comparison id.
        existing: The file's decisions.

    Returns:
        The decisions to write: new ones, and the file's cause decisions
        re-approved, each under its own id.

    Raises:
        AnswerError: An entry is malformed, repeats an id or an (item,
            cause), takes an id the file has, has a reason that carries what
            `NOTE_REFUSALS` keeps out, names an item the triage does not list,
            a row group no proof decides, or a cause the item lacks, leaves
            out `cause` on an item with several, names a comparison the run has
            no fingerprints for, or has a cause with no words, words 2 proofs
            share, a decision with another call, or an answered decision whose
            SQL or proof changed.
    """
    items = {item.get("id"): item for item in triage.get("items", [])}
    proofs = _proofs_by_cause(list(items.values()))
    taken = {d.id for d in existing}
    out: list[dict] = []
    # Each cause's decision as this batch leaves it, by (comparison, side, words).
    decided: dict[tuple, dict] = {}
    ids: set[str] = set()
    seen: set[tuple[str, str]] = set()
    for i, entry in enumerate(approved):
        if not isinstance(entry, dict):
            raise AnswerError(f"approved entry {i + 1}: must be an object")
        where = f"approved entry {i + 1}"
        decision_id = _text(entry, "id", where)
        if decision_id in ids:
            raise AnswerError(f"{where}: id {decision_id!r} repeats")
        ids.add(decision_id)
        item_id = _text(entry, "item", where)
        if item_id not in items:
            raise AnswerError(f"{where}: triage lists no item {item_id!r}")
        item = items[item_id]
        named = _text(entry, "cause", where, required=False)
        stub = item.get("stub") or {}
        call = _text(entry, "call", where)
        reason = _text(entry, "reason", where)
        # The reason is committed to git, like an owner's note.
        if what := note_refusal(reason):
            raise AnswerError(f"{where}: the reason has {what}; reword it")
        task = _text(entry, "task", where, required=False)
        fp: dict[str, str] = {}
        comparison = str(stub.get("comparison") or item.get("comparison") or "")
        # A missing cut or filter covers the view, wherever triage found it and
        # whatever pile it sits in: no comparison, no fingerprints.
        if stub.get("missing_cut") or stub.get("missing_filter"):
            comparison = ""
        if comparison:
            fp = fingerprints.get(comparison) or {}
            if not (fp.get("cube") and fp.get("dashboard")):
                raise AnswerError(
                    f"{where}: the run has no fingerprints for {comparison!r}"
                )
            fp = {"cube": fp["cube"], "dashboard": fp["dashboard"]}

        if item.get("kind") == "group" and not _is_cause_item(item):
            raise AnswerError(
                f"{where}: item {item_id!r} is a row group no proof decides; a "
                "row group is decided only on a proven cause"
            )
        if not _is_cause_item(item):
            if (item_id, "") in seen:
                raise AnswerError(f"{where}: item {item_id!r} is approved twice")
            seen.add((item_id, ""))
            if decision_id in taken:
                raise AnswerError(
                    f"{where}: decisions already has {decision_id!r}; pick a new id"
                )
            decision: dict = {"id": decision_id}
            decision.update({k: stub[k] for k in _STUB_KEYS if k in stub})
            decision["call"], decision["reason"] = call, reason
            if task:
                decision["task"] = task
            if fp:
                decision["fingerprints"] = fp
            out.append(decision)
            continue

        proof = item["proof"].get("fingerprint", "")
        causes = item["cause"]
        if named:
            causes = [
                c
                for c in causes
                if mask_digits(c.get("label") or "") == mask_digits(named)
            ]
            if not causes:
                raise AnswerError(f"{where}: item {item_id!r} has no cause {named!r}")
        elif len(causes) > 1:
            raise AnswerError(
                f"{where}: item {item_id!r} has {len(causes)} causes; approve each "
                "in its own entry, naming its words in `cause`"
            )
        new = 0
        for c in causes:
            side, label = c.get("side", ""), mask_digits(c.get("label") or "")
            if (item_id, f"{side}: {label}") in seen:
                raise AnswerError(f"{where}: item {item_id!r} is approved twice")
            seen.add((item_id, f"{side}: {label}"))
            if not label.strip():
                raise AnswerError(
                    f"{where}: item {item_id!r} has a cause with no words"
                )
            key = (comparison, side, label)
            if len(proofs.get(key, ())) > 1:
                raise AnswerError(
                    f"{where}: {len(proofs[key])} proof files name the {side} cause "
                    f"{label!r}; give each its own words"
                )
            target = decided.get(key)
            if target is None:
                found = next(
                    (
                        d
                        for d in existing
                        if d.cause
                        and (d.comparison, d.cause.get("side"), d.cause.get("label"))
                        == key
                    ),
                    None,
                )
                if found is not None:
                    target = decided[key] = _file_cause(found)
                    state = cause_state(found, proof, fp)
                    if state != "holds":
                        if found.answer:
                            raise AnswerError(
                                f"{where}: the owner answered {found.id!r} before "
                                f"its {'SQL' if state == 'sql' else 'proof'} "
                                f"changed; delete it to ask again"
                            )
                        # Re-approved on the current SQL and proof.
                        target.update(call=call, reason=reason)
                        target.pop("task", None)
                        if task:
                            target["task"] = task
                        target["fingerprints"] = {**fp, "proof": proof}
                        out.append(target)
            if target is None:
                new += 1
                new_id = decision_id if new == 1 else f"{decision_id}-{new}"
                if new_id in taken or any(d["id"] == new_id for d in out):
                    raise AnswerError(
                        f"{where}: decisions already has {new_id!r}; pick a new id"
                    )
                target = decided[key] = {
                    "id": new_id,
                    "comparison": comparison,
                    "cause": {"side": side, "label": label},
                    "call": call,
                    "reason": reason,
                    **({"task": task} if task else {}),
                    "fingerprints": {**fp, "proof": proof},
                }
                out.append(target)
            elif target["call"] != call:
                raise AnswerError(
                    f"{where}: the {side} cause {label!r} is decided "
                    f"{target['call']} in {target['id']!r}, not {call}"
                )
            elif target["fingerprints"].get("proof") != proof:
                raise AnswerError(
                    f"{where}: {target['id']!r} was approved on another version of "
                    "the proof; re-run `triage`"
                )
    return out
