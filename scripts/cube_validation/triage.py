"""Gather evidence and sort each open item of a run into a pile.

An open item is a row group, a comparison's cell differences, or a missing cut
or filter. A pile never applies a call: the analyst reads it and decides, and
an item in `investigate` blocks every decision on the view until it reaches a
proven cause. The trace (`trace.py`) only leads: a row group reaches `cause`
when `triage confirm` (`confirm.py`) checks a classification query that names
each of its unmatched rows' cause. A missing cut or filter the sheet carries,
and rows the sheet's own dashboard-only filter drops, are their own proof.
Item ids and labels carry no value the review issue would hide. `suggest` is
pure; `value_check` and `run_triage` read the warehouse and Cube.
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

from . import decisions, pipeline, trace
from .bq import CostCapError, Warehouse
from .compare import CellDiff, Gap, Group
from .config import Decision, Proof, ViewConfig, mask_digits
from .cube_client import Cube, MemberDoc, member_docs
from .discover import _tokens
from .moment import Build
from .report import (
    _CELL_WORDS,
    CauseAsk,
    RunResult,
    _gap_line,
    _is_identifier,
    _shown_value,
    _where,
)
from .timetravel import PROJECT

# The piles, in the order the analyst's batch shows them. Only a `cause` item
# carries a proven cause; an `investigate` item has none yet.
SUGGESTIONS = ("map_filters", "filters_nothing", "cause", "investigate")


@dataclass(frozen=True)
class Item:
    """One open item.

    `kind` is `group`, `cells` or `gap`. `id` and `label` hide the values the
    review issue hides; `label` shows exact counts and stays local. `stub` holds the key fields of the decision that would cover
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
    missing filter or cut may map to. `cause` is, for a `cause` item, its
    causes, each `{side, step, label, n_rows}`; it is None until one is
    proven. `proof` is, for an item `triage confirm` proved, what a re-run
    checks before keeping the cause (see `carry_confirmed`). `evidence`
    shows exact counts; `posted` is the same lines masked for the review
    issue (`report.shown_counts`), or None when it equals `evidence`.
    """

    item: Item
    suggestion: str
    evidence: tuple[str, ...]
    candidates: tuple[str, ...] = ()
    cause: list[dict] | None = None
    proof: dict | None = None
    posted: tuple[str, ...] | None = None


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
        f"{_where(g, lambda column, value: _shown_value(g, column, value))} in "
        f"{g.comparison_id} ({g.bucket}): {g.n_rows} rows, "
        f"{g.n_students} students"
    )


def _group_item(g: Group, item_id: str, open_groups: list[Group]) -> Item:
    column, value = _stub_dim(g, open_groups)
    label = _group_label(g)
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
            f"{n} {_CELL_WORDS.get(verdict, verdict)}"
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


def proven_triage(
    run: RunResult, run_json: Path, recorded: list[Decision] | None = None
) -> dict:
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
        recorded: The view's decisions. When given, each proven row group is
            marked by the cause decisions that decide it (`mark_decided`).

    Raises:
        pipeline.Refusal: No triage sits beside the run, it is unreadable or of
            another moment, the run has an open item the triage did not see,
            an item sits in a pile this validator does not sort into (a triage
            from an older validator), a `cause` item has no cause, an item is
            in `investigate`, a row group or cell set in `cause` rests on no
            proof, a proof an item rests on changed since, or a cause decision
            and a `group` decision disagree on one group.
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
            "prove each with `triage confirm` (cube-validation skill, step 8), "
            "then re-run `triage`"
        )
    # A gap's proof is the workbook XML, and a dashboard-filtered group's the
    # run's own reconcile; any other cause rests on a stored proof.
    buckets = {i.id: g.bucket for i, g in _entries(run) if isinstance(g, Group)}
    if bare := sum(
        1
        for i in items
        if i["suggestion"] == "cause"
        and i.get("kind") in ("group", "cells")
        and not i.get("proof")
        and buckets.get(i["id"]) != "dashboard_filtered"
    ):
        raise pipeline.Refusal(
            f"{view}: {bare} `cause` item{'' if bare == 1 else 's'} "
            f"rest{'s' if bare == 1 else ''} on no proof; prove "
            f"{'it' if bare == 1 else 'them'} with `triage confirm`, then re-run "
            "`triage`"
        )
    if moved := sum(1 for i in items if _proof_changed(i.get("proof"))):
        raise pipeline.Refusal(
            f"{view}: {moved} item{'' if moved == 1 else 's'} in `cause` "
            f"rest{'s' if moved == 1 else ''} on a proof file changed since "
            "triage; re-run `triage`"
        )
    if recorded is not None:
        try:
            mark_decided(run, items, recorded, refuse=True)
        except pipeline.Refusal as exc:
            raise pipeline.Refusal(f"{view}: {exc}") from exc
    return loaded


# Why a cause decision no longer decides an item it names.
_STALE = {
    "sql": "the SQL changed since the decision; re-approve",
    "proof": "proof changed since the decision; re-approve",
}


def decidable(item: dict) -> bool:
    """A row group a stored proof explains: cause decisions decide it."""
    return (
        item.get("kind") == "group"
        and item.get("suggestion") == "cause"
        and bool(item.get("cause"))
        and bool((item.get("proof") or {}).get("path"))
    )


def cause_key(side: str, label: str) -> str:
    """A cause as a decision names it: its side and its digit-masked words."""
    return f"{side}: {mask_digits(label)}"


def cause_decision(
    recorded: list[Decision], comparison: str, side: str, label: str
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


def mark_decided(
    run: RunResult,
    items: list[dict],
    recorded: list[Decision],
    *,
    refuse: bool = False,
    note: bool = False,
) -> None:
    """Mark each proven row group by the cause decisions that decide it.

    A decidable item gets `decisions`, `{cause_key: decision id or None}`, and
    `decided`, true only when every one of its causes has a decision that
    holds: the comparison's SQL and the item's proof file are the ones it was
    made on. A pair `A + B` or a fallback `A / B` is one cause. A decision
    that no longer holds counts as none.

    A holding cause decision on a group a `group` decision also covers,
    stale or not, is redundant when their calls agree and refused when they
    differ.

    Args:
        run: The run the items come from.
        items: The triage items, marked in place.
        recorded: The view's decisions.
        refuse: Raise on a disagreement instead of noting it.
        note: Add why a decision does not hold, and any redundancy or
            disagreement, to the item's evidence.

    Raises:
        pipeline.Refusal: With `refuse`, a disagreement.
    """
    groups = {i.id: g for i, g in _entries(run) if isinstance(g, Group)}
    by_group = [d for d in recorded if d.group and not d.cause]
    for item in items:
        if not decidable(item):
            continue
        current = run.fingerprints.get(item["comparison"]) or {}
        proof = item["proof"].get("fingerprint", "")
        found: dict[str, str | None] = {}
        held: list[Decision] = []
        lines: list[str] = []
        for c in item["cause"]:
            key = cause_key(c["side"], c["label"])
            d = cause_decision(recorded, item["comparison"], c["side"], c["label"])
            state = decisions.cause_state(d, proof, current) if d else ""
            found[key] = d.id if d and state == "holds" else None
            if d and state == "holds":
                held.append(d)
            elif d:
                lines.append(f"decision {d.id}: {_STALE[state]}")
        item["decisions"] = found
        item["decided"] = all(found.values())
        g = groups.get(item["id"])
        covering = [o for o in by_group if g is not None and _covers_group(o, g)]
        for other in covering:
            for d in held:
                if d.call == other.call:
                    lines.append(f"decision {d.id} repeats group decision {other.id}")
                    continue
                line = (
                    f"decisions {other.id!r} ({other.call}) and {d.id!r} "
                    f"({d.call}) disagree on item {item['id']!r}"
                )
                if refuse:
                    raise pipeline.Refusal(line)
                lines.append(line)
        if note and lines:
            evidence = item.get("evidence", [])
            posted = item.get("evidence_posted", evidence)
            item["evidence"] = [*lines, *evidence]
            item["evidence_posted"] = [*lines, *posted]


def _covers_group(d: Decision, g: Group) -> bool:
    """A `group` decision names `g`, whether or not its SQL still holds."""
    values = {"" if v is None else str(v) for v in d.group.get("values") or []}
    return (
        d.comparison == g.comparison_id
        and g.value_of(d.group.get("column") or "") in values
    )


def cause_asks(
    run: RunResult, loaded: dict, recorded: list[Decision]
) -> list[CauseAsk]:
    """What `review` asks the owner: each unanswered owner cause and its groups.

    Reads items `mark_decided` marked. A cause's rows are only those its
    proof attributes to it, so a group split across causes counts in each
    question only by its own share.
    """
    groups = {i.id: g for i, g in _entries(run) if isinstance(g, Group)}
    out = []
    for d in recorded:
        if not d.cause or d.call != "domain_owner" or d.answer:
            continue
        mine, rows = [], 0
        for item in loaded.get("items", []):
            if not decidable(item) or item["id"] not in groups:
                continue
            marks = item.get("decisions") or {}
            n = [
                c.get("n_rows") or 0
                for c in item["cause"]
                if marks.get(cause_key(c["side"], c["label"])) == d.id
            ]
            if n:
                mine.append(groups[item["id"]])
                rows += sum(n)
        if mine:
            out.append(CauseAsk(d, mine, rows))
    return out


def _proof_changed(proof: dict | None) -> bool:
    """A stored proof's file is gone, or no longer the proof triage ran.

    Compared by `confirm.fingerprint`, so a formatting-only edit is no change.
    """
    if not proof or not proof.get("path"):
        return False
    from . import confirm

    return confirm.file_fingerprint(Path(proof["path"])) != proof.get("fingerprint")


def posted_triage(loaded: dict) -> dict:
    """A triage as the review issue may quote it: each item's masked evidence.

    `evidence` in `triage.json` shows exact counts for the analyst;
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


def _involved_docs(cfg: ViewConfig, docs: dict[str, MemberDoc]) -> dict[str, list]:
    """Each comparison's measure and dims, with their description and ai_context.

    `review` reads them offline for a cause question's evidence.
    """
    members = [
        m for c in cfg.comparisons for m in (c.measure, *(p.cube for p in c.dims))
    ]
    return {
        name: texts
        for name in dict.fromkeys(members)
        if name in docs
        and (
            texts := [
                t for t in (docs[name].description, docs[name].ai_context) if t.strip()
            ]
        )
    }


NOT_TRACED = "not traced (`triage --no-trace`)"
NO_ROWS = "no rows to trace: values differ on rows both sides have"
NO_GRAIN = "not traced: the comparison has no `rows` grain"


def suggest(
    cfg: ViewConfig,
    run: RunResult,
    docs: dict[str, MemberDoc],
    values: Callable[[str, str], str] | None = None,
    traces: dict[tuple, trace.ItemTrace] | None = None,
    stopped: str = "",
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
        stopped: Why the trace stopped early, if it did: a group it did not
            reach says so.

    Returns:
        One suggestion per open item, ordered by `SUGGESTIONS`. A missing
        filter the proof shows filters nothing, or whose values match a Cube
        member's, takes `filters_nothing` or `map_filters`; any other missing
        cut or filter is `cause`, a sheet step on the dashboard side, and so
        is a group the sheet's dashboard-only filter drops. Every other item
        is `investigate`, with the trace's leads and its involved members'
        docs as evidence.
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
        # The same lines masked, for the review issue (`posted`).
        posted: tuple[str, ...] | None = None
        posted_found: tuple[str, ...] | None = None

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
                if (
                    traced is not None
                    and traced.proven
                    and source.bucket == "dashboard_filtered"
                ):
                    # The run's reconcile proved each row: the sheet's own
                    # dashboard-only filter drops it.
                    call, cause, evidence = "cause", traced.cause(), traced.evidence()
                    posted = traced.evidence(posted=True)
                elif traced is not None:
                    # The trace is a lead: a person proves the cause with
                    # `triage confirm`.
                    found, posted_found = traced.leads(), traced.leads(posted=True)
                elif traces is None:
                    found = (NOT_TRACED,)
                elif stopped and source.bucket in trace.TRACED:
                    found = (f"trace stopped: {stopped}",)
                elif source.bucket == "value_differs":
                    found = (NO_ROWS,)
                else:
                    found = (NO_GRAIN,)

        if not call:
            call = "investigate"
            rest = verdict_lines + _doc_evidence(members, docs)
            evidence = found + rest
            posted = (posted_found if posted_found is not None else found) + rest
        if posted is None:
            posted = evidence

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
                posted += (f"also covers: {', '.join(also)}",)
        out.append(Suggestion(item, call, evidence, candidates, cause, posted=posted))

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


def _as_json(s: Suggestion) -> dict:
    """One item as `triage.json` holds it."""
    return {
        **dataclasses.asdict(s.item),
        "suggestion": s.suggestion,
        "evidence": list(s.evidence),
        "evidence_posted": list(s.posted if s.posted is not None else s.evidence),
        "candidates": list(s.candidates),
        "cause": s.cause,
        "proof": s.proof,
    }


def _from_json(d: dict) -> Suggestion:
    return Suggestion(
        Item(d["id"], d["kind"], d["comparison"], d["label"], d["stub"]),
        d["suggestion"],
        tuple(d["evidence"]),
        tuple(d["candidates"]),
        d["cause"],
        d.get("proof"),
        tuple(d["evidence_posted"]),
    )


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
    manifest: Path | None = None,
    trace_max_minutes: float | None = None,
    proofs: Path | None = None,
) -> list[Suggestion]:
    """Sort each open item of the view's latest run into a pile and print them.

    Traces the run's row groups first (`trace.trace_run`) unless `trace_rows`
    is False; its queries count against `max_usd` and the daily cap with the
    value checks. A cap or `trace_max_minutes` hit partway stops the trace;
    what it found is kept and the batch is still written. Then re-runs every
    stored proof in `proofs` on the run's rows (`confirm.reprove`; None skips
    them), under the same caps: only a proof moves an item to `cause`. Prints
    `batch_lines`. Writes every item to `triage.json`
    beside that run's `run.json`, with the run's moment, decisions
    fingerprint and open items (see `proven_triage`), each proven row group
    marked by the cause decisions that decide it (`mark_decided`): it stays in the local
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
        try:
            return value_check(wh, cube, cfg, column, member, run.moment, pii)
        except CostCapError as exc:
            # The trace's paid work is kept: the batch is still written.
            return f"not checked: {exc}"

    with wh.budget(max_usd):
        traced = (
            trace.trace_run(
                cfg,
                run,
                wh=wh,
                cube=cube,
                manifest_path=manifest or trace.MANIFEST,
                max_minutes=trace_max_minutes or trace.TRACE_MAX_MINUTES,
            )
            if trace_rows
            else None
        )
        found = suggest(
            cfg,
            run,
            docs,
            values,
            traced.items if traced else None,
            traced.stopped if traced else "",
        )
        items = [_as_json(s) for s in found]
        if proofs is not None:
            from . import confirm

            confirm.reprove(cfg, run, items, proofs, wh=wh, cube=cube)
            items.sort(key=lambda i: SUGGESTIONS.index(i["suggestion"]))
        mark_decided(run, items, cfg.decisions, note=True)
        found = [_from_json(i) for i in items]

    out = run_json.parent / "triage.json"
    out.write_text(
        json.dumps(
            {
                "view": run.view,
                "moment": _moment(run),
                "decisions_fingerprint": run.decisions_fingerprint,
                "open": open_keys(run),
                "docs": _involved_docs(cfg, docs),
                "items": items,
            },
            indent=1,
        )
    )

    print("\n".join(batch_lines(run, found)))
    print(f"Saved {out}")
    return found
