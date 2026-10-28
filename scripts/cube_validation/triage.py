"""Gather evidence and suggest a call for each open item of a run.

An open item is a row group, a comparison's cell differences, or a missing cut
or filter. A suggestion never applies a call: the analyst reads it and decides.
Item ids and labels carry no value the review issue would hide. Pure: no I/O.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .compare import Gap, Group
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

    `kind` is `group`, `cells` or `gap`. `stub` holds the key fields of the
    decision that would cover it, with a group's value masked as the review
    issue masks it.
    """

    id: str
    kind: str
    comparison: str
    label: str
    stub: dict


@dataclass(frozen=True)
class Suggestion:
    item: Item
    suggestion: str
    evidence: tuple[str, ...]
    candidates: tuple[str, ...] = ()


def _group_item(g: Group) -> Item:
    shown = [(c, _shown_value(g, c, v)) for c, v in g.dims]
    name = ",".join(f"{c}={v}" for c, v in shown) or "all"
    column, value = shown[0] if shown else ("", "")
    label = (
        f"{_where(g, lambda column, value: _shown_value(g, column, value))} in "
        f"{g.comparison_id} ({g.bucket}): {mask(g.n_rows)} rows, "
        f"{mask(g.n_students)} students"
    )
    return Item(
        id=f"{g.comparison_id}:{name}",
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


def open_items(run: RunResult) -> list[Item]:
    """List the run's open items in the order the review reads them.

    Args:
        run: One view's validation run.

    Returns:
        Groups, then missing cuts and filters, then cell differences. Ids are
        stable across runs and carry a value only for a reviewed column of a
        group with 10+ students.
    """
    items = [_group_item(g) for g in run.applied.open]
    items += [_gap_item(g) for g in run.applied.open_gaps]
    for diff in run.applied.open_cells:
        counts = ", ".join(
            f"{mask(n)} {_CELL_WORDS.get(verdict, verdict)}"
            for verdict, n in diff.counts.items()
        )
        items.append(
            Item(
                id=f"{diff.comparison_id}:cells",
                kind="cells",
                comparison=diff.comparison_id,
                label=f"{diff.comparison_id}: {counts}",
                stub={"comparison": diff.comparison_id, "cells": True},
            )
        )
    return items


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
    proofs = [c.proof for c in cfg.comparisons if c.proof]
    notes = {k: v for p in proofs for k, v in (p.filter_notes or {}).items()}
    known = [p.restricting_filters for p in proofs if p.restricting_filters is not None]
    restricting = {f for r in known for f in r}

    gaps = {_gap_item(g).id: g for g in run.applied.open_gaps}
    groups = {_group_item(g).id: g for g in run.applied.open}
    out = []
    for item in open_items(run):
        evidence: tuple[str, ...] = ()
        candidates: tuple[str, ...] = ()
        members: list[str] = []
        call = ""

        if item.kind == "gap":
            gap = gaps[item.id]
            caption = gap.field
            members = [by_id[c].measure for c in gap.comparisons if c in by_id]
            if gap.kind == "filter" and caption in notes:
                call, evidence = "filters_nothing", (notes[caption],)
            elif gap.kind == "filter" and known and caption not in restricting:
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
                if item.kind == "group":
                    to_cube = {p.dashboard: p.cube for p in comparison.dims}
                    members += [to_cube.get(c, c) for c, _ in groups[item.id].dims]

        if not call:
            evidence = _doc_evidence(members, docs)
            call = "docs" if evidence else "owner"
            evidence = evidence or (NO_ANSWER,)
        out.append(Suggestion(item, call, evidence, candidates))

    return sorted(out, key=lambda s: SUGGESTIONS.index(s.suggestion))
