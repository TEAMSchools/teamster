"""Gather evidence and sort each open item of a run into a pile.

An open item is a row group, a comparison's cell differences, or a missing cut
or filter. A pile never applies a call: the analyst reads it and decides. An
item in `investigate` takes no decision until it reaches an explained cause, while
the view's other items are decided; `ask-owner` lists it as still with the
analyst. The trace (`trace.py`) only leads: a row group reaches `cause`
when `explain` (`explain.py`) checks a classification query that names
each of its unmatched rows' cause. A missing cut or filter the sheet carries,
and rows the sheet's own dashboard-only filter drops, are their own explanation.
Item ids and labels carry no value the review issue would hide. `suggest` is
pure; `value_check` and `sort_run` read the warehouse and Cube.
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import re
import sys
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from google.api_core.exceptions import GoogleAPIError

from . import checkpoints, decisions, latest, pipeline, results, trace
from .bq import CostCapError, Warehouse
from .config import Comparison, Decision, RebuildCheck, ViewConfig, mask_digits
from .cube_client import Cube, MemberDoc, member_docs, network_schools
from .find_field import name_tokens
from .moment import Build, utcnow
from .reconcile import FORMULA_CHECK, CellDiff, Gap, Group
from .report import (
    CELL_WORDS,
    CauseAsk,
    RunResult,
    Ticker,
    Unsettled,
    gap_line,
    is_identifier,
    mask,
    name_group,
    run_stamp,
    shown_value,
)
from .timetravel import PROJECT

if TYPE_CHECKING:
    # `formula` is imported where it is used: it imports `explain`, which
    # imports this module.
    from .formula import Check, Job

# The piles, in the order the analyst's batch shows them. Only a `cause` item
# carries an explained cause; an `investigate` item has none yet.
SUGGESTIONS = ("map_filters", "filters_nothing", "cause", "investigate")
# What a `cause` rests on: a stored classification query (`explain.py`), the
# run's own reconcile (rows the sheet's dashboard-only filter drops), the
# workbook XML (a missing cut or filter), explained groups (a cell set), or the
# run's matched rows (a formula difference).
EXPLANATION_KINDS = ("query", "reconcile", "workbook", "cells", "formula")
# A formula difference's cause: every row in its cells matched on both sides.
FORMULA_LABEL = "differing cells hold no unmatched row"
# Its cause when the formula check filed cells that hold unmatched rows too:
# they still differ with those rows left out.
MATCHED_LABEL = "differing cells differ on matched rows"
# How `sort` and `ask-owner` name a comparison the latest run skipped.
NOT_COMPARED = "not compared"
# The sort `sort` writes beside the run's `run.json`.
FILE = "sort.json"
# The name an older validator wrote it under, with items in an older shape:
# never read, only refused.
OLD_FILE = "triage.json"


@dataclass(frozen=True)
class Item:
    """One open item.

    `kind` is `group`, `cells`, `formula` or `gap`. `id` and `label` hide the
    values the review issue hides; `label` shows exact counts and stays local.
    `stub` holds the key fields of the decision that would cover the item,
    with a group's real values: it becomes decision YAML and stays in the
    local cache, never posted.
    """

    id: str
    kind: str
    comparison: str
    label: str
    stub: dict
    # `open_key`: what the item is, whichever siblings are open. An id's
    # `#n` can move when a sibling closes; this cannot.
    key: str = ""


@dataclass(frozen=True)
class Suggestion:
    """The pile one item lands in, with what it rests on.

    `evidence` is the quoted note, verdict, trace lead or model-doc lead;
    a lead never picks the pile. `candidates` are the Cube members a
    missing filter or cut may map to. `cause` is, for a `cause` item, its
    causes, each `{side, step, label, n_rows}`; it is None until one is
    explained. `explanation` is what the cause rests on, typed by `kind`
    (`EXPLANATION_KINDS`); a stored explanation's also names its file. `evidence`
    shows exact counts; `posted` is the same lines masked for the review
    issue (`report.shown_counts`), or None when it equals `evidence`. A
    sheet filter's first evidence line says whether Cube offers it; names
    only, never a value.
    """

    item: Item
    suggestion: str
    evidence: tuple[str, ...]
    candidates: tuple[str, ...] = ()
    cause: list[dict] | None = None
    explanation: dict | None = None
    posted: tuple[str, ...] | None = None
    # `mark_decided`'s marks: each cause's deciding decision id, and whether
    # every cause has one. None on an item no cause decision decides.
    decisions: dict[str, str | None] | None = None
    decided: bool | None = None
    # A sheet filter's default call (`deliberate`, `fix_cube`) when the
    # evidence settles it; empty when the action is a mapping.
    default_call: str = ""


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


def _group_label(g: Group) -> str:
    """The group's label: its values as the id shows them, its exact counts.

    Labels stay in the terminal and the local cache; the review issue never
    shows them.
    """
    return (
        f"{name_group(g, lambda column, value: shown_value(g, column, value))} in "
        f"{g.comparison_id} ({g.bucket}): {g.n_rows} rows, "
        f"{g.n_students} students"
    )


def _group_item(g: Group, item_id: str, open_groups: list[Group]) -> Item:
    label = _group_label(g)
    stub: dict = {"comparison": g.comparison_id}
    # A dashboard-filtered group is decided on its cause (the sheet filter),
    # never by a column value that would close later groups no one explained.
    if g.bucket != "dashboard_filtered":
        column, value = _stub_dim(g, open_groups)
        stub["group"] = {"column": column, "values": [value]}
    return Item(
        id=item_id, kind="group", comparison=g.comparison_id, label=label, stub=stub
    )


def _gap_item(g: Gap) -> Item:
    key = "missing_cut" if g.kind == "cut" else "missing_filter"
    return Item(
        id=f"{g.kind}:{g.field}",
        kind="gap",
        comparison=g.comparisons[0] if g.comparisons else "",
        label=gap_line(g),
        stub={key: g.field},
    )


def _group_ids(groups: list[Group]) -> list[str]:
    """Name each group by its masked values, numbering ids that collide.

    Groups sharing a masked id take `#2`, `#3` in the order of their raw
    dims, so the suffix is stable across runs.
    """
    base = []
    for g in groups:
        shown = ",".join(f"{c}={shown_value(g, c, v)}" for c, v in g.dims)
        base.append(f"{g.comparison_id}:{shown or 'all'}")
    ids = list(base)
    for name in dict.fromkeys(base):
        same = [i for i, b in enumerate(base) if b == name]
        if len(same) > 1:
            same.sort(key=lambda i: (groups[i].dims, groups[i].bucket))
            for n, i in enumerate(same[1:], start=2):
                ids[i] = f"{name}#{n}"
    return ids


def open_entries(run: RunResult) -> list[tuple[Item, Group | Gap | CellDiff]]:
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
            f"{n} {CELL_WORDS.get(verdict, verdict)}"
            for verdict, n in diff.counts.items()
        )
        # A formula difference is its own item, decided by `formula: true`;
        # a cell set closes by coverage.
        what = " formula difference" if diff.kind == "formula" else ""
        item = Item(
            id=f"{diff.comparison_id}:{diff.kind}",
            kind=diff.kind,
            comparison=diff.comparison_id,
            label=f"{diff.comparison_id}{what}: {counts}",
            stub={"comparison": diff.comparison_id, diff.kind: True},
        )
        out.append((item, diff))
    return [(dataclasses.replace(i, key=open_key(src)), src) for i, src in out]


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
    return [item for item, _ in open_entries(run)]


def open_key(source: Group | Gap | CellDiff) -> str:
    """Name an open item by what it is, not by which other items are open.

    An item's id and stub change as its siblings close; this does not. The
    counts are part of it, so a re-run whose rows changed at the same moment
    re-opens a group or cell set the sort already sorted.
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
        raw = [source.kind, source.comparison_id, sorted(source.counts.items())]
    return hashlib.sha256(json.dumps(raw).encode()).hexdigest()[:16]


def open_keys(run: RunResult) -> list[str]:
    """The run's open items as `open_key`s, sorted."""
    return sorted({open_key(source) for _, source in open_entries(run)})


def _moment(run: RunResult) -> dict:
    """The run a sort sorted: its moment, and each composed comparison's,
    so a run composed again from a newer result needs a new sort."""
    return {
        **run.moment.to_json(),
        "moments": {cid: run_stamp(m) for cid, m in run.moments.items()},
    }


def formulas_not_compared(loaded: dict) -> dict[str, dict[str, int]]:
    """Per comparison, the cells the formula check left to coverage, by reason.

    Read from the sort's `formulas_not_compared`, not from item evidence,
    which `explain` can rewrite. A sort without the key, or with a
    malformed one, gives `{}`; `formula_checked` tells that from a check that
    left nothing uncompared. A comparison whose counts are not all positive
    whole numbers is left out.
    """
    held = loaded.get("formulas_not_compared")
    if not isinstance(held, dict):
        return {}
    return {
        cid: dict(reasons)
        for cid, reasons in held.items()
        if isinstance(reasons, dict)
        and reasons
        and all(
            isinstance(n, int) and not isinstance(n, bool) and n > 0
            for n in reasons.values()
        )
    }


# How the sort's posted lines (`evidence_posted`) are masked (`report.suppress`,
# `shown_counts(posted=True)`). `ask-owner` posts them as `sort` stored them,
# so bump this whenever that masking changes: `load_sort` then refuses a
# sort written under an older rule until `sort` runs again.
POSTED_VERSION = 1


def posted_current(loaded: dict) -> bool:
    """Whether the sort's posted lines were masked by the current rule
    (`POSTED_VERSION`); a missing or older version was not."""
    held = loaded.get("posted_version")
    return (
        isinstance(held, int) and not isinstance(held, bool) and held >= POSTED_VERSION
    )


def formula_checked(loaded: dict) -> bool:
    """Whether the sort was written by a `sort` that ran the formula check.

    `sort` always writes `formulas_not_compared`, empty when the check left
    nothing uncompared, so a sort without it, or with a malformed one,
    predates the check: its cells closed by coverage alone, with nothing to
    say so.
    """
    return isinstance(loaded.get("formulas_not_compared"), dict)


def comparisons_waiting(
    cfg: ViewConfig, run: RunResult, loaded: dict
) -> dict[str, str]:
    """Each confirmed comparison still with the analyst, and why, in config order.

    A comparison is waiting when the run skipped it (`not compared: <why>`),
    the run holds no result of it, its result was stale when the sort ran
    (`loaded["stale"]`), or its entry changed since the result
    (`latest.entry_fingerprint` against `run.entries`, offline). Nothing
    refuses over them: the rest of the view goes on.
    """
    stale = loaded.get("stale") or {}
    skipped = {s["comparison"]: s["why"] for s in run.skipped}
    out: dict[str, str] = {}
    for c in cfg.comparisons:
        if not c.confirmed:
            continue
        if c.id in skipped:
            out[c.id] = f"{NOT_COMPARED}: {skipped[c.id]}"
        elif c.id in run.missing:
            out[c.id] = results.NEVER_COMPARED
        elif c.id in stale:
            out[c.id] = stale[c.id]
        elif c.id in run.entries and latest.entry_fingerprint(c) != run.entries[c.id]:
            out[c.id] = results.ENTRY_CHANGED
    return out


def load_sort(
    run: RunResult, run_json: Path, *, for_explain: bool = False
) -> tuple[Path, dict]:
    """Read the sort beside `run_json`, refusing one that is missing (an
    older validator's `OLD_FILE` alone counts as missing, named as such),
    unreadable, of another moment, written before the formula check
    (`formula_checked`) or under an older posted masking (`posted_current`),
    or blind to an open item of `run`.

    Args:
        run: The view's latest run.
        run_json: The `run.json` it came from.
        for_explain: Word the refusals as `explain` does: its remedy ends in
            "first", and it counts no unseen items.

    Raises:
        pipeline.Refusal: The sort fails one of those checks.

    Returns:
        The sort's path and its contents.
    """
    view, found = run.view, run_json.parent / FILE
    again = f"run `sort` for {run.moment.start:%Y-%m-%d %H:%M} UTC" + (
        " first" if for_explain else ""
    )
    if not found.exists():
        if (run_json.parent / OLD_FILE).exists():
            raise pipeline.Refusal(
                f"{view}: the sort of the latest run is an older validator's "
                f"{OLD_FILE}; {again}"
            )
        raise pipeline.Refusal(f"{view}: no sort of the latest run; {again}")
    unreadable = pipeline.Refusal(
        f"{view}: {FILE} is unreadable; " + (again if for_explain else "re-run `sort`")
    )
    try:
        loaded = json.loads(found.read_text())
    except json.JSONDecodeError as exc:
        raise unreadable from exc
    other_moment = pipeline.Refusal(f"{view}: {FILE} is of another moment; {again}")
    if not isinstance(loaded, dict):
        raise other_moment if for_explain else unreadable
    if loaded.get("moment") != _moment(run):
        raise other_moment
    if not formula_checked(loaded):
        raise pipeline.Refusal(f"{view}: the sort predates the formula check; {again}")
    if not posted_current(loaded):
        raise pipeline.Refusal(
            f"{view}: the sort's posted evidence was masked by an older rule; {again}"
        )
    if unseen := len(set(open_keys(run)) - set(loaded.get("open") or [])):
        if for_explain:
            raise pipeline.Refusal(
                f"{view}: the latest run has open items its sort lacks; {again}"
            )
        were = "is" if unseen == 1 else "are"
        raise pipeline.Refusal(
            f"{view}: {unseen} open item{'' if unseen == 1 else 's'} of the "
            f"latest run {were} not in its sort; {again}"
        )
    return found, loaded


def checked_sort(
    run: RunResult,
    run_json: Path,
    recorded: list[Decision] | None = None,
    base: Path | None = None,
) -> dict:
    """Read the sort of the view's latest run, refusing one that is stale or
    whose explained items do not hold.

    The gate is per validation file: it reads only the sort beside that view's
    latest `run.json`. Decisions written since the sort may close items; an
    item open in the run but absent from the sort refuses. Items still in
    `investigate` do not refuse: they come back under `unsettled`, so
    `ask-owner` lists them, and `decide` decides the rest.

    Args:
        run: The view's latest run (see `results.latest_run`).
        run_json: The `run.json` it came from.
        recorded: The view's decisions. When given, each explained row group is
            marked by the cause decisions that decide it (`mark_decided`).
        base: The validation file's directory, which stored explanation paths are
            relative to.

    Raises:
        pipeline.Refusal: No sort sits beside the run, it is unreadable or of
            another moment, it predates the formula check (`formula_checked`)
            or the current posted masking (`posted_current`), the run has an
            open item the sort did not see,
            an item sits in a pile this validator does not sort into (a sort
            from an older validator), a `cause` item has no cause, a decision
            other than a comparison decision closes an item in `investigate`,
            a row group or cell set in
            `cause` rests on no explanation, an explanation an item rests on
            changed since, or a cause decision and a `group` decision disagree on
            one group.

    Returns:
        The sort as `sort.json` holds it, with `unsettled`: its items
        still in `investigate` that no decision closed.
    """
    view = run.view
    found, loaded = load_sort(run, run_json)
    items = loaded.get("items", [])
    piles = Counter(item.get("suggestion") for item in items)
    if other := sorted(str(p) for p in set(piles) - set(SUGGESTIONS)):
        raise pipeline.Refusal(
            f"{view}: {found} has items in piles this validator does not sort "
            f"into ({', '.join(other)}); re-run `sort`"
        )
    if bare := sum(
        1 for i in items if i["suggestion"] == "cause" and not i.get("cause")
    ):
        raise pipeline.Refusal(
            f"{view}: {bare} `cause` item{'' if bare == 1 else 's'} "
            f"{'has' if bare == 1 else 'have'} no cause; re-run `sort`"
        )
    # A decision written by hand must not close what no one explained; a
    # comparison decision, which `decide` writes, closes it on purpose. A
    # hand-written comparison decision would pass here too: the runbook
    # forbids one, and nothing here can tell who wrote it.
    closed = {
        open_key(src): d for d, src in [*run.applied.quiet, *run.applied.quiet_cells]
    }
    for i in items:
        d = closed.get(i.get("key", ""))
        if d is not None and i["suggestion"] == "investigate" and not d.all_groups:
            raise pipeline.Refusal(
                f"{view}: decision {d.id!r} closes item {i['id']!r}, which the "
                "sort holds in `investigate`; delete the decision and run `explain` "
                "on the item (see `explain` in the cube-validation skill)"
            )
    # Every cause rests on a typed explanation (`EXPLANATION_KINDS`).
    if bare := sum(
        1
        for i in items
        if i["suggestion"] == "cause"
        and (i.get("explanation") or {}).get("kind") not in EXPLANATION_KINDS
    ):
        raise pipeline.Refusal(
            f"{view}: {bare} `cause` item{'' if bare == 1 else 's'} "
            f"rest{'s' if bare == 1 else ''} on no explanation; run `explain` "
            f"on {'it' if bare == 1 else 'them'}, then re-run `sort`"
        )
    if moved := sum(
        1 for i in items if _explanation_changed(i.get("explanation"), base)
    ):
        raise pipeline.Refusal(
            f"{view}: {moved} item{'' if moved == 1 else 's'} in `cause` "
            f"rest{'s' if moved == 1 else ''} on an explanation file changed "
            "since the sort; re-run `sort`"
        )
    if recorded is not None:
        try:
            mark_decided(run, items, recorded, refuse=True)
            mark_decided(run, _closed(loaded), recorded, refuse=True)
        except pipeline.Refusal as exc:
            raise pipeline.Refusal(f"{view}: {exc}") from exc
    loaded["unsettled"] = [
        i
        for i in items
        if i["suggestion"] == "investigate" and i.get("key", "") not in closed
    ]
    return loaded


def unsettled(run: RunResult, loaded: dict) -> list[Unsettled]:
    """The sort's items still in `investigate` and open, as `ask-owner`
    lists them; one a comparison decision closed since is decided.

    Each is matched to the run's open item by its `open_key` for its bucket
    and counts; one the run no longer holds keeps its kind and no count. Read
    `loaded` through `posted_sort`, so a lead's counts are masked.
    """
    sources = {open_key(src): src for _, src in open_entries(run)}
    # A comparison decision closes groups still in `investigate`.
    closed = {open_key(g) for _, g in run.applied.quiet}
    out = []
    for item in loaded.get("items", []):
        if item.get("suggestion") != "investigate" or item.get("key") in closed:
            continue
        source = sources.get(item.get("key", ""))
        lead = next((e for e in item.get("evidence", []) if e.startswith("lead: ")), "")
        common = {
            "view": run.view,
            "comparison": item.get("comparison", ""),
            "item": item["id"],
            "lead": lead,
        }
        if isinstance(source, Group):
            hidden = tuple(
                v for c, v in source.dims if shown_value(source, c, v) == "<redacted>"
            )
            out.append(
                Unsettled(
                    **common, what=source.bucket, rows=source.n_rows, hidden=hidden
                )
            )
        elif isinstance(source, CellDiff):
            out.append(
                Unsettled(**common, what=source.kind, cells=sum(source.counts.values()))
            )
        else:
            out.append(Unsettled(**common, what=item.get("kind", "item")))
    return out


def _closed(loaded: dict) -> list[dict]:
    """A copy of the sort's closed groups, which `mark_decided` marks in place."""
    return copy.deepcopy(loaded.get("closed") or [])


def check_closed(run: RunResult, run_json: Path, recorded: list[Decision]) -> None:
    """Refuse a cause decision that disagrees with the `group` decision closing a
    group its explanation covers.

    The sort lists no closed group, so `mark_decided` on its items never sees
    one; the sort's `closed` list (`closed_groups`) says which causes each
    holds. Called wherever decisions are written, so the disagreement refuses
    then, not once the group decision goes stale and the group reopens. With
    no readable sort of the run's moment there is nothing to compare.

    Raises:
        pipeline.Refusal: A holding cause decision and a `group` decision on
            one closed group make different calls.
    """
    try:
        loaded = json.loads((run_json.parent / FILE).read_text())
    except (OSError, json.JSONDecodeError):
        loaded = None
    if isinstance(loaded, dict) and loaded.get("moment") == _moment(run):
        mark_decided(run, _closed(loaded), recorded, refuse=True)
        return
    print(
        "closed-group check skipped: no sort of this run; "
        "run `sort --no-trace` to check decisions against closed groups",
        file=sys.stderr,
    )


# Why a cause decision no longer decides an item it names.
_STALE = {
    "sql": "the SQL changed since the decision; re-approve",
    "explanation": "the explanation changed since the decision; re-approve",
}


# The explanations of a row group that cause decisions decide.
DECIDABLE_EXPLANATIONS = ("query", "reconcile")


def decidable(item: dict) -> bool:
    """An explained row group: cause decisions decide it, never a column value."""
    explanation = item.get("explanation") or {}
    return (
        item.get("kind") == "group"
        and item.get("suggestion") == "cause"
        and bool(item.get("cause"))
        and explanation.get("kind") in DECIDABLE_EXPLANATIONS
        and bool(explanation.get("fingerprint"))
    )


def cause_key(side: str, label: str) -> str:
    """A cause as a decision names it: its side and its digit-masked words."""
    return f"{side}: {mask_digits(label)}"


def cause_decision(
    recorded: Iterable[Decision], comparison: str, side: str, label: str
) -> Decision | None:
    """The cause decision on `label` at `side` of `comparison`, if any."""
    words = mask_digits(label)
    return next(
        (
            d
            for d in recorded
            if d.cause
            and d.comparison == comparison
            and d.cause.get("side") == side
            and d.cause.get("label") == words
        ),
        None,
    )


def groups_by_key(run: RunResult) -> dict[str, Group]:
    """The run's open groups by `open_key`, which no sibling's closing moves."""
    return {i.key: g for i, g in open_entries(run) if isinstance(g, Group)}


def _quiet_by_key(run: RunResult) -> dict[str, Group]:
    """The groups a `group` decision closes in the run, by `open_key`."""
    return {open_key(g): g for _, g in run.applied.quiet}


def mark_decided(
    run: RunResult,
    items: list[dict],
    recorded: list[Decision],
    *,
    refuse: bool = False,
    note: bool = False,
) -> None:
    """Mark each explained row group by the cause decisions that decide it.

    A decidable item gets `decisions`, `{cause_key: decision id or None}`, and
    `decided`, true only when every one of its causes has a decision that
    holds: the comparison's SQL and the item's explanation file are the ones it was
    made on. A decision that no longer holds counts as none.

    A cell set in `cause` on its covering groups (`explanation.kind` `cells`) gets
    `decided`, true when every item its explanation names (`explanation.groups`) is
    decided; the groups a `group` decision closed (`explanation.closed`) are
    decided by it.

    A holding cause decision on a group a `group` decision also covers,
    stale or not, is redundant when their calls agree and refused when they
    differ; so is one on a group of a comparison decision's comparison that
    no `group` decision covers.

    Args:
        run: The run the items come from.
        items: The sort items, or its `closed` groups, marked in place. The
            group is looked up among the run's open and closed groups, since
            a re-apply since the sort can close an item's.
        recorded: The view's decisions.
        refuse: Raise on a disagreement instead of noting it.
        note: Add why a decision does not hold, and any redundancy or
            disagreement, to the item's evidence.

    Raises:
        pipeline.Refusal: With `refuse`, a disagreement.
    """
    groups = {**_quiet_by_key(run), **groups_by_key(run)}
    by_group = [d for d in recorded if (d.group or d.all_groups) and not d.cause]
    for item in items:
        if not decidable(item):
            continue
        current = run.fingerprints.get(item["comparison"]) or {}
        explanation = item["explanation"].get("fingerprint", "")
        found: dict[str, str | None] = {}
        held: list[Decision] = []
        lines: list[str] = []
        for c in item["cause"]:
            key = cause_key(c["side"], c["label"])
            d = cause_decision(recorded, item["comparison"], c["side"], c["label"])
            state = (
                decisions.cause_state(d, explanation, current, c.get("unchanged") or ())
                if d
                else ""
            )
            found[key] = d.id if d and state == "holds" else None
            if d and state == "holds":
                held.append(d)
            elif d:
                lines.append(f"decision {d.id}: {_STALE[state]}")
        item["decisions"] = found
        item["decided"] = all(found.values())
        g = groups.get(item.get("key", ""))
        covering = [o for o in by_group if g is not None and _covers_group(o, g)]
        # A comparison decision leaves a group decision's groups to it.
        if any(not o.all_groups for o in covering):
            covering = [o for o in covering if not o.all_groups]
        for other in covering:
            for d in held:
                if d.call == other.call:
                    lines.append(f"decision {d.id} repeats group decision {other.id}")
                    continue
                # A closed group's id is a hash: name it by the closing
                # decision's column, never by its values.
                how = (
                    "as a whole comparison"
                    if other.all_groups
                    else f"by {other.group.get('column')!r}"
                )
                where = (
                    f"a group of {item['comparison']!r} that {other.id!r} closes {how}"
                    if item.get("closed")
                    else f"item {item['id']!r}"
                )
                line = (
                    f"decisions {other.id!r} ({other.call}) and {d.id!r} "
                    f"({d.call}) disagree on {where}"
                )
                if refuse:
                    raise pipeline.Refusal(line)
                lines.append(line)
        if note and lines:
            evidence = item.get("evidence", [])
            posted = item.get("evidence_posted", evidence)
            item["evidence"] = [*lines, *evidence]
            item["evidence_posted"] = [*lines, *posted]
    # After the groups, which a cell set's mark reads, wherever it is listed.
    marked = {i["id"]: i.get("decided") is True for i in items if decidable(i)}
    for item in items:
        explanation = item.get("explanation") or {}
        if item.get("suggestion") == "cause" and explanation.get("kind") == "cells":
            item["decided"] = all(marked.get(g, False) for g in explanation["groups"])


def _covers_group(d: Decision, g: Group) -> bool:
    """A `group` decision names `g`, or a comparison decision is on its
    comparison, whether or not its SQL still holds."""
    if d.all_groups:
        return d.comparison == g.comparison_id
    values = {decisions.group_text(v) for v in d.group.get("values") or []}
    return (
        d.comparison == g.comparison_id
        and g.value_of(d.group.get("column") or "") in values
    )


def cause_asks(
    run: RunResult,
    loaded: dict,
    recorded: list[Decision],
    leads: dict[str, str] | None = None,
    owner: bool = True,
) -> list[CauseAsk]:
    """What `ask-owner` asks the owner: each unanswered owner cause and its groups.

    Reads items `mark_decided` marked. A cause's rows are only those its
    explanation attributes to it, so a group split across causes counts in each
    question only by its own share. With `owner` False, the cause decisions
    the analyst made with any other call instead, which `ask-owner` only reports.
    """
    groups = groups_by_key(run)
    out = []
    for d in recorded:
        if not d.cause or d.answer or (d.call == "domain_owner") != owner:
            continue
        mine, rows, explanations = [], 0, {}
        for item in loaded.get("items", []):
            if not decidable(item) or item.get("key", "") not in groups:
                continue
            marks = item.get("decisions") or {}
            causes = [
                c
                for c in item["cause"]
                if marks.get(cause_key(c["side"], c["label"])) == d.id
            ]
            if causes:
                mine.append(groups[item["key"]])
                rows += sum(c.get("n_rows") or 0 for c in causes)
                explanation = item.get("explanation") or {}
                if explanation.get("kind") == "query" and explanation.get("path"):
                    explanations |= dict.fromkeys(
                        (explanation["path"], c["step"]) for c in causes
                    )
        if mine:
            out.append(
                CauseAsk(
                    d,
                    mine,
                    rows,
                    (leads or {}).get(d.comparison, ""),
                    tuple(explanations),
                )
            )
    return out


def _explanation_changed(explanation: dict | None, base: Path | None = None) -> bool:
    """A stored explanation's file is gone, or no longer the explanation the sort ran.

    The recorded path is relative to the validation file's directory, `base`.
    Compared by `explain.fingerprint`, so a formatting-only edit is no change.
    """
    if not explanation or not explanation.get("path"):
        return False
    from . import explain

    path = Path(explanation["path"])
    if base is not None and not path.is_absolute():
        path = base / path
    return explain.file_fingerprint(path) != explanation.get("fingerprint")


def posted_sort(loaded: dict) -> dict:
    """A sort as the review issue may quote it: each item's masked evidence.

    `evidence` in `sort.json` shows exact counts for the analyst;
    `evidence_posted` holds the same lines masked (`report.shown_counts`).
    """
    return {
        **loaded,
        "items": [
            {**item, "evidence": item.get("evidence_posted", item.get("evidence", []))}
            for item in loaded.get("items", [])
        ],
    }


def _candidates(caption: str, docs: dict[str, MemberDoc]) -> tuple[str, ...]:
    """Name the non-measure members whose name, title or description holds the
    caption."""
    wanted = name_tokens(caption)
    if not wanted:
        return ()
    return tuple(
        sorted(
            name
            for name, d in docs.items()
            if d.kind != "measure"
            and wanted <= name_tokens(f"{name} {d.title} {d.description}")
        )
    )


# The model reference docs a lead names (`doc_leads`).
DOCS_DIR = Path(__file__).resolve().parents[2] / "docs" / "models"


def _bare(table: str | None) -> str:
    return (table or "").rsplit(".", 1)[-1]


def doc_leads(cfg: ViewConfig, docs_dir: Path = DOCS_DIR) -> dict[str, str]:
    """Per comparison, 1 lead naming the model docs on its dashboard or fact.

    A doc is a `docs_dir/*.md` file that names the comparison's dashboard
    model or the view's Cube fact as a whole word. Such a doc states the
    filters and joins a missing row passes through; a member description
    never has. A comparison no doc names has no lead.
    """
    files = sorted(docs_dir.glob("*.md")) if docs_dir.is_dir() else []
    texts = {f: f.read_text(encoding="utf-8") for f in files}
    shown = f"{docs_dir.parent.name}/{docs_dir.name}"
    out = {}
    for c in cfg.comparisons:
        names = list(
            dict.fromkeys(n for n in (_bare(c.dashboard_view), _bare(cfg.fact)) if n)
        )
        found = []
        for f, text in texts.items():
            hit = [n for n in names if re.search(rf"(?<!\w){re.escape(n)}(?!\w)", text)]
            if hit:
                found.append(f"{shown}/{f.name} (mentions {', '.join(hit)})")
        if found:
            out[c.id] = f"lead: read {', '.join(found)}"
    return out


NOT_TRACED = "not traced (`sort --no-trace`)"
NO_FILTER = "no `dashboard_filters` entry names the filter that drops these rows"


def _filter_cause(
    comparison: Comparison | None, g: Group
) -> tuple[list[dict], tuple[str, ...], tuple[str, ...], dict] | None:
    """A dashboard-filtered group's cause, from the run's reconcile.

    The reconcile found every row present with the comparison's
    `dashboard_filters` entry off and absent with it on.

    Returns:
        The cause, its evidence, the posted copy and the explanation; None when no
        entry names the group's filter.
    """
    column = g.value_of("dashboard_filter") or ""
    entry = next(
        (
            e
            for e in (comparison.dashboard_filters if comparison else [])
            if e["dashboard"] == column
        ),
        None,
    )
    if comparison is None or entry is None:
        return None
    # The sheet filter's caption, when the rebuild check maps it to this column.
    captions = {
        c: caption
        for caption, c in (
            (comparison.rebuild_check.missing_columns or {})
            if comparison.rebuild_check
            else {}
        ).items()
    }
    label = f"sheet filter {captions.get(column, column)}"
    sql = pipeline.dashboard_filter_sql(entry)
    cause = [
        {
            "side": "dashboard",
            "step": f"dashboard:filter:{column}",
            "label": label,
            "n_rows": g.n_rows,
        }
    ]
    return (
        cause,
        (f"the run's reconcile: {label} ({sql}) drops all {g.n_rows} rows",),
        (f"the run's reconcile: {label} ({sql}) drops every row",),
        reconcile_explanation(entry),
    )


def reconcile_explanation(entry: dict) -> dict:
    """The explanation of a dashboard-filtered group: the filter the reconcile ran.

    Its fingerprint is the `dashboard_filters` entry's, so editing the filter
    re-opens the decisions made on it.
    """
    text = json.dumps(entry, sort_keys=True, default=str)
    return {
        "kind": "reconcile",
        "fingerprint": hashlib.sha256(text.encode()).hexdigest(),
    }


_FORMULA_CAUSE = {
    "side": "both",
    "step": "formula",
    "label": FORMULA_LABEL,
    "n_rows": None,
}


def formula_evidence(
    run: RunResult, diff: CellDiff
) -> tuple[list[dict], tuple[str, ...], tuple[str, ...]]:
    """A formula difference's cause, local evidence and posted evidence.

    One line per origin: cells no unmatched row lies in, and cells the formula
    check filed (`matched_only`), each count masked when posted. With the
    latter, the local evidence also names each formula cell's cut and dims
    from `run.diff_cells`, tagged with its origin; the posted evidence never
    names a cell. A run saved without origins tags no line, since its tags
    would not add up to `matched_only`.
    """
    matched = diff.matched_only
    free = sum(diff.counts.values()) - matched
    origins = [
        (free, f"{FORMULA_LABEL}: every row in them matched on both sides"),
        (
            matched,
            f"{MATCHED_LABEL}: with their unmatched rows left out, the 2 sides "
            "still differ",
        ),
    ]
    evidence = tuple(f"{n} {tail}" for n, tail in origins if n)
    posted = tuple(f"{mask(n)} {tail}" for n, tail in origins if n)
    if matched:
        cells = [
            c
            for c in run.diff_cells
            if c["comparison"] == diff.comparison_id and c.get("kind") == "formula"
        ]
        tagged = sum(_checked_cell(c) for c in cells) == matched
        evidence += tuple(
            f"cell {c['cut']} {c['key']}" + (f" ({_cell_origin(c)})" if tagged else "")
            for c in cells
        )
    cause = {**_FORMULA_CAUSE, "label": MATCHED_LABEL if matched else FORMULA_LABEL}
    return [cause], evidence, posted


def _checked_cell(cell: dict) -> bool:
    """Whether the formula check filed this `run.diff_cells` cell."""
    return cell.get("origin") == FORMULA_CHECK


def _cell_origin(cell: dict) -> str:
    """A formula cell's origin, as its local evidence line names it."""
    return "filed by the formula check" if _checked_cell(cell) else "no unmatched row"


def _formula_explanation(run: RunResult, comparison: str) -> dict:
    """A formula difference's explanation: the comparison's SQL fingerprints in the
    run, whose reconcile matched every row in its cells."""
    text = json.dumps(run.fingerprints.get(comparison) or {}, sort_keys=True)
    return {"kind": "formula", "fingerprint": hashlib.sha256(text.encode()).hexdigest()}


NO_ROWS = (
    "values differ on rows both sides have: no trace; explain them with "
    "`explain --bucket value_differs`"
)
NO_GRAIN = "not traced: the comparison has no `rows` grain"
MOVED_ROWS = (
    "rows both sides hold sit in different cells, by a column or by a cut "
    "(Cube's columns, then the dashboard's as `d:`): no trace; explain them with "
    "`explain --bucket dims_differ`"
)


def _filter_label(
    cfg: ViewConfig, gap: Gap, candidates: tuple[str, ...]
) -> tuple[str, str]:
    """A sheet filter's evidence label and default call, from names alone.

    A candidate member wins, even for a workbook calc: a name match is a
    lead, so the label says to check before mapping. Without one, the
    `missing_columns` of the gap's own comparisons' rebuild checks tell a
    workbook-only field from a gap in Cube.
    """
    if candidates:
        names = ", ".join(f"`{m}`" for m in candidates)
        return (
            f"Cube offers it as {names}, unmapped: "
            "check before mapping it under `filters:`",
            "",
        )
    if not _missing_column(cfg, gap.field, gap.comparisons):
        return "Workbook-only field: no datasource column behind it", "deliberate"
    return "Cube has no member: a gap", "fix_cube"


def suggest(
    cfg: ViewConfig,
    run: RunResult,
    docs: dict[str, MemberDoc],
    values: Callable[[str, str], str] | None = None,
    traces: dict[tuple, trace.ItemTrace] | None = None,
    leads: dict[str, str] | None = None,
) -> list[Suggestion]:
    """Sort each open item into a pile, first matching rule wins.

    Args:
        cfg: The view's config, for each comparison's measure, group-by
            columns and rebuild check.
        run: One view's validation run.
        docs: The view's members by bare name, from `member_docs`, for a
            missing filter's candidate members.
        values: `values(caption, member)` returns a value-check verdict;
            `None` skips value checks.
        traces: Each traced row group's trace, by `trace.item_key`; `None`
            when the trace was skipped.
        leads: Per comparison, the line naming its model docs (`doc_leads`).

    Returns:
        One suggestion per open item, ordered by `SUGGESTIONS`. A missing
        filter the rebuild check shows filters nothing, or whose values match a Cube
        member's, takes `filters_nothing` or `map_filters`; any other missing
        cut or filter is `cause`, a sheet step on the dashboard side, and so
        is a group the sheet's dashboard-only filter drops, and a formula
        difference, on the run's matched rows (its count masked in `posted`).
        Every other item is `investigate`, with the trace's leads and its
        comparison's doc lead as evidence. Member descriptions are never
        evidence here: they have not explained a missing row.
    """
    by_id = {c.id: c for c in cfg.comparisons}
    entries = open_entries(run)
    out = []
    for item, source in entries:
        evidence: tuple[str, ...] = ()
        verdict_lines: tuple[str, ...] = ()
        candidates: tuple[str, ...] = ()
        call = ""
        default_call = ""
        cause: list[dict] | None = None
        explanation: dict | None = None
        found: tuple[str, ...] = ()
        # The same lines masked, for the review issue (`posted`).
        posted: tuple[str, ...] | None = None
        posted_found: tuple[str, ...] | None = None

        if isinstance(source, Gap):
            gap = source
            caption = gap.field
            candidates = _candidates(caption, docs)
            # Only the sheets the gap sits on speak for it; a rebuild check that
            # predates `restricting_filters` leaves the answer unknown.
            checks: list[RebuildCheck] = [
                p
                for c in gap.comparisons
                if c in by_id and (p := by_id[c].rebuild_check)
            ]
            notes = {k: v for p in checks for k, v in (p.filter_notes or {}).items()}
            all_known = bool(checks) and all(
                p.restricting_filters is not None for p in checks
            )
            restricting = {f for p in checks for f in p.restricting_filters or []}
            if gap.kind == "filter" and caption in notes:
                call, evidence = "filters_nothing", (notes[caption],)
            elif gap.kind == "filter" and all_known and caption not in restricting:
                call = "filters_nothing"
                evidence = (f"keeps every member on {', '.join(gap.sheets)}",)
            else:
                verdicts = (
                    [(m, values(caption, m)) for m in candidates] if values else []
                )
                verdict_lines = tuple(f"{m}: {v}" for m, v in verdicts if v)
                if any(v.startswith("same values") for _, v in verdicts):
                    call, evidence = "map_filters", verdict_lines
                else:
                    # The workbook carries it: that is the explanation. Whether
                    # Cube needs it is the owner's call on an explained step.
                    step = f"sheet {gap.kind} {caption}"
                    call, explanation = "cause", {"kind": "workbook"}
                    cause = [
                        {
                            "side": "dashboard",
                            "step": step,
                            "label": step,
                            "n_rows": None,
                        }
                    ]
                    sheets = ", ".join(gap.sheets)
                    evidence = (
                        f"{sheets} carries it; Cube has no member for it",
                        *verdict_lines,
                    )
        else:
            comparison = by_id.get(item.comparison)
            if isinstance(source, Group):
                traced = (traces or {}).get(trace.item_key(source))
                if source.bucket == "dashboard_filtered":
                    # The run's reconcile explained each row: the sheet's own
                    # dashboard-only filter drops it. No trace is needed.
                    filtered = _filter_cause(comparison, source)
                    if filtered:
                        call = "cause"
                        cause, evidence, posted, explanation = filtered
                    else:
                        found = (NO_FILTER,)
                elif traced is not None:
                    # The trace is a lead: a person explains the cause with
                    # `explain`.
                    found, posted_found = traced.leads(), traced.leads(posted=True)
                elif traces is None:
                    found = (NOT_TRACED,)
                elif source.bucket == "value_differs":
                    found = (NO_ROWS,)
                elif source.bucket == "dims_differ":
                    found = (MOVED_ROWS,)
                else:
                    found = (NO_GRAIN,)
            elif source.kind == "formula":
                # The run's own reconcile matched every row in these cells, or
                # the formula check recomputed them on matched rows alone, so
                # the 2 formulas differ: no explanation file is needed.
                call, explanation = (
                    "cause",
                    _formula_explanation(run, source.comparison_id),
                )
                cause, evidence, posted = formula_evidence(run, source)

        if not call:
            call = "investigate"
            lead = (leads or {}).get(item.comparison)
            rest = verdict_lines + (
                (lead,) if lead and not isinstance(source, Gap) else ()
            )
            evidence = found + rest
            posted = (posted_found if posted_found is not None else found) + rest
        if posted is None:
            posted = evidence

        if isinstance(source, Gap) and source.kind == "filter":
            label, default_call = _filter_label(cfg, source, candidates)
            evidence, posted = (label, *evidence), (label, *posted)

        out.append(
            Suggestion(
                item,
                call,
                evidence,
                candidates,
                cause,
                explanation,
                posted,
                default_call=default_call,
            )
        )

    return sorted(out, key=lambda s: SUGGESTIONS.index(s.suggestion))


# --- the printed batch -------------------------------------------------------

# Items listed per suggestion; `sort.json` keeps them all.
BATCH_CAP = 25


def _counts(counter: Counter, order: tuple[str, ...] = ()) -> str:
    """`k n` pairs in `order`, then by name."""
    rank = {k: i for i, k in enumerate(order)}
    keys = sorted(counter, key=lambda k: (rank.get(k, len(order)), k))
    return ", ".join(f"{k} {counter[k]:,}" for k in keys)


def batch_lines(run: RunResult, found: list[Suggestion]) -> list[str]:
    """The lines `sort` prints: a summary, a blank line, then the items.

    The summary counts each comparison's items by suggestion and by kind, and
    its row groups by bucket. Each suggestion then lists its first
    `BATCH_CAP` items with their evidence and says how many more
    `sort.json` holds.
    """
    buckets = {i.id: g.bucket for i, g in open_entries(run) if isinstance(g, Group)}
    lines = ["Summary"]
    for comparison in dict.fromkeys(s.item.comparison for s in found):
        mine = [s for s in found if s.item.comparison == comparison]
        lines.append(f"  {comparison or '(no comparison)'}: {len(mine):,} items")
        by_pile = _counts(Counter(s.suggestion for s in mine), SUGGESTIONS)
        lines.append(f"    by suggestion: {by_pile}")
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
            if s.default_call:
                lines.append(f"    default call: {s.default_call}")
        if len(group) > BATCH_CAP:
            lines.append(f"  … {len(group) - BATCH_CAP:,} more in {FILE}")
    return lines


def _as_json(s: Suggestion) -> dict:
    """One item as `sort.json` holds it."""
    return {
        **dataclasses.asdict(s.item),
        "suggestion": s.suggestion,
        "evidence": list(s.evidence),
        "evidence_posted": list(s.posted if s.posted is not None else s.evidence),
        "candidates": list(s.candidates),
        "cause": s.cause,
        "explanation": s.explanation,
        "decisions": s.decisions,
        "decided": s.decided,
        "default_call": s.default_call,
    }


def _from_json(d: dict) -> Suggestion:
    return Suggestion(
        Item(
            d["id"], d["kind"], d["comparison"], d["label"], d["stub"], d.get("key", "")
        ),
        d["suggestion"],
        tuple(d["evidence"]),
        tuple(d["candidates"]),
        d["cause"],
        d.get("explanation"),
        tuple(d["evidence_posted"]),
        d.get("decisions"),
        d.get("decided"),
        d.get("default_call", ""),
    )


# --- value checks and the command --------------------------------------------

# A column with more distinct values than this is a key, not a coding.
REFERENCE_MAX_VALUES = 50
ID_SUFFIXES = ("_number", "_id", "_name", "_email")
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
    """The dashboard table behind `column`: the comparison that names it, else
    the first."""
    for c in cfg.comparisons:
        if (
            c.rebuild_check
            and column in (c.rebuild_check.missing_columns or {}).values()
        ):
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
    `sort.json` or the evidence.

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
        or member.endswith(ID_SUFFIXES)
        or column.endswith(ID_SUFFIXES)
        or not _SQL_NAME.fullmatch(column)
        or not _TABLE.fullmatch(table)
    ):
        return _NOT_COMPARED

    dataset, name = table.split(".")
    sql = (
        # trunk-ignore(bandit/B608): the names are checked against _SQL_NAME and _TABLE
        f"SELECT DISTINCT CAST({column} AS STRING) AS value "
        f"FROM `{PROJECT}`.`{dataset}`.`{name}` "
        f"WHERE {column} IS NOT NULL LIMIT {REFERENCE_MAX_VALUES + 1}"
    )
    dash = {
        str(r["value"])
        for r in wh.rows(pipeline.checked_as_of(sql, moment.start, wh).sql)
    }
    if len(dash) > REFERENCE_MAX_VALUES:
        return _NOT_COMPARED

    key = f"{cfg.view}.{member}"
    rows = pipeline.priced_load(
        cube, wh, {"dimensions": [key], "limit": REFERENCE_MAX_VALUES + 1}
    )
    # Count before dropping nulls: a null can fill the limit and cut the set short.
    if len(rows) > REFERENCE_MAX_VALUES:
        return _NOT_COMPARED
    theirs = {str(r[key]) for r in rows if r.get(key) is not None}

    if dash == theirs:
        return _SAME
    if not (is_identifier(member) or is_identifier(column)):
        print(f"  {member}: dashboard {sorted(dash)} vs Cube {sorted(theirs)}")
    return _CODING


def _missing_column(
    cfg: ViewConfig, caption: str, comparisons: Iterable[str] | None = None
) -> str:
    """The datasource column behind a missing field, or empty when no rebuild
    check names it.

    With `comparisons`, only their rebuild checks are read.
    """
    wanted = None if comparisons is None else set(comparisons)
    for c in cfg.comparisons:
        if wanted is not None and c.id not in wanted:
            continue
        if c.rebuild_check and caption in (c.rebuild_check.missing_columns or {}):
            return (c.rebuild_check.missing_columns or {})[caption]
    return ""


def with_closed(run: RunResult) -> RunResult:
    """The run with its closed groups listed as open, for the stored explanations.

    An explanation reads every unmatched row of its bucket already, so classifying
    the closed groups too only adds their keys; `closed_groups` splits the
    result back.
    """
    quiet = [g for _, g in run.applied.quiet]
    return dataclasses.replace(
        run,
        applied=dataclasses.replace(run.applied, open=[*run.applied.open, *quiet]),
    )


def closed_groups(run: RunResult, ran: list, cfg: ViewConfig) -> tuple[list, list]:
    """Split the explanations' runs over `with_closed(run)` into open and closed groups.

    Args:
        run: The run as the sort lists it.
        ran: `explain.run_stored`'s runs over `with_closed(run)`.
        cfg: The view's config, for a dashboard-filtered group's filter.

    Returns:
        The runs over the open groups only, under their own item ids, as
        `explain.apply_runs` reads them (a run over closed groups alone is
        dropped), and the closed groups an explanation fully explains, or a
        `dashboard_filters` entry drops, each as an item `mark_decided`
        reads, marked `closed` and named by its `open_key`.
    """
    from . import explain

    open_ids = {i.key: i.id for i, g in open_entries(run) if isinstance(g, Group)}
    quiet = _quiet_by_key(run)
    kept, closed = [], []
    for r in ran:
        mine = [
            (open_ids[open_key(g)], g) for _, g in r.items if open_key(g) in open_ids
        ]
        if mine:
            found = r.found and {
                open_ids[open_key(g)]: r.found[i]
                for i, g in r.items
                if open_key(g) in open_ids
            }
            kept.append(dataclasses.replace(r, items=mine, found=found))
        if not r.found:
            continue
        shut = {open_key(g): r.found[i] for i, g in r.items if open_key(g) in quiet}
        entries = [_closed_item(quiet[k]) for k in shut]
        explain.apply_outcomes(entries, r.explanation, shut)
        closed += [e for e in entries if e["suggestion"] == "cause"]
    by_id = {c.id: c for c in cfg.comparisons}
    for g in quiet.values():
        if g.bucket == "dashboard_filtered" and (
            filtered := _filter_cause(by_id.get(g.comparison_id), g)
        ):
            cause, _, _, explanation = filtered
            closed.append({**_closed_item(g), "suggestion": "cause", "cause": cause,
                           "explanation": explanation})  # fmt: skip
    # 2 explanations, or an explanation and a sheet filter, can explain one
    # closed group.
    closed = list(
        {json.dumps([e["key"], e["explanation"]]): e for e in closed}.values()
    )
    return kept, [
        {k: e[k] for k in ("id", "key", "kind", "comparison", "closed", "suggestion",
                           "cause", "explanation")}
        for e in closed
    ]  # fmt: skip


def _closed_item(g: Group) -> dict:
    key = open_key(g)
    return {"id": key, "key": key, "kind": "group", "comparison": g.comparison_id,
            "closed": True, "suggestion": "investigate", "evidence": [],
            "evidence_posted": [], "cause": None, "explanation": None}  # fmt: skip


def sort_run(
    cfg: ViewConfig,
    *,
    wh: Warehouse,
    cube: Cube,
    max_usd: float,
    cache_root: Path,
    trace_rows: bool = True,
    manifest: Path | None = None,
    trace_max_minutes: float | None = None,
    explanations: Path | None = None,
    comparisons: list[str] | None = None,
    now: datetime | None = None,
    ticker: Ticker | None = None,
) -> list[Suggestion]:
    """Sort each open item of the view's latest run into a pile and print them.

    Re-runs every stored explanation in `explanations` on the run's rows
    first (`explain.run_stored`; None skips them): only an explanation moves a
    row group to `cause`. Then traces the row groups no explanation explains
    (`trace.trace_run`) unless `trace_rows` is False, for leads. Both count
    against `max_usd` and the daily cap with the value checks. A cap or
    `trace_max_minutes` hit partway stops the trace; what it found is kept and
    the batch is still written, as it is when an explanation cannot run.
    Prints `batch_lines`. Writes every item to `sort.json` beside that run's
    `run.json`, with the run's moment, decisions fingerprint and open items
    (see `checked_sort`), each explained row group marked by the cause
    decisions that decide it (`mark_decided`): it stays in the local cache,
    and its stubs and causes carry real values and exact counts.

    Each confirmed comparison whose result in the run is missing or stale at
    `now` (`results.stale_comparisons` over `results.composed_results`),
    whose SQL cannot be built today, or which the run skipped (`not compared:
    <why>`), is printed and written to `sort.json` under `stale`, so
    `comparisons_waiting` can name it. Such a comparison's row groups are
    neither checked for the trace nor traced: its SQL may not build today, or
    not as the run reconciled it.

    Each explanation's outcome is kept beside `run.json` as it finishes
    (`explain_progress`), so a stopped sort skips the explanations it
    finished. With `comparisons`, only their explanations run and only their
    row groups are traced or printed; `sort.json` still holds every item,
    the others' from their kept explanation outcomes.

    Each confirmed comparison with `rows` that is not stale also gets the
    formula check (`formula.plan`): its differing cells holding row groups are
    recomputed on the rows both sides matched. Its queries (`formula.Job`)
    are dry-run and priced with the explanations, so one cap refusal comes
    before either runs. A check is kept beside its comparison's latest result
    (`latest.add_formula_check`) and reused while that result stands, unless
    it is of an older `formula.CHECK_VERSION`: that one runs again, and if it
    then cannot run, its kept verdicts stand. A
    cell still differing there joins the comparison's formula item once the
    run is composed again (`results.recompose`). Outside `comparisons`, a
    kept check is reused as it is and a comparison with none is not checked.
    A check that cannot run, for any reason, never refuses the sort or makes
    the comparison stale: its cells stay with coverage, and the cell set's
    evidence says why (`formula.label`), as does `sort.json` under
    `formulas_not_compared`.

    `ticker` (a new one by default) prints a progress line after each
    explanation runs and after each level of the trace.

    Raises:
        pipeline.Refusal: The view has no usable saved run (see
            `results.latest_run`), its SQL changed since the run, the
            manifest lacks compiled SQL the trace needs, or a comparison asked
            for is not in the view.
        CostCapError: The value checks, the explanations and the formula
            check together, or the trace would pass a cap.
    """
    wanted = set(comparisons) if comparisons else None
    if wanted and (unknown := wanted - {c.id for c in cfg.comparisons}):
        raise pipeline.Refusal(
            f"--comparison: {', '.join(sorted(unknown))} is no comparison of {cfg.view}"
        )
    run, run_json = results.latest_run(cfg, cache_root)
    meta = cube.meta()
    docs = member_docs(meta, cfg.view)
    pii = pii_members(meta, cfg.view)

    def values(caption: str, member: str) -> str:
        column = _missing_column(cfg, caption)
        if not column:
            return ""
        try:
            return value_check(wh, cube, cfg, column, member, run.moment, pii)
        except CostCapError as exc:
            # The trace's paid work is kept: the batch is still written.
            return f"not checked: {exc}"

    from . import explain, formula

    ticker = ticker or Ticker(utcnow, utcnow())
    prepared = trace.Prepared()
    with wh.budget(max_usd):
        prepared.schools = network_schools(wh)
        # Judged from what the run was composed from, which a stopped run
        # can leave older than `latest/`. A comparison the run skipped is
        # named by why; its SQL may not build today.
        skipped = {s["comparison"]: s["why"] for s in run.skipped}
        stale = results.stale_comparisons(
            cfg,
            [c for c in cfg.comparisons if c.id not in skipped],
            results.composed_results(cfg, run),
            wh=wh,
            cube=cube,
            schools=prepared.schools,
            now=now or utcnow(),
        )
        # A comparison `compare` skipped keeps its older result: say why.
        stale |= {cid: f"{NOT_COMPARED}: {why}" for cid, why in skipped.items()}
        for cid, why in stale.items():
            print(f"{cfg.view}: comparison {cid} {why}; compare it, then sort.")
        if trace_rows:
            # A trace refusal after the explanations ran would throw their spend away.
            trace.check_ready(
                cfg,
                run,
                wh=wh,
                cube=cube,
                manifest_path=manifest or trace.MANIFEST,
                prepared=prepared,
                skip=_groups_of(run, set(stale)),
            )
        checks, jobs, usd = _formula_jobs(
            cfg, run, run_json, cache_root, stale, wanted,
            wh=wh, cube=cube, prepared=prepared,
        )  # fmt: skip
        if explanations is None and usd:
            wh.refuse_past_caps(usd)
        # Explanations first: they are the only path to `cause`, so a trace that
        # hits a cap never un-explains an item, and nothing they explain is
        # traced.
        # Closed groups go through the explanations too, so a cause decision that
        # disagrees with the `group` decision closing one refuses when it is
        # written (`check_closed`).
        ran, closed = closed_groups(
            run,
            explain.run_stored(
                cfg,
                with_closed(run),
                explanations,
                wh=wh,
                cube=cube,
                prepared=prepared,
                progress_dir=run_json.parent,
                comparisons=wanted,
                ticker=ticker,
                also_usd=usd,
            )
            if explanations is not None
            else [],
            cfg,
        )
        run = _run_formula_jobs(
            cfg, run, run_json, cache_root, checks, jobs, wh=wh, cube=cube,
            ticker=ticker,
        )  # fmt: skip
        traced = (
            trace.trace_run(
                cfg,
                run,
                wh=wh,
                cube=cube,
                manifest_path=manifest or trace.MANIFEST,
                max_minutes=trace_max_minutes or trace.TRACE_MAX_MINUTES,
                skip=explain.explained(ran)
                | _outside(run, wanted)
                | _groups_of(run, set(stale)),
                prepared=prepared,
                ticker=ticker,
            )
            if trace_rows
            else None
        )
        found = suggest(
            cfg, run, docs, values, traced.items if traced else None, doc_leads(cfg)
        )
        items = [_as_json(s) for s in found]
        kept: dict = {}
        if explanations is not None:
            explain.apply_runs(run, items, ran, cfg, kept)
            items.sort(key=lambda i: SUGGESTIONS.index(i["suggestion"]))
        unchecked = formula.label(items, checks)
        mark_decided(run, items, cfg.decisions, note=True)
        found = [_from_json(i) for i in items]

    out = run_json.parent / FILE
    checkpoints.write_text(
        out,
        json.dumps(
            {
                "view": run.view,
                "moment": _moment(run),
                "decisions_fingerprint": run.decisions_fingerprint,
                "open": open_keys(run),
                "items": items,
                # Groups a `group` decision closes, with the causes an explanation
                # gives them (`closed_groups`), for `check_closed`.
                "closed": closed,
                # Per comparison, each explained cause's students per cell and
                # cut, from the explanations' counting queries (`ask-owner` examples).
                "cause_students": kept.get("cause_students", {}),
                # Each comparison whose latest result is missing or stale.
                "stale": stale,
                # Per comparison, the cells the formula check left to coverage,
                # counted per reason (`formula.label`).
                "formulas_not_compared": unchecked,
                # The masking rule its posted lines were written under.
                "posted_version": POSTED_VERSION,
            },
            indent=1,
        ),
    )

    shown = found
    if wanted:
        shown = [s for s in found if s.item.comparison in wanted]
        print(
            f"Showing {', '.join(sorted(wanted))} (--comparison); "
            f"{len(found) - len(shown):,} other items are in {out.name}."
        )
    print("\n".join(batch_lines(run, shown)))
    print(f"Saved {out}")
    return found


def stored_check(held: latest.Latest) -> Check | None:
    """The formula check kept beside a result, when it checked that very result.

    The one reading of a kept check, for `sort` to reuse it and for
    `results.compose_run` to file its cells. A check that cannot be read
    whole counts as none, so it never stops a sort or a compose.
    """
    from . import formula

    data = held.data.get("formula_check")
    if not isinstance(data, dict) or data.get("fingerprint") != held.fingerprint:
        return None
    try:
        return formula.Check.from_json(data)
    except (AttributeError, KeyError, TypeError, ValueError):
        return None


def _formula_jobs(
    cfg: ViewConfig,
    run: RunResult,
    run_json: Path,
    cache_root: Path,
    stale: dict[str, str],
    wanted: set[str] | None,
    *,
    wh: Warehouse,
    cube: Cube,
    prepared: trace.Prepared,
) -> tuple[dict[str, Check], list[Job], float]:
    """Plan and price the formula check of each comparison that can take one.

    A kept check of the latest result is reused when it is of this
    `formula.CHECK_VERSION`, or outside `wanted`; any other is run again, and
    when that one falls back the kept check's verdicts stand.

    Returns:
        The checks already decided, by comparison (kept ones reused, and
        every fallback); the jobs to run, each dry-run without error; and
        their summed dry-run price.
    """
    from . import formula

    confirmed = [c for c in cfg.comparisons if c.confirmed]
    held = latest.read_all(latest.folder(cache_root / cfg.view, cfg.fact), cfg.fact)
    composed = results.composed_from(json.loads(run_json.read_text()), confirmed, held)
    checks: dict[str, formula.Check] = {}
    jobs: list[formula.Job] = []
    for c in confirmed:
        if c.rows is None or c.id in stale:
            continue
        if not composed or c.id not in held:
            # The check would be kept beside results the run was not composed
            # from, and filed by a compose that would replace the run.
            if cells := formula.checkable_cells(run, c):
                checks[c.id] = formula.not_compared(
                    c.id, "", cells, formula.NOT_COMPOSED
                )
            continue
        fingerprint = held[c.id].fingerprint
        outside = bool(wanted) and c.id not in wanted
        # A kept check of this version would decide its cells the same while
        # its result stands, so only a validator update runs it again (a new
        # result drops it); outside --comparison it stays as it is.
        if (kept := stored_check(held[c.id])) is not None and (
            outside or kept.version == formula.CHECK_VERSION
        ):
            checks[c.id] = kept
            continue
        if outside:
            if cells := formula.checkable_cells(run, c):
                checks[c.id] = formula.not_compared(
                    c.id, fingerprint, cells, formula.OUTSIDE
                )
            continue
        planned = formula.plan(
            cfg, run, c, fingerprint=fingerprint, wh=wh, cube=cube, prepared=prepared
        )
        if isinstance(planned, formula.Job):
            planned.stored = kept
            jobs.append(planned)
        elif planned is not None:
            checks[c.id] = _fallen_back(kept, planned)
    ready: list[formula.Job] = []
    usd = 0.0
    for job in jobs:
        # One job at a time, so an error outside BigQuery (expired
        # credentials, say) stops only its own check.
        try:
            mine = trace.dry_runs(wh, list(job.sql.values()))
        except Exception as exc:  # noqa: BLE001 - the check never stops `sort`
            print(f"Formula check of {job.comparison} not priced: {exc!r}")
            checks[job.comparison] = _fallen_back(
                job.stored, formula.not_compared(
                    job.comparison, job.fingerprint, job.cells, formula.RUN_FAILED
                ),
            )  # fmt: skip
            continue
        if failed := [p for p in mine if isinstance(p, GoogleAPIError)]:
            checks[job.comparison] = _fallen_back(
                job.stored, formula.not_compared(
                    job.comparison, job.fingerprint, job.cells,
                    formula.bigquery_refused(failed[0]),
                ),
            )  # fmt: skip
            continue
        usd += sum(p for p in mine if not isinstance(p, GoogleAPIError))
        ready.append(job)
    if ready:
        n = sum(len(j.sql) for j in ready)
        print(f"Formula check: {n} queries, ${usd:.2f} (dry run).")
    return checks, ready, usd


def _fallen_back(stored: Check | None, check: Check) -> Check:
    """`check`, a fallback, unless it runs `stored`, a kept check, again: then
    the kept check's verdicts stand, so no cell it decided reads as not
    compared, and a line names the fallback's reasons (fixed text, no value).
    Neither is kept anew."""
    if stored is None:
        return check
    why = "; ".join(check.not_compared)
    print(
        f"Formula check of {check.comparison}: kept the stored check; this run "
        f"fell back: {why}"
    )
    return stored


def _run_formula_jobs(
    cfg: ViewConfig,
    run: RunResult,
    run_json: Path,
    cache_root: Path,
    checks: dict[str, Check],
    jobs: list[Job],
    *,
    wh: Warehouse,
    cube: Cube,
    ticker: Ticker,
) -> RunResult:
    """Run the priced formula checks into `checks`, keep each that ran, and
    compose the run again when a check files a cell the run does not, or
    one the run files without its origin.

    Returns:
        The run, composed again when a check filed a formula cell; else as
        given. When composing refuses or fails (the error printed), the run
        is kept; if a check's cell is not filed, each check just run, or not
        yet filed, reads `formula.NOT_COMPOSED`, and the kept checks stay
        for the next compose. A run that files every cell, only without
        origins, keeps every check as it is and its local lines untagged.
    """
    from . import formula

    by_id = {c.id: c for c in cfg.comparisons}
    results_dir = latest.folder(cache_root / cfg.view, cfg.fact)
    just_ran: set[str] = set()
    for job in jobs:
        check = formula.run_job(job, by_id[job.comparison], wh)
        ticker.say("sort formula", job.comparison, wh.spent)
        if formula.ran(check):
            latest.add_formula_check(results_dir, job.comparison, check.to_json())
            just_ran.add(job.comparison)
        else:
            check = _fallen_back(job.stored, check)
        checks[job.comparison] = check
    filed = {
        (c["comparison"], c["cut"], c["key"]): _checked_cell(c)
        for c in run.diff_cells
        if c.get("kind") == "formula"
    }
    unfiled = {
        cid
        for cid, check in checks.items()
        if any((cid, cut, key) not in filed for cut, key in check.formula)
    }
    # Filed without its origin: a run saved without origins, composed again
    # only so its local evidence is tagged.
    untagged = any(
        filed.get((cid, cut, key)) is False
        for cid, check in checks.items()
        for cut, key in check.formula
    )
    if not unfiled and not untagged:
        return run
    what = "not filed" if unfiled else "not tagged with their origin"
    try:
        return results.recompose(cfg, cache_root, run, run_json, cube=cube)
    except pipeline.Refusal as exc:
        print(f"Formula check: its cells are {what}: {exc}.")
    except Exception as exc:  # noqa: BLE001 - the checks are paid for; keep sorting
        print(f"Formula check: its cells are {what}: {exc!r}")
    if not unfiled:
        # The run already files every cell; only its local tags are missing.
        return run
    for cid in just_ran | unfiled:
        check = checks[cid]
        cells = [
            {"cut": cut, "key": key}
            for cut, key in [
                *check.formula,
                *check.coverage,
                *(c for cs in check.not_compared.values() for c in cs),
            ]
        ]
        checks[cid] = formula.not_compared(
            cid, check.fingerprint, cells, formula.NOT_COMPOSED
        )
    return run


def _groups_of(run: RunResult, comparisons: set[str]) -> set[tuple]:
    """The `trace.item_key` of every open row group of `comparisons`: the
    stale or skipped ones, whose SQL the trace may not build today, or not as
    the run reconciled it."""
    return {
        trace.item_key(g) for g in run.applied.open if g.comparison_id in comparisons
    }


def _outside(run: RunResult, wanted: set[str] | None) -> set[tuple]:
    """The `trace.item_key` of every row group outside `wanted`: not traced."""
    if not wanted:
        return set()
    return {
        trace.item_key(g)
        for _, g in open_entries(run)
        if isinstance(g, Group) and g.comparison_id not in wanted
    }
