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
from .config import Comparison, Decision, Proof, ViewConfig, mask_digits
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
# What a `cause` rests on: a stored classification query (`confirm.py`), the
# run's own reconcile (rows the sheet's dashboard-only filter drops), the
# workbook XML (a missing cut or filter), or proven groups (a cell set).
PROOF_KINDS = ("query", "reconcile", "workbook", "cells")


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
    # `_open_key`: what the item is, whichever siblings are open. An id's
    # `#n` can move when a sibling closes; this cannot.
    key: str = ""


@dataclass(frozen=True)
class Suggestion:
    """The pile one item lands in, with what it rests on.

    `evidence` is the quoted note, verdict, trace lead or model-doc lead;
    a lead never picks the pile. `candidates` are the Cube members a
    missing filter or cut may map to. `cause` is, for a `cause` item, its
    causes, each `{side, step, label, n_rows}`; it is None until one is
    proven. `proof` is what the cause rests on, typed by `kind`
    (`PROOF_KINDS`); a stored proof's also names its file. `evidence`
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
    # `mark_decided`'s marks: each cause's deciding decision id, and whether
    # every cause has one. None on an item no cause decision decides.
    decisions: dict[str, str | None] | None = None
    decided: bool | None = None


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
    label = _group_label(g)
    stub: dict = {"comparison": g.comparison_id}
    # A dashboard-filtered group is decided on its cause (the sheet filter),
    # never by a column value that would close later groups no one proved.
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
    return [(dataclasses.replace(i, key=_open_key(src)), src) for i, src in out]


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
    run: RunResult,
    run_json: Path,
    recorded: list[Decision] | None = None,
    base: Path | None = None,
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
        base: The validation file's directory, which stored proof paths are
            relative to.

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
    # A decision written by hand must not close what no one proved.
    closed = {
        _open_key(src): d for d, src in [*run.applied.quiet, *run.applied.quiet_cells]
    }
    for i in items:
        d = closed.get(i.get("key", ""))
        if d is not None and i["suggestion"] == "investigate":
            raise pipeline.Refusal(
                f"{view}: decision {d.id!r} closes item {i['id']!r}, which the "
                "triage holds in `investigate`; delete the decision and prove "
                "the item (cube-validation skill, step 8)"
            )
    if n := piles["investigate"]:
        raise pipeline.Refusal(
            f"{view}: {n} triage item{'' if n == 1 else 's'} in `investigate`; "
            "prove each with `triage confirm` (cube-validation skill, step 8), "
            "then re-run `triage`"
        )
    # Every cause rests on a typed proof (`PROOF_KINDS`).
    if bare := sum(
        1
        for i in items
        if i["suggestion"] == "cause"
        and (i.get("proof") or {}).get("kind") not in PROOF_KINDS
    ):
        raise pipeline.Refusal(
            f"{view}: {bare} `cause` item{'' if bare == 1 else 's'} "
            f"rest{'s' if bare == 1 else ''} on no proof; prove "
            f"{'it' if bare == 1 else 'them'} with `triage confirm`, then re-run "
            "`triage`"
        )
    if moved := sum(1 for i in items if _proof_changed(i.get("proof"), base)):
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


# The proofs of a row group that cause decisions decide.
DECIDABLE_PROOFS = ("query", "reconcile")


def decidable(item: dict) -> bool:
    """A proven row group: cause decisions decide it, never a column value."""
    proof = item.get("proof") or {}
    return (
        item.get("kind") == "group"
        and item.get("suggestion") == "cause"
        and bool(item.get("cause"))
        and proof.get("kind") in DECIDABLE_PROOFS
        and bool(proof.get("fingerprint"))
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


def _groups_by_key(run: RunResult) -> dict[str, Group]:
    """The run's open groups by `_open_key`, which no sibling's closing moves."""
    return {i.key: g for i, g in _entries(run) if isinstance(g, Group)}


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
    made on. A decision that no longer holds counts as none.

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
    groups = _groups_by_key(run)
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
        g = groups.get(item.get("key", ""))
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
    run: RunResult,
    loaded: dict,
    recorded: list[Decision],
    leads: dict[str, str] | None = None,
    owner: bool = True,
) -> list[CauseAsk]:
    """What `review` asks the owner: each unanswered owner cause and its groups.

    Reads items `mark_decided` marked. A cause's rows are only those its
    proof attributes to it, so a group split across causes counts in each
    question only by its own share. With `owner` False, the cause decisions
    the analyst made with any other call instead, which `review` only reports.
    """
    groups = _groups_by_key(run)
    out = []
    for d in recorded:
        if not d.cause or d.answer or (d.call == "domain_owner") != owner:
            continue
        mine, rows, proofs = [], 0, {}
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
                proof = item.get("proof") or {}
                if proof.get("kind") == "query" and proof.get("path"):
                    proofs |= dict.fromkeys((proof["path"], c["step"]) for c in causes)
        if mine:
            out.append(
                CauseAsk(
                    d, mine, rows, (leads or {}).get(d.comparison, ""), tuple(proofs)
                )
            )
    return out


def _proof_changed(proof: dict | None, base: Path | None = None) -> bool:
    """A stored proof's file is gone, or no longer the proof triage ran.

    The recorded path is relative to the validation file's directory, `base`.
    Compared by `confirm.fingerprint`, so a formatting-only edit is no change.
    """
    if not proof or not proof.get("path"):
        return False
    from . import confirm

    path = Path(proof["path"])
    if base is not None and not path.is_absolute():
        path = base / path
    return confirm.file_fingerprint(path) != proof.get("fingerprint")


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


NOT_TRACED = "not traced (`triage --no-trace`)"
NO_FILTER = "no `dashboard_filters` entry names the filter that drops these rows"


def _filter_cause(
    comparison: Comparison | None, g: Group
) -> tuple[list[dict], tuple[str, ...], tuple[str, ...], dict] | None:
    """A dashboard-filtered group's cause, from the run's reconcile.

    The reconcile found every row present with the comparison's
    `dashboard_filters` entry off and absent with it on.

    Returns:
        The cause, its evidence, the posted copy and the proof; None when no
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
    # The sheet filter's caption, when the proof maps it to this column.
    captions = {
        c: caption
        for caption, c in (
            (comparison.proof.missing_columns or {}) if comparison.proof else {}
        ).items()
    }
    label = f"sheet filter {captions.get(column, column)}"
    sql = pipeline._dashboard_filter_sql(entry)
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
        reconcile_proof(entry),
    )


def reconcile_proof(entry: dict) -> dict:
    """The proof of a dashboard-filtered group: the filter the reconcile ran.

    Its fingerprint is the `dashboard_filters` entry's, so editing the filter
    re-opens the decisions made on it.
    """
    text = json.dumps(entry, sort_keys=True, default=str)
    return {
        "kind": "reconcile",
        "fingerprint": hashlib.sha256(text.encode()).hexdigest(),
    }


NO_ROWS = (
    "values differ on rows both sides have: no trace; prove them with "
    "`triage confirm --bucket value_differs`"
)
NO_GRAIN = "not traced: the comparison has no `rows` grain"
MOVED_ROWS = (
    "rows both sides hold sit in different cells (Cube's columns, then the "
    "dashboard's as `d:`): no trace; prove them with "
    "`triage confirm --bucket dims_differ`"
)


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
            columns and proof.
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
        filter the proof shows filters nothing, or whose values match a Cube
        member's, takes `filters_nothing` or `map_filters`; any other missing
        cut or filter is `cause`, a sheet step on the dashboard side, and so
        is a group the sheet's dashboard-only filter drops. Every other item
        is `investigate`, with the trace's leads and its comparison's doc lead
        as evidence. Member descriptions are never evidence here: they have
        not explained a missing row.
    """
    by_id = {c.id: c for c in cfg.comparisons}
    entries = _entries(run)
    out = []
    for item, source in entries:
        evidence: tuple[str, ...] = ()
        verdict_lines: tuple[str, ...] = ()
        candidates: tuple[str, ...] = ()
        call = ""
        cause: list[dict] | None = None
        proof: dict | None = None
        found: tuple[str, ...] = ()
        # The same lines masked, for the review issue (`posted`).
        posted: tuple[str, ...] | None = None
        posted_found: tuple[str, ...] | None = None

        if isinstance(source, Gap):
            gap = source
            caption = gap.field
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
                    call, proof = "cause", {"kind": "workbook"}
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
            if isinstance(source, Group):
                traced = (traces or {}).get(trace.item_key(source))
                if source.bucket == "dashboard_filtered":
                    # The run's reconcile proved each row: the sheet's own
                    # dashboard-only filter drops it. No trace is needed.
                    filtered = _filter_cause(comparison, source)
                    if filtered:
                        call = "cause"
                        cause, evidence, posted, proof = filtered
                    else:
                        found = (NO_FILTER,)
                elif traced is not None:
                    # The trace is a lead: a person proves the cause with
                    # `triage confirm`.
                    found, posted_found = traced.leads(), traced.leads(posted=True)
                elif traces is None:
                    found = (NOT_TRACED,)
                elif source.bucket == "value_differs":
                    found = (NO_ROWS,)
                elif source.bucket == "dims_differ":
                    found = (MOVED_ROWS,)
                else:
                    found = (NO_GRAIN,)

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

        out.append(Suggestion(item, call, evidence, candidates, cause, proof, posted))

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
        "decisions": s.decisions,
        "decided": s.decided,
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
        d.get("proof"),
        tuple(d["evidence_posted"]),
        d.get("decisions"),
        d.get("decided"),
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

    Re-runs every stored proof in `proofs` on the run's rows first
    (`confirm.run_stored`; None skips them): only a proof moves a row group
    to `cause`. Then traces the row groups no proof explains
    (`trace.trace_run`) unless `trace_rows` is False, for leads. Both count
    against `max_usd` and the daily cap with the value checks. A cap or
    `trace_max_minutes` hit partway stops the trace; what it found is kept
    and the batch is still written, as it is when a proof cannot run. Prints
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

    from . import confirm

    prepared = trace.Prepared()
    with wh.budget(max_usd):
        if trace_rows:
            # A trace refusal after the proofs ran would throw their spend away.
            trace.check_ready(
                cfg,
                run,
                wh=wh,
                cube=cube,
                manifest_path=manifest or trace.MANIFEST,
                prepared=prepared,
            )
        # Proofs first: they are the only path to `cause`, so a trace that
        # hits a cap never un-proves an item, and nothing they explain is
        # traced.
        ran = (
            confirm.run_stored(cfg, run, proofs, wh=wh, cube=cube, prepared=prepared)
            if proofs is not None
            else []
        )
        traced = (
            trace.trace_run(
                cfg,
                run,
                wh=wh,
                cube=cube,
                manifest_path=manifest or trace.MANIFEST,
                max_minutes=trace_max_minutes or trace.TRACE_MAX_MINUTES,
                skip=confirm.explained(ran),
                prepared=prepared,
            )
            if trace_rows
            else None
        )
        found = suggest(
            cfg, run, docs, values, traced.items if traced else None, doc_leads(cfg)
        )
        items = [_as_json(s) for s in found]
        kept: dict = {}
        if proofs is not None:
            confirm.apply_runs(run, items, ran, cfg, kept)
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
                "items": items,
                # Per comparison, each proven cause's students per cell and
                # cut, from the proofs' counting queries (`review` examples).
                "cause_students": kept.get("cause_students", {}),
            },
            indent=1,
        )
    )

    print("\n".join(batch_lines(run, found)))
    print(f"Saved {out}")
    return found
