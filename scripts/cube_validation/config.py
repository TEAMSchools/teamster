"""Load and validate the per-view Cube validation files.

Each file at `src/cube/validation/<view>.yml` records the dashboard-to-Cube
comparisons for one Cube view and the decisions made about differences. Cube
loads only `src/cube/model/`, so these files never reach the semantic layer.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any, NoReturn

import yaml

CALLS = ("deliberate", "fix_dashboard", "fix_cube", "fix_source", "domain_owner")
# A domain-owner decision's task is the review issue, which `ask-owner` drafts
# from the decisions, so its task is filled in after the issue posts. A
# `fix_source` task is the issue opened for the source data's owner.
CALLS_NEEDING_TASK = ("fix_dashboard", "fix_cube", "fix_source")
# The `tasks:` block names a domain's Cube-fix issue and dashboard-fix task,
# which `record-answers` copies into a decision's `task`.
TASK_KEYS = ("cube_fix", "dashboard_fix")
# The side of a comparison whose SQL holds a cause decision's step.
CAUSE_SIDES = ("dashboard", "cube")
# A committed decision carries no ID-shaped number: 5 or more digits, whole or
# joined by single separators within one word (`973-555-1234`, `1,234,567`).
# A school year or a date is not one, nor are small numbers apart (`9 10 11`).
_ID_RUN = re.compile(r"\d+(?:[-.,/:]\d+)*")
_YEAR_OR_DATE = re.compile(r"\d{4}-(?:\d{2}|\d{4})|\d{4}-\d{2}-\d{2}")
# Digits split by spaces, dashes, commas or dots, for scrubbing free text
# (`report._safe_reason`, `answers.NOTE_REFUSALS`).
SEPARATED_DIGITS = re.compile(r"\d[\d\-\s,.]{3,}\d")


def id_like(text: str) -> bool:
    """Text that could name a person: an email, or an ID-shaped number."""
    return "@" in text or mask_digits(text) != text


def mask_digits(text: str) -> str:
    """Write each ID-shaped number in `text` as `<n>`."""

    def masked(m: re.Match) -> str:
        run = m[0]
        if _YEAR_OR_DATE.fullmatch(run) or sum(c.isdigit() for c in run) < 5:
            return run
        return "<n>"

    return _ID_RUN.sub(masked, text)


_TASK = re.compile(r"https://\S+|#\d+")
# Filter operators for `scope` (Cube side) and `dashboard_filters` (dashboard
# side). The comparisons take exactly 1 number; `set` means not null.
SCOPE_OPERATORS = ("equals", "not_equals", "gt", "gte", "lt", "lte", "set")
COMPARE_OPERATORS = ("gt", "gte", "lt", "lte")
# A dashboard filter's days past the coming Sunday, in place of `values`.
WEEK_END_KEY = "days_from_week_end"
# How `rebuild-sheet` treats export rows that share every mapped dim: `refuse`
# fails the rebuild check; `sum` adds them, which is right only for a field
# that adds up.
SPLIT_ROWS = ("refuse", "sum")
# How `rows.reduce` cuts the dashboard rows to one per grain key: `latest`
# keeps the row with the latest value of the `by` column.
REDUCE_RULES = ("latest",)

# Every config value the SQL builders interpolate must pass one of these, so a
# validation file cannot carry SQL text into a query.
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_TABLE_REF = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*")

# The marts dataset a fact is read from: prod's, or an analyst's dbt dev build.
_FACT_DATASET = re.compile(r"kipptaf_marts|zz_[a-z0-9]+_kipptaf_marts")
DEFAULT_FACT_DATASET = "kipptaf_marts"


class ConfigError(Exception):
    """A validation file is malformed; the message names the file and key path."""


@dataclass(frozen=True)
class ColumnPair:
    dashboard: str
    cube: str


@dataclass(frozen=True)
class RowSpec:
    grain: list[ColumnPair]
    values: list[ColumnPair]
    # Dashboard-side row filters (`dashboard_filters` entries) for the
    # reconcile's dashboard rows only, mirroring a `scope` Cube applies: the
    # sheet query and the cells keep every row, so a cell with no rows in scope
    # still shows (blank) on both.
    dashboard_scope: list[dict[str, Any]] = field(default_factory=list)
    # `{rule, by}`: one dashboard row per grain key before the reconcile, for a
    # dashboard that stores 1 row per key per day. Empty keeps every row.
    reduce: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class RebuildCheck:
    fingerprint: str
    cells: Any
    matched_at: str
    workbook_updated_at: str = ""
    sheet_query_fingerprint: str = ""
    # `tableau.source_fingerprint` of the sheet; "" when the check predates it.
    source_fingerprint: str = ""
    # The cut labels the REST export matched; None when the check predates them.
    cuts: list[str] | None = None
    # Total rows the export showed and the check skipped; None when the check
    # predates the count.
    totals_skipped: int | None = None
    # Sheet fields with no Cube member, by caption: cuts on the sheet's shelves,
    # filters, and the filters that narrow the sheet now. None when the check
    # predates them.
    missing_cuts: list[str] | None = None
    missing_filters: list[str] | None = None
    restricting_filters: list[str] | None = None
    # Why a missing field needs no Cube member, by caption: `copy of <mapped
    # caption>` or `display switch on <parameter caption>`; and the datasource
    # column behind a plain missing field. None when the check predates them.
    filter_notes: dict[str, str] | None = None
    missing_columns: dict[str, str] | None = None
    # The reshape the rebuild copy carried; the sheet query fingerprint covers it.
    shelves: dict[str, Any] | None = None
    # Whether a dashboard viewer can see the sheet (`tableau.published_sheets`);
    # None when the check predates it.
    published: bool | None = None


@dataclass(frozen=True)
class Comparison:
    id: str
    measure: str
    confirmed: bool = False
    workbook: str | None = None
    sheet: str | None = None
    dashboard_view: str | None = None
    sheet_query: str | None = None
    sheet_query_sql: str | None = None
    decimals: int | None = None
    dims: list[ColumnPair] = field(default_factory=list)
    filters: dict[str, ColumnPair] = field(default_factory=dict)
    defaults: dict[str, Any] = field(default_factory=dict)
    cuts: list[dict[str, Any]] = field(default_factory=list)
    scope: list[dict[str, Any]] = field(default_factory=list)
    rows: RowSpec | None = None
    rebuild_check: RebuildCheck | None = None
    # The sheet field to compare, by its exported caption: a column header, or
    # a `Measure Names` value in a long export.
    sheet_field: str | None = None
    split_rows: str = "refuse"
    # Row filters on the dashboard side only, for a sheet filter Cube has no
    # member for; each is `{dashboard: <column>, operator, values}`.
    dashboard_filters: list[dict[str, Any]] = field(default_factory=list)
    # What each side counts, in a sentence or code list, for a domain owner to
    # compare in the review issue: `{dashboard: ..., cube: ...}`.
    definitions: dict[str, str] = field(default_factory=dict)
    # Workbook parameters set on the rebuild copy, `{caption: member}`, for a
    # field the sheet shows only behind a parameter value.
    parameters: dict[str, str] = field(default_factory=dict)
    # A reshape of the rebuild copy's rows and columns, for a sheet field Cube has
    # no member for: `{drop: [caption], add: {rows: [caption], cols: [caption]}}`.
    # Tableau recomputes the measure at the new grain, so the check covers that
    # grain, not the sheet's own.
    shelves: dict[str, Any] = field(default_factory=dict)
    # Columns computed over `dashboard_view`, `{name: SQL expression}`, for a
    # workbook calc a dim or row value maps to. Every dashboard read sees them
    # as plain columns. Name one after the calc (`Calculation_<id>`) and the
    # export header with the calc's caption maps to it.
    dashboard_columns: dict[str, str] = field(default_factory=dict)
    # Compare a sheet no dashboard viewer sees (`tableau.published_sheets`);
    # `rebuild-sheet` refuses one otherwise.
    unpublished: bool = False


def fingerprint_data(comparison: Comparison) -> dict:
    """What a comparison's entry and checkpoint fingerprints hash.

    Its `definitions` are left out: words for the owner change no result.
    `unpublished` when False and `rebuild_check.published` when None are left
    out too, so a file written before those keys keeps the fingerprints, and
    every saved result, it already has.
    """
    data = asdict(replace(comparison, definitions={}))
    if not comparison.unpublished:
        del data["unpublished"]
    if data["rebuild_check"] is not None and data["rebuild_check"]["published"] is None:
        del data["rebuild_check"]["published"]
    return data


# The keys that decide which rows a comparison reconciles and which of them
# match; `dims` only group the rows, and the rest shape the cells.
_POPULATION = (
    "dashboard_view",
    "rows",
    "filters",
    "defaults",
    "cuts",
    "scope",
    "dashboard_filters",
    "dashboard_columns",
)


def row_population(comparison: Comparison) -> str | None:
    """A key shared by the comparisons that reconcile the same rows, or None.

    Comparisons with the same key usually hold the same unmatched rows,
    grouped by their own `dims`, so one explanation can classify them all. A
    dim from another cube adds a join that can drop or repeat rows; an
    explanation run on each comparison's own rows refuses then, as for any
    explanation.
    """
    if comparison.rows is None:
        return None
    data = asdict(comparison)
    return json.dumps([data[k] for k in _POPULATION], sort_keys=True, default=str)


@dataclass(frozen=True)
class Decision:
    id: str
    comparison: str
    call: str
    reason: str
    group: dict[str, Any] = field(default_factory=dict)
    task: str = ""
    fingerprints: dict[str, str] = field(default_factory=dict)
    # A decision on a sheet field Cube has no member for names it here instead
    # of `group`, and covers the whole view, so it has no `comparison`.
    missing_cut: str = ""
    missing_filter: str = ""
    # Covers the row groups whose triage cause names this `{side, label}`, in
    # place of `group`: `label` is the words of a stored explanation's bucket,
    # with each number of 5 or more digits written `<n>`. Which groups it covers
    # is read from the latest triage, never stored here;
    # `fingerprints.explanation` is the explanation file's.
    cause: dict[str, Any] = field(default_factory=dict)
    # Covers the comparison's formula difference, in place of `group`: its
    # differing cells that hold no unmatched row, whichever they are in a run.
    formula: bool = False
    # The call the owner answered a cause decision with; set by
    # `record-answers`, so `ask-owner` asks it no more.
    answer: str = ""


@dataclass(frozen=True)
class ViewConfig:
    view: str
    fact: str
    comparisons: list[Comparison]
    email: str | None = None
    time_dimension: str | None = None
    decisions: list[Decision] = field(default_factory=list)
    tasks: dict[str, str] = field(default_factory=dict)
    # Facts other than `fact` that the view's members read. Cube reads them at
    # the build end like `fact`; `compare` refuses one that changed during the build.
    also_facts: list[str] = field(default_factory=list)


class _Reader:
    """Typed access to one parsed mapping, with errors that name the key path."""

    def __init__(self, path: Path, where: str, data: Any):
        self.path = path
        self.where = where
        if not isinstance(data, dict):
            self.fail("", "must be a mapping")
        self.data: dict = data

    def fail(self, key: str, msg: str) -> NoReturn:
        where = f"{self.where}.{key}" if self.where and key else self.where or key
        raise ConfigError(f"{self.path}: {where or '<root>'}: {msg}")

    def get(self, key: str, kind: type | tuple, *, required=False, default=None) -> Any:
        if key not in self.data or self.data[key] is None:
            if required:
                self.fail(key, "is required")
            return default
        value = self.data[key]
        if isinstance(value, bool) and kind not in (bool, (bool,)):
            self.fail(key, f"must be {_kind_name(kind)}")
        if not isinstance(value, kind):
            self.fail(key, f"must be {_kind_name(kind)}")
        return value

    def child(self, key: str, value: Any) -> _Reader:
        return _Reader(self.path, f"{self.where}.{key}" if self.where else key, value)


def _kind_name(kind: type | tuple) -> str:
    kinds = kind if isinstance(kind, tuple) else (kind,)
    return " or ".join(k.__name__ for k in kinds)


def _identifier(reader: _Reader, key: str, *, required=False) -> str | None:
    """A string that is safe to interpolate into SQL as a column or member name."""
    value = reader.get(key, str, required=required)
    if value is not None and not _IDENTIFIER.fullmatch(value):
        reader.fail(
            key, f"must be a plain identifier ([A-Za-z_][A-Za-z0-9_]*); got {value!r}"
        )
    return value


def with_fact_dataset(cfg: ViewConfig, dataset: str) -> ViewConfig:
    """Point `cfg.fact` and each of `cfg.also_facts` at `dataset`, keeping its table.

    Raises:
        ConfigError: `dataset` is neither `kipptaf_marts` nor a dev build's
            `zz_<user>_kipptaf_marts`. It reaches SQL, so nothing else passes.
    """
    if not _FACT_DATASET.fullmatch(dataset):
        raise ConfigError(
            f"fact dataset must be {DEFAULT_FACT_DATASET} or "
            f"zz_<user>_{DEFAULT_FACT_DATASET} (lowercase letters and digits); "
            f"got {dataset!r}"
        )

    return replace(
        cfg,
        fact=f"{dataset}.{cfg.fact.split('.', 1)[1]}",
        also_facts=[f"{dataset}.{f.split('.', 1)[1]}" for f in cfg.also_facts],
    )


def _table_ref(reader: _Reader, key: str, *, required=False) -> str | None:
    """A `dataset.table` string that is safe to interpolate into SQL."""
    value = reader.get(key, str, required=required)
    if value is not None and not _TABLE_REF.fullmatch(value):
        reader.fail(key, f"must be dataset.table of plain identifiers; got {value!r}")
    return value


def _table_refs(reader: _Reader, key: str) -> list[str]:
    """A list of `dataset.table` strings, each safe to interpolate into SQL."""
    values = reader.get(key, list, default=[])
    for i, value in enumerate(values):
        if not isinstance(value, str) or not _TABLE_REF.fullmatch(value):
            reader.fail(
                f"{key}[{i}]",
                f"must be dataset.table of plain identifiers; got {value!r}",
            )
    return values


def _list_of(reader: _Reader, key: str) -> list[_Reader]:
    items = reader.get(key, list, default=[])
    return [reader.child(f"{key}[{i}]", item) for i, item in enumerate(items)]


def _pair(reader: _Reader) -> ColumnPair:
    return ColumnPair(
        dashboard=_identifier(reader, "dashboard", required=True),
        cube=_identifier(reader, "cube", required=True),
    )


def _pairs(reader: _Reader, key: str) -> list[ColumnPair]:
    return [_pair(item) for item in _list_of(reader, key)]


def _reduce(reader: _Reader) -> dict[str, str]:
    if reader.data.get("reduce") is None:
        return {}
    spec = reader.child("reduce", reader.data["reduce"])
    for key in spec.data:
        if key not in ("rule", "by"):
            spec.fail(key, "unknown key; `reduce` takes only rule and by")
    rule = spec.get("rule", str, required=True)
    if rule not in REDUCE_RULES:
        spec.fail("rule", f"must be one of {', '.join(REDUCE_RULES)}; got {rule!r}")
    by = _identifier(spec, "by", required=True)
    if by.startswith("__"):
        spec.fail("by", "must not start with __; that prefix is the tool's own")
    return {"rule": rule, "by": by}


# Comparison keys renamed to plain words; an old key is refused, never read.
RENAMED_KEYS = {
    "probe": "sheet_query",
    "probe_sql": "sheet_query_sql",
    "proof": "rebuild_check",
}


# `rebuild_check:` keys renamed the same way.
RENAMED_CHECK_KEYS = {
    "proven_at": "matched_at",
    "probe_fingerprint": "sheet_query_fingerprint",
}


def _comparison(reader: _Reader) -> Comparison:
    for old, new in RENAMED_KEYS.items():
        if old in reader.data:
            reader.fail(old, f"renamed; write it as {new}")
    sheet_query = reader.get("sheet_query", str)
    sheet_query_sql = reader.get("sheet_query_sql", str)
    if sheet_query and sheet_query_sql:
        reader.fail(
            "sheet_query", "set either sheet_query or sheet_query_sql, not both"
        )

    filters = {}
    for caption, spec in reader.get("filters", dict, default={}).items():
        filters[caption] = _pair(reader.child(f"filters.{caption}", spec))

    rows = None
    if reader.data.get("rows") is not None:
        rows_reader = reader.child("rows", reader.data["rows"])
        if "cell" in rows_reader.data:
            rows_reader.fail("cell", "delete it; cells close by coverage")
        rows = RowSpec(
            grain=_pairs(rows_reader, "grain"),
            values=_pairs(rows_reader, "values"),
            dashboard_scope=[
                _filter_entry(r, "dashboard")
                for r in _list_of(rows_reader, "dashboard_scope")
            ],
            reduce=_reduce(rows_reader),
        )

    rebuild_check = None
    if reader.data.get("rebuild_check") is not None:
        check_reader = reader.child("rebuild_check", reader.data["rebuild_check"])
        for old, new in RENAMED_CHECK_KEYS.items():
            if old in check_reader.data:
                check_reader.fail(old, f"renamed; write it as {new}")
        cuts = check_reader.get("cuts", list)
        totals_skipped = check_reader.get("totals_skipped", int)
        if totals_skipped is not None and totals_skipped < 0:
            check_reader.fail("totals_skipped", "must be 0 or more")
        rebuild_check = RebuildCheck(
            cuts=None if cuts is None else [str(c) for c in cuts],
            fingerprint=check_reader.get("fingerprint", str, required=True),
            cells=check_reader.data.get("cells"),
            matched_at=str(check_reader.data.get("matched_at", "")),
            workbook_updated_at=str(check_reader.data.get("workbook_updated_at", "")),
            sheet_query_fingerprint=str(
                check_reader.data.get("sheet_query_fingerprint", "")
            ),
            source_fingerprint=str(check_reader.data.get("source_fingerprint", "")),
            totals_skipped=totals_skipped,
            missing_cuts=_captions(check_reader, "missing_cuts"),
            missing_filters=_captions(check_reader, "missing_filters"),
            restricting_filters=_captions(check_reader, "restricting_filters"),
            filter_notes=_caption_map(check_reader, "filter_notes"),
            missing_columns=_caption_map(check_reader, "missing_columns"),
            shelves=check_reader.get("shelves", dict),
            published=check_reader.get("published", bool),
        )

    dims = _pairs(reader, "dims")
    split_rows = reader.get("split_rows", str, default="refuse")
    if split_rows not in SPLIT_ROWS:
        reader.fail(
            "split_rows", f"must be one of {', '.join(SPLIT_ROWS)}; got {split_rows!r}"
        )

    return Comparison(
        id=reader.get("id", str, required=True),
        measure=_identifier(reader, "measure", required=True),
        confirmed=reader.get("confirmed", bool, default=False),
        workbook=reader.get("workbook", str),
        sheet=reader.get("sheet", str),
        dashboard_view=_table_ref(reader, "dashboard_view"),
        sheet_query=sheet_query,
        sheet_query_sql=sheet_query_sql,
        decimals=reader.get("decimals", int),
        dims=dims,
        filters=filters,
        defaults=reader.get("defaults", dict, default={}),
        cuts=reader.get("cuts", list, default=[]),
        scope=[_scope_entry(r) for r in _list_of(reader, "scope")],
        rows=rows,
        rebuild_check=rebuild_check,
        sheet_field=reader.get("sheet_field", str),
        split_rows=split_rows,
        dashboard_filters=[
            _filter_entry(r, "dashboard") for r in _list_of(reader, "dashboard_filters")
        ],
        definitions=_definitions(reader),
        parameters={
            str(k): str(v)
            for k, v in reader.get("parameters", dict, default={}).items()
        },
        shelves=_shelves(reader, dims, filters),
        dashboard_columns=_dashboard_columns(reader),
        unpublished=reader.get("unpublished", bool, default=False),
    )


def _dashboard_columns(reader: _Reader) -> dict[str, str]:
    columns = reader.get("dashboard_columns", dict, default={})
    for name, sql in columns.items():
        if not (isinstance(name, str) and _IDENTIFIER.fullmatch(name)):
            reader.fail(
                "dashboard_columns",
                f"names must be plain identifiers ([A-Za-z_][A-Za-z0-9_]*); got {name!r}",
            )
        if not (isinstance(sql, str) and sql.strip()):
            reader.fail("dashboard_columns", f"{name}: the expression must be SQL text")
    return dict(columns)


def _caption_list(reader: _Reader, key: str) -> list[str]:
    captions = reader.get(key, list, default=[])
    if not all(isinstance(c, str) and c for c in captions):
        reader.fail(key, "captions must be text")
    return captions


def _snake(caption: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", caption.lower()).strip("_")


def _shelves(
    reader: _Reader, dims: list[ColumnPair], filters: dict[str, ColumnPair]
) -> dict[str, Any]:
    """Read `shelves`; each added caption must name a dim.

    `clear_filters` names sheet filters the rebuild copy resets to keep
    every member, so the check covers values the sheet filters out.

    A caption names a dim when a `filters:` caption maps it to the dim's
    dashboard column, or when it is that column's name, as is or in Tableau's
    default caption form (`Grade Level` for `grade_level`).
    """
    if reader.data.get("shelves") is None:
        return {}
    child = reader.child("shelves", reader.get("shelves", dict))
    if set(child.data) - {"drop", "add", "clear_filters"}:
        child.fail("", "takes drop, add and clear_filters")
    out: dict[str, Any] = {}
    if drop := _caption_list(child, "drop"):
        out["drop"] = drop
    if cleared := _caption_list(child, "clear_filters"):
        out["clear_filters"] = cleared
    if child.data.get("add") is not None:
        add = child.child("add", child.get("add", dict))
        if set(add.data) - {"rows", "cols"}:
            add.fail("", "takes rows and cols")
        dashboard = {d.dashboard for d in dims}
        for shelf in ("rows", "cols"):
            captions = _caption_list(add, shelf)
            for caption in captions:
                pair = filters.get(caption)
                if not (
                    (pair is not None and pair.dashboard in dashboard)
                    or caption in dashboard
                    or _snake(caption) in dashboard
                ):
                    add.fail(
                        "",
                        f"{caption!r} maps to no dim; add it under dims, or "
                        "name it under filters with a dim's dashboard column",
                    )
            if captions:
                out.setdefault("add", {})[shelf] = captions
    if not out:
        child.fail("", "set drop, add or clear_filters")
    return out


def _definitions(reader: _Reader) -> dict[str, str]:
    if reader.data.get("definitions") is None:
        return {}
    child = reader.child("definitions", reader.get("definitions", dict))
    return {
        side: child.get(side, str, required=True) or ""
        for side in ("dashboard", "cube")
    }


def _captions(reader: _Reader, key: str) -> list[str] | None:
    values = reader.get(key, list)
    return None if values is None else [str(v) for v in values]


def _caption_map(reader: _Reader, key: str) -> dict[str, str] | None:
    values = reader.get(key, dict)
    return None if values is None else {str(k): str(v) for k, v in values.items()}


def _scope_entry(reader: _Reader) -> dict[str, Any]:
    """A Cube-only row filter."""
    return _filter_entry(reader, "cube")


def _filter_entry(reader: _Reader, side: str) -> dict[str, Any]:
    """A one-sided row filter on `side` (`cube` or `dashboard`).

    `equals` and `not_equals` take `values`; `gt`, `gte`, `lt` and `lte` take
    exactly 1 number; `set` (not null) takes none. A dashboard filter may
    compare a date to the coming Sunday instead (`days_from_week_end: 0`, as
    Tableau's `TODAY() + 8 - weekday`), plus that many days.
    """
    column = _identifier(reader, side, required=True)
    operator = reader.get("operator", str, default="equals")
    if operator not in SCOPE_OPERATORS:
        reader.fail(
            "operator", f"must be one of {', '.join(SCOPE_OPERATORS)}; got {operator!r}"
        )
    if reader.data.get(WEEK_END_KEY) is not None:
        if side != "dashboard":
            reader.fail(WEEK_END_KEY, "applies to dashboard_filters only")
        if operator not in COMPARE_OPERATORS:
            reader.fail(
                WEEK_END_KEY, f"takes {', '.join(COMPARE_OPERATORS)}; got {operator!r}"
            )
        if reader.data.get("values") is not None:
            reader.fail("values", f"must be absent with {WEEK_END_KEY}")
        days = reader.get(WEEK_END_KEY, int)
        return {side: column, "operator": operator, WEEK_END_KEY: days}
    if operator == "set":
        if reader.data.get("values") is not None:
            reader.fail("values", "must be absent when operator is set")
        return {side: column, "operator": operator}
    values = reader.get("values", list, required=True)
    if operator in COMPARE_OPERATORS and (
        len(values) != 1
        or isinstance(values[0], bool)
        or not isinstance(values[0], (int, float))
    ):
        reader.fail("values", f"{operator} takes exactly 1 number; got {values!r}")
    return {side: column, "operator": operator, "values": values}


def _child_node(node: yaml.Node | None, key: str | int) -> yaml.Node | None:
    """One key of a mapping node or one item of a sequence node, else None."""
    if isinstance(node, yaml.MappingNode) and isinstance(key, str):
        return next((v for k, v in node.value if k.value == key), None)
    if isinstance(node, yaml.SequenceNode) and isinstance(key, int):
        return node.value[key] if key < len(node.value) else None
    return None


def _value_texts(root: yaml.Node | None, i: int) -> list[str | None]:
    """The source text of each `decisions[i].group.values` scalar, as written."""
    node = root
    for key in ("decisions", i, "group", "values"):
        node = _child_node(node, key)
    if not isinstance(node, yaml.SequenceNode):
        return []
    return [v.value if isinstance(v, yaml.ScalarNode) else None for v in node.value]


def _decision_values(group: _Reader, texts: list[str | None]) -> None:
    """Refuse a group value YAML rewrote: `9.50` reads as 9.5, `010` as 8.

    A group's value is compared as text, so a rewritten value never matches,
    or matches another group. Only quoted text, null and an int written in
    plain decimal (`9` is `"9"`) pass; `texts` is each value's source text.
    """
    for i, value in enumerate(group.get("values", list, default=[])):
        text = texts[i] if i < len(texts) else None
        rewritten = isinstance(value, (bool, float, date)) or (
            isinstance(value, int) and text != str(value)
        )
        if rewritten:
            group.fail(
                f"values[{i}]",
                f"YAML read {text if text is not None else value!r} as "
                f"{type(value).__name__} {value!r}; quote it exactly as the "
                "sort line shows it",
            )


def _decision(
    reader: _Reader, comparison_ids: set[str], texts: list[str | None]
) -> Decision:
    call = reader.get("call", str, required=True)
    if call not in CALLS:
        reader.fail("call", f"must be one of {', '.join(CALLS)}; got {call!r}")
    task = reader.get("task", str, default="")
    if call in CALLS_NEEDING_TASK and not task.strip():
        reader.fail("task", f"is required when call is {call}")
    # The review issue posts `task` to GitHub as written, so it may only be a
    # link, never free text that could name a person.
    if task and not _TASK.fullmatch(task):
        reader.fail("task", f"must be an https:// link or #<issue>; got {task!r}")
    if "cells" in reader.data:
        reader.fail(
            "cells",
            "delete this decision; covered cells need none, and a formula "
            "difference takes formula: true",
        )
    missing_cut = reader.get("missing_cut", str, default="")
    missing_filter = reader.get("missing_filter", str, default="")
    formula = reader.get("formula", bool, default=False)
    if "formula" in reader.data and not formula:
        reader.fail("formula", "must be true; delete the key otherwise")
    keys = ("group", "missing_cut", "missing_filter", "formula", "cause")
    named = [k for k in keys if reader.data.get(k)]
    if len(named) > 1:
        reader.fail(
            named[1],
            "set only one of group, missing_cut, missing_filter, formula and cause",
        )
    if missing_cut or missing_filter:
        # A sheet field Cube lacks is missing from the view, not one comparison.
        for key in ("comparison", "fingerprints"):
            if key in reader.data:
                reader.fail(key, "a missing cut or filter belongs to the view; drop it")
        comparison, group = "", {}
    else:
        comparison = reader.get("comparison", str, required=True)
        if comparison not in comparison_ids:
            reader.fail("comparison", f"{comparison!r} is not a comparison id")
        group = reader.get("group", dict, default={})
        _decision_values(reader.child("group", group), texts)
    cause = reader.get("cause", dict, default={})
    if cause:
        _cause(reader.child("cause", cause))
    fingerprints = reader.get("fingerprints", dict, default={})
    if "proof" in fingerprints:
        reader.child("fingerprints", fingerprints).fail(
            "proof", "renamed; write it as explanation"
        )
    answer = reader.get("answer", str, default="")
    if answer and not cause:
        reader.fail("answer", "belongs to a cause decision")
    if answer and answer not in CALLS:
        reader.fail("answer", f"must be one of {', '.join(CALLS)}; got {answer!r}")
    return Decision(
        id=reader.get("id", str, required=True),
        comparison=comparison,
        call=call,
        reason=reader.get("reason", str, required=True),
        group=group,
        task=task,
        fingerprints=fingerprints,
        missing_cut=missing_cut,
        missing_filter=missing_filter,
        cause=cause,
        formula=formula,
        answer=answer,
    )


def _cause(reader: _Reader) -> None:
    """Check a cause decision's `side` and `label`."""
    side = reader.get("side", str, required=True)
    if side not in CAUSE_SIDES:
        reader.fail("side", f"must be one of {', '.join(CAUSE_SIDES)}; got {side!r}")
    label = reader.get("label", str, required=True)
    if not label.strip():
        reader.fail("label", "must be the cause's words")
    if mask_digits(label) != label:
        reader.fail(
            "label", "carries a number of 5 or more digits; write each one as <n>"
        )
    for key in reader.data:
        if key not in ("side", "label"):
            reader.fail(str(key), "must be one of side and label")


def _tasks(root: _Reader) -> dict[str, str]:
    """The `tasks:` block: only `TASK_KEYS`, each an https:// link or #<issue>."""
    if root.data.get("tasks") is None:
        return {}
    reader = root.child("tasks", root.get("tasks", dict))
    for key in reader.data:
        if key not in TASK_KEYS:
            reader.fail(str(key), f"must be one of {', '.join(TASK_KEYS)}")
    tasks = {}
    for key in TASK_KEYS:
        value = reader.get(key, str)
        if value is None:
            continue
        if not _TASK.fullmatch(value):
            reader.fail(key, f"must be an https:// link or #<issue>; got {value!r}")
        tasks[key] = value
    return tasks


def load_view_config(path: Path) -> ViewConfig:
    """Read and validate one validation file.

    Args:
        path: A `src/cube/validation/<view>.yml` file.

    Returns:
        The parsed config.

    Raises:
        ConfigError: The file sits under `src/cube/model`, is not valid YAML, or
            a key is missing or wrong. The message names the file and key path.
    """
    path = Path(path)
    if "src/cube/model" in path.as_posix():
        raise ConfigError(
            f"{path}: validation files belong in src/cube/validation, "
            "not src/cube/model, which Cube loads as data model"
        )
    try:
        text = path.read_text()
        data = yaml.safe_load(text)
        # The node tree keeps each scalar's source text, which a decision's
        # values are checked against.
        tree = yaml.compose(text, Loader=yaml.SafeLoader)
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path}: not valid YAML: {exc}") from exc

    root = _Reader(path, "", data)
    # `shared:` holds YAML anchors that comparisons merge with `<<: *name`; the
    # loader reads the merged comparisons, never the block itself.
    root.get("shared", dict, default={})
    comparisons = [_comparison(r) for r in _list_of(root, "comparisons")]
    if not comparisons:
        root.fail("comparisons", "needs at least one comparison")
    ids = [c.id for c in comparisons]
    for i, cid in enumerate(ids):
        if ids.count(cid) > 1:
            root.fail(f"comparisons[{i}].id", f"duplicate comparison id {cid!r}")

    for key in ("anchors", "identities"):
        if key in root.data:
            root.fail(
                key,
                "delete this block; the validator checks Cube against dashboards only",
            )
    time_dimension = _identifier(root, "time_dimension")
    # Row comparisons cast the time dimension to DATE on both sides; without
    # it a date grain joins TIMESTAMP text to DATE text and nothing matches.
    if not time_dimension and any(c.rows for c in comparisons):
        root.fail("time_dimension", "is required when comparison rows are set")

    return ViewConfig(
        view=_identifier(root, "view", required=True),
        fact=_table_ref(root, "fact", required=True),
        email=root.get("email", str),
        time_dimension=time_dimension,
        comparisons=comparisons,
        decisions=[
            _decision(r, set(ids), _value_texts(tree, i))
            for i, r in enumerate(_list_of(root, "decisions"))
        ],
        tasks=_tasks(root),
        also_facts=_table_refs(root, "also_facts"),
    )


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def _list_item(
    lines: list[str], head: int, end: int, item_id: str
) -> tuple[int, int, int] | None:
    """Find the block-list item whose `id:` line is `item_id`.

    The `id:` may be the item's first line (`- id: x`) or any later line at the
    item's key indent, as when a `<<: *anchor` merge key comes first.

    Args:
        lines: The file's lines.
        head: Index of the block's key line.
        end: Index after the block's last line.
        item_id: The id to find.

    Returns:
        The item's first line, the line after it, and its key indent; or
        None when no item matches. Trailing blank lines and comments at or
        below the item's indent belong to what follows, not to the item.
    """
    item_indent = next(
        (
            _indent(lines[i])
            for i in range(head + 1, end)
            if re.match(r"\s*- ", lines[i])
        ),
        None,
    )
    if item_indent is None:
        return None
    key_indent = item_indent + 2
    marker = re.compile(rf"\s{{{item_indent}}}- ")
    wanted = re.compile(
        rf"(?:\s{{{item_indent}}}- |\s{{{key_indent}}})id:\s*['\"]?"
        rf"{re.escape(item_id)}['\"]?\s*(?:#.*)?"
    )
    starts = [i for i in range(head + 1, end) if marker.match(lines[i])]
    for n, start in enumerate(starts):
        stop = starts[n + 1] if n + 1 < len(starts) else end
        for i in range(start + 1, stop):
            if (
                lines[i].strip()
                and not _is_comment(lines[i])
                and _indent(lines[i]) < key_indent
            ):
                stop = i
                break
        if any(wanted.fullmatch(lines[i]) for i in range(start, stop)):
            while stop > start + 1 and (
                not lines[stop - 1].strip()
                or (
                    _is_comment(lines[stop - 1])
                    and _indent(lines[stop - 1]) <= item_indent
                )
            ):
                stop -= 1
            return start, stop, key_indent
    return None


def comparison_item(
    lines: list[str], comparison_id: str
) -> tuple[int, int, int] | None:
    """Find a comparison's item in the top-level `comparisons:` block.

    Returns:
        The item's first line, the line after it, and its key indent; or
        None when the block is missing, is not a block list, or holds no item
        with that id. Decisions are never searched.
    """
    head = next(
        (i for i, line in enumerate(lines) if re.match(r"comparisons\s*:", line)), None
    )
    if head is None:
        return None
    end = next(
        (i for i in range(head + 1, len(lines)) if re.match(r"[^\s#-]", lines[i])),
        len(lines),
    )
    return _list_item(lines, head, end, comparison_id)


def find_comparison(path: Path, comparison_id: str) -> None:
    """Check that a line edit can find a comparison's item.

    Raises:
        ConfigError: No block item of `comparisons:` carries that id, so
            `write_rebuild_check` could not write it.
    """
    if comparison_item(Path(path).read_text().splitlines(), comparison_id) is None:
        raise ConfigError(
            f"{path}: comparisons: no comparison with id {comparison_id!r}"
        )


def write_rebuild_check(path: Path, comparison_id: str, check: dict[str, Any]) -> None:
    """Rewrite one comparison's `rebuild_check:` key, leaving the rest of the
    file as is.

    The edit is line-based so comments and layout elsewhere survive.

    Args:
        path: The validation file.
        comparison_id: The `id` of the comparison to update.
        check: The new rebuild check (`fingerprint`, `cells`, `matched_at`,
            `workbook_updated_at`, `sheet_query_fingerprint`, `cuts`,
            `totals_skipped`, `missing_cuts`, `missing_filters`,
            `restricting_filters`).

    Raises:
        ConfigError: No comparison has that id.
    """
    path = Path(path)
    lines = path.read_text().splitlines()

    found = comparison_item(lines, comparison_id)
    if found is None:
        raise ConfigError(
            f"{path}: comparisons: no comparison with id {comparison_id!r}"
        )
    start, end, key_indent = found

    check_at = next(
        (
            i
            for i in range(start + 1, end)
            if re.match(rf"\s{{{key_indent}}}rebuild_check:", lines[i])
        ),
        None,
    )
    block = yaml.safe_dump(check, default_flow_style=False, sort_keys=False)
    new = [" " * key_indent + "rebuild_check:"] + [
        " " * (key_indent + 2) + line for line in block.splitlines()
    ]

    if check_at is None:
        # Insert after the last non-blank line of the comparison.
        insert = end
        while insert > start + 1 and not lines[insert - 1].strip():
            insert -= 1
        lines[insert:insert] = new
    else:
        check_end = check_at + 1
        while check_end < end and (
            not lines[check_end].strip()
            or len(lines[check_end]) - len(lines[check_end].lstrip()) > key_indent
        ):
            check_end += 1
        while not lines[check_end - 1].strip():
            check_end -= 1
        lines[check_at:check_end] = new

    path.write_text("\n".join(lines) + "\n")


def replace_text(path: Path, text: str) -> None:
    """Write `text` to `path` through a temp file in its folder and `os.replace`.

    A failed write leaves the old file whole instead of a truncated one.
    """
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _decisions_block(path: Path, lines: list[str]) -> tuple[int, int]:
    """The `decisions:` line and the line after its block, adding the key if absent.

    The block ends at the next top-level key; a comment at column 0 does not
    end it, so the caller trims trailing comments before appending.

    Raises:
        ConfigError: `decisions:` holds a flow list, null or other value, which
            a line edit cannot extend; appending a second key would make YAML
            drop every decision in the first.
    """
    head = next(
        (i for i, line in enumerate(lines) if re.match(r"decisions\s*:", line)), None
    )
    if head is None:
        while lines and not lines[-1].strip():
            lines.pop()
        lines.append("decisions:")
        head = len(lines) - 1
    else:
        value = re.sub(r"\s#.*$", "", lines[head].split(":", 1)[1]).strip()
        if value == "[]":
            lines[head] = "decisions:"
        elif value:
            raise ConfigError(
                f"{path}: decisions: is written as {value!r}; rewrite it as a "
                "block list (`- id: ...` items) or [] before adding decisions"
            )
    end = next(
        (i for i in range(head + 1, len(lines)) if re.match(r"[^\s#-]", lines[i])),
        len(lines),
    )
    return head, end


def _is_comment(line: str) -> bool:
    return line.lstrip().startswith("#")


def _holds(d: Decision, asked: dict[str, Any]) -> bool:
    """True when the loaded decision `d` carries every value `asked` set."""
    return (
        d.call == asked.get("call")
        and d.reason == asked.get("reason")
        and d.task == asked.get("task", "")
        and d.comparison == asked.get("comparison", "")
        and d.group == asked.get("group", {})
        and d.missing_cut == asked.get("missing_cut", "")
        and d.missing_filter == asked.get("missing_filter", "")
        and d.cause == asked.get("cause", {})
        and d.answer == asked.get("answer", "")
        and d.fingerprints == asked.get("fingerprints", {})
    )


def write_decision(path: Path, decision: dict[str, Any]) -> None:
    """Replace the `decisions:` item with `decision`'s id, or append it.

    The edit is line-based like `write_rebuild_check`, so comments and layout outside
    that item survive. Values YAML would rewrite (`9.50`, `010`, `no`) are
    written quoted.

    Args:
        path: The validation file.
        decision: The whole decision, `id` first, as the file holds it.

    Raises:
        ConfigError: The file does not load afterwards, or does not hold the
            values asked for (the original text is restored either way);
            `decisions:` is not a block list (see `_decisions_block`); or a
            decision with that id exists but no block item carries an `id:`
            line for it (a flow mapping), so a line edit cannot find it.
    """
    path = Path(path)
    decision_id = decision.get("id")
    if not isinstance(decision_id, str) or not decision_id:
        raise ConfigError(f"{path}: decisions: a decision needs a text id")
    original = path.read_text()
    lines = original.splitlines()
    head, end = _decisions_block(path, lines)

    first_item = next(
        (i for i in range(head + 1, end) if re.match(r"\s*- ", lines[i])), None
    )
    indent = (
        len(lines[first_item]) - len(lines[first_item].lstrip())
        if first_item is not None
        else 2
    )
    block = yaml.safe_dump([decision], default_flow_style=None, sort_keys=False)
    new = [" " * indent + line for line in block.splitlines()]

    found = _list_item(lines, head, end, decision_id)
    if found is None:
        if any(d.id == decision_id for d in load_view_config(path).decisions):
            raise ConfigError(
                f"{path}: decisions: {decision_id!r} is written as a flow "
                "mapping, so a line edit cannot find it; edit it by hand"
            )
        # Append after the block's last item line, before trailing blanks and
        # column-0 comments that lead into the next key.
        insert = end
        while insert > head + 1 and (
            not lines[insert - 1].strip() or lines[insert - 1].startswith("#")
        ):
            insert -= 1
        lines[insert:insert] = new
    else:
        start, stop, _ = found
        lines[start:stop] = new

    replace_text(path, "\n".join(lines) + "\n")
    try:
        found = [d for d in load_view_config(path).decisions if d.id == decision_id]
        if len(found) != 1:
            raise ConfigError(f"{path}: decisions: {decision_id!r} is not unique")
        if not _holds(found[0], decision):
            raise ConfigError(
                f"{path}: decisions: {decision_id!r} does not read back with the "
                "call, reason, task and key fields asked for"
            )
    except BaseException as exc:
        replace_text(path, original)
        if isinstance(exc, ConfigError):
            raise ConfigError(f"{exc} (not written; the file is unchanged)") from exc
        raise
