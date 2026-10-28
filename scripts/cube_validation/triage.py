"""Gather evidence and suggest a call for each open item of a run.

An open item is a row group, a comparison's cell differences, or a missing cut
or filter. A suggestion never applies a call: the analyst reads it and decides.
Item ids and labels carry no value the review issue would hide. Pure: no I/O.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .compare import CellDiff, Gap, Group
from .config import ViewConfig
from .cube_client import MemberDoc
from .discover import _tokens
from .report import _CELL_WORDS, RunResult, _gap_line, _shown_value, _where, mask

# The order the analyst's batch shows suggestions, the owner last.
SUGGESTIONS = ("map_filters", "filters_nothing", "docs", "owner")

NO_ANSWER = "no description or ai_context answers it"


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
    """A suggested call for one item, with what it rests on.

    `evidence` is the quoted note, doc text or verdict behind the call, and
    `candidates` the Cube members a missing filter or cut may map to.
    """

    item: Item
    suggestion: str
    evidence: tuple[str, ...]
    candidates: tuple[str, ...] = ()


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
        (_group_item(g, i, open_groups), g) for g, i in zip(open_groups, ids)
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


def suggest(
    cfg: ViewConfig,
    run: RunResult,
    docs: dict[str, MemberDoc],
    values: Callable[[str, str], str] | None = None,
) -> list[Suggestion]:
    """Suggest a call for each open item, first matching rule wins.

    Args:
        cfg: The view's config, for each comparison's measure, group-by
            columns and proof.
        run: One view's validation run.
        docs: The view's members by bare name, from `member_docs`.
        values: `values(caption, member)` returns a value-check verdict;
            `None` skips value checks.

    Returns:
        One suggestion per open item, ordered by `SUGGESTIONS`, owner last.
    """
    by_id = {c.id: c for c in cfg.comparisons}
    entries = _entries(run)
    out = []
    for item, source in entries:
        evidence: tuple[str, ...] = ()
        candidates: tuple[str, ...] = ()
        members: list[str] = []
        call = ""

        if isinstance(source, Gap):
            gap = source
            caption = gap.field
            members = [by_id[c].measure for c in gap.comparisons if c in by_id]
            # Only the sheets the gap sits on speak for it; a proof that
            # predates `restricting_filters` leaves the answer unknown.
            proofs = [
                by_id[c].proof for c in gap.comparisons if c in by_id and by_id[c].proof
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
                same = [(m, v) for m, v in verdicts if v.startswith("same values")]
                if same:
                    call = "map_filters"
                    evidence = tuple(f"{m}: {v}" for m, v in same)
        else:
            comparison = by_id.get(item.comparison)
            if comparison:
                members = [comparison.measure]
                if isinstance(source, Group):
                    to_cube = {p.dashboard: p.cube for p in comparison.dims}
                    members += [to_cube.get(c, c) for c, _ in source.dims]

        if not call:
            evidence = _doc_evidence(members, docs)
            call = "docs" if evidence else "owner"
            evidence = evidence or (NO_ANSWER,)

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
        out.append(Suggestion(item, call, evidence, candidates))

    return sorted(out, key=lambda s: SUGGESTIONS.index(s.suggestion))
