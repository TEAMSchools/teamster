"""Gather evidence and suggest a call for each open item of a run.

An open item is a row group, a comparison's cell differences, or a missing cut
or filter. A suggestion never applies a call: the analyst reads it and decides.
Item ids and labels carry no value the review issue would hide. `suggest` is
pure; `value_check` and `run_triage` read the warehouse and Cube.
"""

from __future__ import annotations

import dataclasses
import json
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from . import pipeline
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

# The order the analyst's batch shows suggestions, the owner last.
SUGGESTIONS = ("map_filters", "filters_nothing", "docs", "owner")

NO_ANSWER = "no description or ai_context answers it"

# The fixed words of `pipeline.candidate_causes` and `pipeline._cell_diffs`:
# they read the same on every cell set, so they never tie a doc to one.
_CAUSE_WORDS = frozenset(
    _tokens(
        "cell cells Cube is blank where the dashboard shows 0 a value display "
        "unit apart at decimals values differ beyond rounding of in cut have row "
        "groups on this comparison see Triage may explain part it every matches "
        "grain and so definitions or their filters"
    )
)
# Cause lines that restate the measure's definitions, not the cells.
_DEFINITION_CAUSES = ("Cube computes ", "Recorded definitions:")


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


def _group_topic(
    g: Group, to_cube: dict[str, str], docs: dict[str, MemberDoc]
) -> set[str]:
    """Words naming a group's columns: each column, its member and the member's title.

    A dashboard-only filter's dim names the filter's column in its value.
    """
    out: set[str] = set()
    for column, value in g.dims:
        if column == "dashboard_filter":
            out |= _tokens(value)
            continue
        member = to_cube.get(column, column)
        title = docs[member].title if member in docs else ""
        out |= _tokens(f"{column} {member} {title}")
    return out


def _cells_topic(diff: CellDiff) -> set[str]:
    """Words of a cell set's candidate causes, past their fixed wording and the definitions."""
    words = set().union(
        *(_tokens(c) for c in diff.causes if not c.startswith(_DEFINITION_CAUSES))
    )
    return words - _CAUSE_WORDS


def _speaks_to(members: list[str], topic: set[str], docs: dict[str, MemberDoc]) -> bool:
    """Whether any member's description or ai_context names a word of `topic`."""
    return any(
        _tokens(text) & topic
        for name in members
        if (d := docs.get(name))
        for text in (d.description, d.ai_context)
    )


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
        `docs` needs a description or ai_context of an involved member to name
        the item: its group's column or that member's title, the gap's
        caption, or a word of the cell set's candidate causes. The measure's
        own name and title never count, since its description is always
        there. Docs that name nothing are still quoted on an `owner` item.
    """
    by_id = {c.id: c for c in cfg.comparisons}
    entries = _entries(run)
    out = []
    for item, source in entries:
        evidence: tuple[str, ...] = ()
        verdict_lines: tuple[str, ...] = ()
        candidates: tuple[str, ...] = ()
        members: list[str] = []
        measures: list[str] = []
        topic: set[str] = set()
        call = ""

        if isinstance(source, Gap):
            gap = source
            caption = gap.field
            measures = [by_id[c].measure for c in gap.comparisons if c in by_id]
            members = list(measures)
            topic = _tokens(caption)
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
            comparison = by_id.get(item.comparison)
            if comparison:
                measures = [comparison.measure]
                members = list(measures)
                if isinstance(source, Group):
                    to_cube = {p.dashboard: p.cube for p in comparison.dims}
                    members += [to_cube.get(c, c) for c, _ in source.dims]
                    topic = _group_topic(source, to_cube, docs)
                elif isinstance(source, CellDiff):
                    topic = _cells_topic(source)

        if not call:
            for m in measures:
                topic -= _tokens(f"{m} {docs[m].title if m in docs else ''}")
            quoted = _doc_evidence(members, docs)
            if _speaks_to(members, topic, docs):
                call, evidence = "docs", verdict_lines + quoted
            else:
                call, evidence = "owner", verdict_lines + quoted + (NO_ANSWER,)

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


# --- the printed batch -------------------------------------------------------

# Items listed per suggestion; `triage.json` keeps them all.
BATCH_CAP = 25


def _counts(counter: Counter) -> str:
    return ", ".join(f"{k} {n:,}" for k, n in sorted(counter.items()))


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
            f"    by suggestion: {_counts(Counter(s.suggestion for s in mine))}"
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
    cfg: ViewConfig, *, wh: Warehouse, cube: Cube, max_usd: float, cache_root: Path
) -> list[Suggestion]:
    """Suggest a call for each open item of the view's latest run and print them.

    Prints `batch_lines`. Writes every item to `triage.json` beside that run's
    `run.json`: it stays in the local cache, and its stubs carry real values.

    Raises:
        pipeline.Refusal: The view has no usable saved run (see
            `pipeline.latest_run`).
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
        found = suggest(cfg, run, docs, values)

    out = run_json.parent / "triage.json"
    out.write_text(
        json.dumps(
            {
                "view": run.view,
                "moment": {
                    "start": run.moment.start.isoformat(),
                    "end": run.moment.end.isoformat(),
                    "job_id": run.moment.job_id,
                },
                "decisions_fingerprint": run.decisions_fingerprint,
                "items": [
                    {
                        **dataclasses.asdict(s.item),
                        "suggestion": s.suggestion,
                        "evidence": list(s.evidence),
                        "candidates": list(s.candidates),
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
