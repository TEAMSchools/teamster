"""Gather evidence and sort each open item of a run into a pile.

An open item is a row group, a comparison's cell differences, or a missing cut
or filter. A pile never applies a call: the analyst reads it and decides, and
an item in `investigate` blocks every decision on the view until it reaches a
proven cause. A row group reaches `cause` when the trace (`trace.py`)
attributes every one of its unmatched rows to a step; a missing cut or filter
the sheet carries is its own proof. Item ids and labels carry no value the
review issue would hide. `suggest` is pure; `value_check` and `run_triage`
read the warehouse and Cube.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from . import pipeline, trace
from .bq import Warehouse
from .compare import CellDiff, Gap, Group
from .config import Proof, ViewConfig
from .cube_client import Cube, MemberDoc, member_docs
from .discover import _tokens
from .moment import Build
from .report import (
    _CELL_WORDS,
    RunResult,
    _gap_line,
    _is_identifier,
    _shown_value,
    _where,
    mask,
)
from .timetravel import PROJECT

# The piles, in the order the analyst's batch shows them. Only a `cause` item
# carries a proven cause; an `investigate` item has none yet.
SUGGESTIONS = ("map_filters", "filters_nothing", "cause", "investigate")


@dataclass(frozen=True)
class Item:
    """One open item.

    `kind` is `group`, `cells` or `gap`. `id` and `label` hide what the review
    issue hides. `stub` holds the key fields of the decision that would cover
    the item, with a group's real values: it becomes decision YAML and stays in
    the local cache, never posted.
    """

    id: str
    kind: str
    comparison: str
    label: str
    stub: dict


@dataclass(frozen=True)
class Suggestion:
    """The pile one item lands in, with what it rests on.

    `evidence` is the quoted note, verdict or member doc text; doc text is
    evidence only and never picks the pile. `candidates` are the Cube members a
    missing filter or cut may map to. `cause` is, for a `cause` item, the steps
    its rows are attributed to, each `{side, step, label, n_rows}`; it is None
    until a trace proves one.
    """

    item: Item
    suggestion: str
    evidence: tuple[str, ...]
    candidates: tuple[str, ...] = ()
    cause: list[dict] | None = None


def _stub_dim(g: Group, open_groups: list[Group]) -> tuple[str, str]:
    """Pick the column a decision names for `g`.

    A decision matches one column, so it covers every open group of the
    comparison with that value. Take the first of `g`'s columns whose value no
    other open group holds, else the first column.
    """
    if not g.dims:
        return "", ""
    others = [
        o for o in open_groups if o is not g and o.comparison_id == g.comparison_id
    ]
    for column, value in g.dims:
        if all(o.value_of(column) != value for o in others):
            return column, value
    return g.dims[0]


def _group_item(g: Group, item_id: str, open_groups: list[Group]) -> Item:
    column, value = _stub_dim(g, open_groups)
    label = (
        f"{_where(g, lambda column, value: _shown_value(g, column, value))} in "
        f"{g.comparison_id} ({g.bucket}): {mask(g.n_rows)} rows, "
        f"{mask(g.n_students)} students"
    )
    return Item(
        id=item_id,
        kind="group",
        comparison=g.comparison_id,
        label=label,
        stub={
            "comparison": g.comparison_id,
            "group": {"column": column, "values": [value]},
        },
    )


def _gap_item(g: Gap) -> Item:
    key = "missing_cut" if g.kind == "cut" else "missing_filter"
    return Item(
        id=f"{g.kind}:{g.field}",
        kind="gap",
        comparison=g.comparisons[0] if g.comparisons else "",
        label=_gap_line(g),
        stub={key: g.field},
    )


def _group_ids(groups: list[Group]) -> list[str]:
    """Name each group by its masked values, numbering ids that collide.

    Groups sharing a masked id take `#2`, `#3` in the order of their raw
    dims, so the suffix is stable across runs.
    """
    base = []
    for g in groups:
        shown = ",".join(f"{c}={_shown_value(g, c, v)}" for c, v in g.dims)
        base.append(f"{g.comparison_id}:{shown or 'all'}")
    ids = list(base)
    for name in dict.fromkeys(base):
        same = [i for i, b in enumerate(base) if b == name]
        if len(same) > 1:
            same.sort(key=lambda i: (groups[i].dims, groups[i].bucket))
            for n, i in enumerate(same[1:], start=2):
                ids[i] = f"{name}#{n}"
    return ids


def _entries(run: RunResult) -> list[tuple[Item, Group | Gap | CellDiff]]:
    """Pair each open item with the object it came from."""
    open_groups = run.applied.open
    ids = _group_ids(open_groups)
    out: list[tuple[Item, Group | Gap | CellDiff]] = [
        (_group_item(g, i, open_groups), g)
        for g, i in zip(open_groups, ids, strict=True)
    ]
    out += [(_gap_item(g), g) for g in run.applied.open_gaps]
    for diff in run.applied.open_cells:
        counts = ", ".join(
            f"{mask(n)} {_CELL_WORDS.get(verdict, verdict)}"
            for verdict, n in diff.counts.items()
        )
        item = Item(
            id=f"{diff.comparison_id}:cells",
            kind="cells",
            comparison=diff.comparison_id,
            label=f"{diff.comparison_id}: {counts}",
            stub={"comparison": diff.comparison_id, "cells": True},
        )
        out.append((item, diff))
    return out


def open_items(run: RunResult) -> list[Item]:
    """List the run's open items in the order the review reads them.

    Args:
        run: One view's validation run.

    Returns:
        Groups, then missing cuts and filters, then cell differences. Ids and
        labels are stable across runs and carry a value only for a reviewed
        column of a group with 10+ students; a collision gets `#2`, `#3`.
        Stubs carry real values.
    """
    return [item for item, _ in _entries(run)]


def _open_key(source: Group | Gap | CellDiff) -> str:
    """Name an open item by what it is, not by which other items are open.

    An item's id and stub change as its siblings close; this does not. The
    counts are part of it, so a re-run whose rows changed at the same moment
    re-opens a group or cell set the triage already sorted.
    """
    if isinstance(source, Group):
        raw = [
            "group",
            source.comparison_id,
            source.bucket,
            source.dims,
            source.n_rows,
            source.n_students,
        ]
    elif isinstance(source, Gap):
        raw = ["gap", source.kind, source.field]
    else:
        raw = ["cells", source.comparison_id, sorted(source.counts.items())]
    return hashlib.sha256(json.dumps(raw).encode()).hexdigest()[:16]


def open_keys(run: RunResult) -> list[str]:
    """The run's open items as `_open_key`s, sorted."""
    return sorted({_open_key(source) for _, source in _entries(run)})


def _moment(run: RunResult) -> dict:
    return {
        "start": run.moment.start.isoformat(),
        "end": run.moment.end.isoformat(),
        "job_id": run.moment.job_id,
    }


def proven_triage(run: RunResult, run_json: Path) -> dict:
    """Read the triage of the view's latest run, refusing while any item is unproven.

    Nothing is recorded or reviewed for a view until every one of its items has
    left `investigate`. The gate is per view file: it reads only the triage
    beside that view's latest `run.json`, so one view's open item blocks
    `add-decisions` on that file and any `review` that includes it. Decisions
    written since triage may close items; an item open in the run but absent
    from the triage refuses.

    Args:
        run: The view's latest run (see `pipeline.latest_run`).
        run_json: The `run.json` it came from.

    Raises:
        pipeline.Refusal: No triage sits beside the run, it is unreadable or of
            another moment, the run has an open item the triage did not see,
            an item sits in a pile this validator does not sort into (a triage
            from an older validator), a `cause` item has no cause, or an item
            is in `investigate`.
    """
    view, found = run.view, run_json.parent / "triage.json"
    again = f"run `triage` for {run.moment.start:%Y-%m-%d %H:%M} UTC"
    if not found.exists():
        raise pipeline.Refusal(f"{view}: no triage of the latest run; {again}")
    unreadable = pipeline.Refusal(f"{view}: triage.json is unreadable; re-run triage")
    try:
        loaded = json.loads(found.read_text())
    except json.JSONDecodeError as exc:
        raise unreadable from exc
    if not isinstance(loaded, dict):
        raise unreadable
    if loaded.get("moment") != _moment(run):
        raise pipeline.Refusal(f"{view}: triage.json is of another moment; {again}")
    if unseen := len(set(open_keys(run)) - set(loaded.get("open") or [])):
        were = "is" if unseen == 1 else "are"
        raise pipeline.Refusal(
            f"{view}: {unseen} open item{'' if unseen == 1 else 's'} of the "
            f"latest run {were} not in its triage; {again}"
        )
    items = loaded.get("items", [])
    piles = Counter(item.get("suggestion") for item in items)
    if other := sorted(str(p) for p in set(piles) - set(SUGGESTIONS)):
        raise pipeline.Refusal(
            f"{view}: {found} has items in piles this validator does not sort "
            f"into ({', '.join(other)}); re-run triage"
        )
    if bare := sum(
        1 for i in items if i["suggestion"] == "cause" and not i.get("cause")
    ):
        raise pipeline.Refusal(
            f"{view}: {bare} `cause` item{'' if bare == 1 else 's'} "
            f"{'has' if bare == 1 else 'have'} no cause; re-run triage"
        )
    if n := piles["investigate"]:
        raise pipeline.Refusal(
            f"{view}: {n} triage item{'' if n == 1 else 's'} in `investigate`; "
            "trace each to a proven cause (cube-validation skill, step 8), "
            "then re-run `triage`"
        )
    return loaded


def _candidates(caption: str, docs: dict[str, MemberDoc]) -> tuple[str, ...]:
    """Name the non-measure members whose name, title or description holds the caption."""
    wanted = _tokens(caption)
    if not wanted:
        return ()
    return tuple(
        sorted(
            name
            for name, d in docs.items()
            if d.kind != "measure"
            and wanted <= _tokens(f"{name} {d.title} {d.description}")
        )
    )


def _doc_evidence(members: list[str], docs: dict[str, MemberDoc]) -> tuple[str, ...]:
    """Quote each member's description and ai_context as `<member>: <text>`."""
    out = []
    for name in dict.fromkeys(members):
        d = docs.get(name)
        if d is None:
            continue
        out += [f"{name}: {t}" for t in (d.description, d.ai_context) if t.strip()]
    return tuple(out)


NOT_TRACED = "not traced (`triage --no-trace`)"
NO_ROWS = "no rows to trace: values differ on rows both sides have"
NO_GRAIN = "not traced: the comparison has no `rows` grain"


def suggest(
    cfg: ViewConfig,
    run: RunResult,
    docs: dict[str, MemberDoc],
    values: Callable[[str, str], str] | None = None,
    traces: dict[tuple, trace.ItemTrace] | None = None,
) -> list[Suggestion]:
    """Sort each open item into a pile, first matching rule wins.

    Args:
        cfg: The view's config, for each comparison's measure, group-by
            columns and proof.
        run: One view's validation run.
        docs: The view's members by bare name, from `member_docs`.
        values: `values(caption, member)` returns a value-check verdict;
            `None` skips value checks.
        traces: Each traced row group's trace, by `trace.item_key`; `None`
            when the trace was skipped.

    Returns:
        One suggestion per open item, ordered by `SUGGESTIONS`. A missing
        filter the proof shows filters nothing, or whose values match a Cube
        member's, takes `filters_nothing` or `map_filters`; any other missing
        cut or filter is `cause`, a sheet step on the dashboard side. A row
        group whose rows the trace all attributes is `cause`, with the steps
        and their row counts. Every other item is `investigate`, with what
        the trace found and its involved members' docs as evidence.
    """
    by_id = {c.id: c for c in cfg.comparisons}
    entries = _entries(run)
    out = []
    for item, source in entries:
        evidence: tuple[str, ...] = ()
        verdict_lines: tuple[str, ...] = ()
        candidates: tuple[str, ...] = ()
        members: list[str] = []
        call = ""
        cause: list[dict] | None = None
        found: tuple[str, ...] = ()

        if isinstance(source, Gap):
            gap = source
            caption = gap.field
            members = [by_id[c].measure for c in gap.comparisons if c in by_id]
            # Only the sheets the gap sits on speak for it; a proof that
            # predates `restricting_filters` leaves the answer unknown.
            proofs: list[Proof] = [
                p for c in gap.comparisons if c in by_id and (p := by_id[c].proof)
            ]
            notes = {k: v for p in proofs for k, v in (p.filter_notes or {}).items()}
            all_known = bool(proofs) and all(
                p.restricting_filters is not None for p in proofs
            )
            restricting = {f for p in proofs for f in p.restricting_filters or []}
            if gap.kind == "filter" and caption in notes:
                call, evidence = "filters_nothing", (notes[caption],)
            elif gap.kind == "filter" and all_known and caption not in restricting:
                call = "filters_nothing"
                evidence = (f"keeps every member on {', '.join(gap.sheets)}",)
            else:
                candidates = _candidates(caption, docs)
                verdicts = (
                    [(m, values(caption, m)) for m in candidates] if values else []
                )
                verdict_lines = tuple(f"{m}: {v}" for m, v in verdicts if v)
                if any(v.startswith("same values") for _, v in verdicts):
                    call, evidence = "map_filters", verdict_lines
                else:
                    # The workbook carries it: that is the proof. Whether
                    # Cube needs it is the owner's call on a proven step.
                    step = f"sheet {gap.kind} {caption}"
                    call = "cause"
                    cause = [
                        {
                            "side": "dashboard",
                            "step": step,
                            "label": step,
                            "n_rows": None,
                        }
                    ]
                    evidence = (
                        f"{', '.join(gap.sheets)} carries it; Cube has no member for it",
                        *verdict_lines,
                    )
        else:
            comparison = by_id.get(item.comparison)
            if comparison:
                members = [comparison.measure]
                if isinstance(source, Group):
                    to_cube = {p.dashboard: p.cube for p in comparison.dims}
                    members += [to_cube.get(c, c) for c, _ in source.dims]
            if isinstance(source, Group):
                traced = (traces or {}).get(trace.item_key(source))
                if traced is not None and traced.proven:
                    call, cause, evidence = "cause", traced.cause(), traced.evidence()
                elif traced is not None:
                    found = traced.evidence()
                elif traces is None:
                    found = (NOT_TRACED,)
                elif source.bucket == "value_differs":
                    found = (NO_ROWS,)
                else:
                    found = (NO_GRAIN,)

        if not call:
            call = "investigate"
            evidence = found + verdict_lines + _doc_evidence(members, docs)

        if isinstance(source, Group) and source.dims:
            stub_group = item.stub["group"]
            column, value = stub_group["column"], stub_group["values"][0]
            # No column of this group is its own: the decision covers siblings.
            also = [
                i.id
                for i, o in entries
                if isinstance(o, Group)
                and o is not source
                and o.comparison_id == source.comparison_id
                and o.value_of(column) == value
            ]
            if also:
                evidence += (f"also covers: {', '.join(also)}",)
        out.append(Suggestion(item, call, evidence, candidates, cause))

    return sorted(out, key=lambda s: SUGGESTIONS.index(s.suggestion))


# --- the printed batch -------------------------------------------------------

# Items listed per suggestion; `triage.json` keeps them all.
BATCH_CAP = 25


def _counts(counter: Counter, order: tuple[str, ...] = ()) -> str:
    """`k n` pairs in `order`, then by name."""
    rank = {k: i for i, k in enumerate(order)}
    keys = sorted(counter, key=lambda k: (rank.get(k, len(order)), k))
    return ", ".join(f"{k} {counter[k]:,}" for k in keys)


def batch_lines(run: RunResult, found: list[Suggestion]) -> list[str]:
    """The lines `triage` prints: a summary, a blank line, then the items.

    The summary counts each comparison's items by suggestion and by kind, and
    its row groups by bucket. Each suggestion then lists its first
    `BATCH_CAP` items with their evidence and says how many more
    `triage.json` holds.
    """
    buckets = {i.id: g.bucket for i, g in _entries(run) if isinstance(g, Group)}
    lines = ["Summary"]
    for comparison in dict.fromkeys(s.item.comparison for s in found):
        mine = [s for s in found if s.item.comparison == comparison]
        lines.append(f"  {comparison or '(no comparison)'}: {len(mine):,} items")
        lines.append(
            f"    by suggestion: {_counts(Counter(s.suggestion for s in mine), SUGGESTIONS)}"
        )
        lines.append(f"    by kind: {_counts(Counter(s.item.kind for s in mine))}")
        in_buckets = Counter(buckets[s.item.id] for s in mine if s.item.id in buckets)
        if in_buckets:
            lines.append(f"    groups by bucket: {_counts(in_buckets)}")
    lines.append("")

    for call in SUGGESTIONS:
        group = [s for s in found if s.suggestion == call]
        if not group:
            continue
        lines.append(f"{call} ({len(group)})")
        for s in group[:BATCH_CAP]:
            lines.append(f"- {s.item.label}")
            lines += [f"    {line}" for line in s.evidence]
            if s.candidates:
                lines.append(f"    candidates: {', '.join(s.candidates)}")
        if len(group) > BATCH_CAP:
            lines.append(f"  … {len(group) - BATCH_CAP:,} more in triage.json")
    return lines


# --- value checks and the command --------------------------------------------

# A column with more distinct values than this is a key, not a coding.
REFERENCE_MAX_VALUES = 50
_ID_SUFFIXES = ("_number", "_id", "_name", "_email")
_SAME = "same values: map it under filters:"
_CODING = "same field, different coding"
_NOT_COMPARED = "not compared: identifier column"
_SQL_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_TABLE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*")


def pii_members(meta: dict, view: str) -> set[str]:
    """Name `view`'s members Cube marks `contains_pii`, by bare name.

    Names ending in `_number`, `_id`, `_name` or `_email` count as PII in
    `value_check` whether or not Cube marks them.
    """
    out: set[str] = set()
    for cube in meta.get("cubes", []):
        if cube.get("name") != view:
            continue
        for field in ("measures", "dimensions", "segments"):
            out |= {
                m["name"].split(".", 1)[-1]
                for m in cube.get(field) or []
                if (m.get("meta") or {}).get("contains_pii") is True
            }
    return out


def _dashboard_view(cfg: ViewConfig, column: str) -> str:
    """The dashboard table behind `column`: the comparison that names it, else the first."""
    for c in cfg.comparisons:
        if c.proof and column in (c.proof.missing_columns or {}).values():
            return c.dashboard_view or ""
    return next((c.dashboard_view for c in cfg.comparisons if c.dashboard_view), "")


def value_check(
    wh: Warehouse,
    cube: Cube,
    cfg: ViewConfig,
    column: str,
    member: str,
    moment: Build,
    pii: set[str],
) -> str:
    """Compare a dashboard column's distinct values with a Cube member's.

    The dashboard side reads as of `moment.start`, the Cube side as Cube serves
    it now. Both queries count against the run and daily caps, so call this
    inside `wh.budget`. It runs no query for a `pii` member or for a member or
    column named like an identifier, and compares nothing when either side has
    more than `REFERENCE_MAX_VALUES` values. A distinct-value list carries no
    group size, so values print only to the terminal, and only when both the
    member and the column are in `report._SHOWN_COLUMNS`; they never reach
    `triage.json` or the evidence.

    Args:
        wh: The warehouse the dashboard side reads through.
        cube: Cube, for the member's distinct values.
        cfg: The view's config, for its name and dashboard table.
        column: The dashboard datasource column behind the missing field.
        member: The Cube member's bare name.
        moment: The run's moment.
        pii: Members whose values are never read.

    Returns:
        One of `same values: map it under filters:`,
        `same field, different coding` (the candidate already matches by name
        or description, so differing values mean differing codes) or
        `not compared: identifier column`.
    """
    table = _dashboard_view(cfg, column)
    if (
        member in pii
        or member.endswith(_ID_SUFFIXES)
        or column.endswith(_ID_SUFFIXES)
        or not _SQL_NAME.fullmatch(column)
        or not _TABLE.fullmatch(table)
    ):
        return _NOT_COMPARED

    dataset, name = table.split(".")
    sql = (
        f"SELECT DISTINCT CAST({column} AS STRING) AS value "  # trunk-ignore(bandit/B608)
        f"FROM `{PROJECT}`.`{dataset}`.`{name}` "
        f"WHERE {column} IS NOT NULL LIMIT {REFERENCE_MAX_VALUES + 1}"
    )
    dash = {
        str(r["value"]) for r in wh.rows(pipeline._as_of(sql, moment.start, wh).sql)
    }
    if len(dash) > REFERENCE_MAX_VALUES:
        return _NOT_COMPARED

    key = f"{cfg.view}.{member}"
    rows = pipeline._priced_load(
        cube, wh, {"dimensions": [key], "limit": REFERENCE_MAX_VALUES + 1}
    )
    # Count before dropping nulls: a null can fill the limit and cut the set short.
    if len(rows) > REFERENCE_MAX_VALUES:
        return _NOT_COMPARED
    theirs = {str(r[key]) for r in rows if r.get(key) is not None}

    if dash == theirs:
        return _SAME
    if not (_is_identifier(member) or _is_identifier(column)):
        print(f"  {member}: dashboard {sorted(dash)} vs Cube {sorted(theirs)}")
    return _CODING


def _missing_column(cfg: ViewConfig, caption: str) -> str:
    """The datasource column behind a missing field, or empty when no proof names it."""
    for c in cfg.comparisons:
        if c.proof and caption in (c.proof.missing_columns or {}):
            return (c.proof.missing_columns or {})[caption]
    return ""


def run_triage(
    cfg: ViewConfig,
    *,
    wh: Warehouse,
    cube: Cube,
    max_usd: float,
    cache_root: Path,
    trace_rows: bool = True,
    manifest: Path = trace.MANIFEST,
) -> list[Suggestion]:
    """Sort each open item of the view's latest run into a pile and print them.

    Traces the run's row groups first (`trace.trace_run`) unless `trace_rows`
    is False; its queries count against `max_usd` and the daily cap with the
    value checks. Prints `batch_lines`. Writes every item to `triage.json`
    beside that run's `run.json`, with the run's moment, decisions
    fingerprint and open items (see `proven_triage`): it stays in the local
    cache, and its stubs and causes carry real values and exact counts.

    Raises:
        pipeline.Refusal: The view has no usable saved run (see
            `pipeline.latest_run`), its SQL changed since the run, or the
            manifest lacks compiled SQL the trace needs.
        CostCapError: The value checks or the trace would pass a cap.
    """
    run, run_json = pipeline.latest_run(cfg, cache_root)
    meta = cube.meta()
    docs = member_docs(meta, cfg.view)
    pii = pii_members(meta, cfg.view)

    def values(caption: str, member: str) -> str:
        column = _missing_column(cfg, caption)
        if not column:
            return ""
        return value_check(wh, cube, cfg, column, member, run.moment, pii)

    with wh.budget(max_usd):
        traces = (
            trace.trace_run(cfg, run, wh=wh, cube=cube, manifest_path=manifest)
            if trace_rows
            else None
        )
        found = suggest(cfg, run, docs, values, traces)

    out = run_json.parent / "triage.json"
    out.write_text(
        json.dumps(
            {
                "view": run.view,
                "moment": _moment(run),
                "decisions_fingerprint": run.decisions_fingerprint,
                "open": open_keys(run),
                "items": [
                    {
                        **dataclasses.asdict(s.item),
                        "suggestion": s.suggestion,
                        "evidence": list(s.evidence),
                        "candidates": list(s.candidates),
                        "cause": s.cause,
                    }
                    for s in found
                ],
            },
            indent=1,
        )
    )

    print("\n".join(batch_lines(run, found)))
    print(f"Saved {out}")
    return found
