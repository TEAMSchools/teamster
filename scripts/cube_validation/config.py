"""Load and validate the per-view Cube validation files.

Each file at `src/cube/validation/<view>.yml` records the dashboard-to-Cube
comparisons for one Cube view, the anchors and identities that check it, and
the decisions made about differences. Cube loads only `src/cube/model/`, so
these files never reach the semantic layer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, NoReturn

import yaml

CALLS = ("deliberate", "fix_dashboard", "fix_cube", "domain_owner")
CALLS_NEEDING_TASK = ("fix_dashboard", "fix_cube", "domain_owner")
_TASK = re.compile(r"https://\S+|#\d+")
SCOPE_OPERATORS = ("equals", "set")
# How `prove` treats export rows that share every mapped dim: `refuse` fails
# the proof; `sum` adds them, which is right only for a field that adds up.
SPLIT_ROWS = ("refuse", "sum")

# Every config value the SQL builders interpolate must pass one of these, so a
# validation file cannot carry SQL text into a query.
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_TABLE_REF = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*")


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


@dataclass(frozen=True)
class Proof:
    fingerprint: str
    cells: Any
    proven_at: str
    workbook_updated_at: str = ""
    probe_fingerprint: str = ""
    # The cut labels the REST export proved; None when the proof predates them.
    cuts: list[str] | None = None
    # Total rows the export showed and the proof skipped; None when the proof
    # predates the count.
    totals_skipped: int | None = None
    # Sheet fields with no Cube member, by caption: cuts on the sheet's shelves,
    # filters, and the filters that narrow the sheet now. None when the proof
    # predates them.
    missing_cuts: list[str] | None = None
    missing_filters: list[str] | None = None
    restricting_filters: list[str] | None = None


@dataclass(frozen=True)
class Comparison:
    id: str
    measure: str
    confirmed: bool = False
    workbook: str | None = None
    sheet: str | None = None
    dashboard_view: str | None = None
    probe: str | None = None
    probe_sql: str | None = None
    decimals: int | None = None
    dims: list[ColumnPair] = field(default_factory=list)
    filters: dict[str, ColumnPair] = field(default_factory=dict)
    defaults: dict[str, Any] = field(default_factory=dict)
    cuts: list[dict[str, Any]] = field(default_factory=list)
    scope: list[dict[str, Any]] = field(default_factory=list)
    rows: RowSpec | None = None
    proof: Proof | None = None
    # The sheet field to compare, by its exported caption: a column header, or
    # a `Measure Names` value in a long export.
    sheet_field: str | None = None
    split_rows: str = "refuse"


@dataclass(frozen=True)
class Anchor:
    measure: str
    value: float
    source: str
    as_of: Any = None
    date_range: list[Any] = field(default_factory=list)
    filters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Identity:
    name: str
    left: str
    right: str


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


@dataclass(frozen=True)
class ViewConfig:
    view: str
    fact: str
    comparisons: list[Comparison]
    email: str | None = None
    time_dimension: str | None = None
    anchors: list[Anchor] = field(default_factory=list)
    identities: list[Identity] = field(default_factory=list)
    decisions: list[Decision] = field(default_factory=list)


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


def _table_ref(reader: _Reader, key: str, *, required=False) -> str | None:
    """A `dataset.table` string that is safe to interpolate into SQL."""
    value = reader.get(key, str, required=required)
    if value is not None and not _TABLE_REF.fullmatch(value):
        reader.fail(key, f"must be dataset.table of plain identifiers; got {value!r}")
    return value


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


def _comparison(reader: _Reader) -> Comparison:
    probe = reader.get("probe", str)
    probe_sql = reader.get("probe_sql", str)
    if probe and probe_sql:
        reader.fail("probe", "set either probe or probe_sql, not both")

    filters = {}
    for caption, spec in reader.get("filters", dict, default={}).items():
        filters[caption] = _pair(reader.child(f"filters.{caption}", spec))

    rows = None
    if reader.data.get("rows") is not None:
        rows_reader = reader.child("rows", reader.data["rows"])
        rows = RowSpec(
            grain=_pairs(rows_reader, "grain"), values=_pairs(rows_reader, "values")
        )

    proof = None
    if reader.data.get("proof") is not None:
        proof_reader = reader.child("proof", reader.data["proof"])
        cuts = proof_reader.get("cuts", list)
        totals_skipped = proof_reader.get("totals_skipped", int)
        if totals_skipped is not None and totals_skipped < 0:
            proof_reader.fail("totals_skipped", "must be 0 or more")
        proof = Proof(
            cuts=None if cuts is None else [str(c) for c in cuts],
            fingerprint=proof_reader.get("fingerprint", str, required=True),
            cells=proof_reader.data.get("cells"),
            proven_at=str(proof_reader.data.get("proven_at", "")),
            workbook_updated_at=str(proof_reader.data.get("workbook_updated_at", "")),
            probe_fingerprint=str(proof_reader.data.get("probe_fingerprint", "")),
            totals_skipped=totals_skipped,
            missing_cuts=_captions(proof_reader, "missing_cuts"),
            missing_filters=_captions(proof_reader, "missing_filters"),
            restricting_filters=_captions(proof_reader, "restricting_filters"),
        )

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
        probe=probe,
        probe_sql=probe_sql,
        decimals=reader.get("decimals", int),
        dims=_pairs(reader, "dims"),
        filters=filters,
        defaults=reader.get("defaults", dict, default={}),
        cuts=reader.get("cuts", list, default=[]),
        scope=[_scope_entry(r) for r in _list_of(reader, "scope")],
        rows=rows,
        proof=proof,
        sheet_field=reader.get("sheet_field", str),
        split_rows=split_rows,
    )


def _captions(reader: _Reader, key: str) -> list[str] | None:
    values = reader.get(key, list)
    return None if values is None else [str(v) for v in values]


def _scope_entry(reader: _Reader) -> dict[str, Any]:
    """A Cube-only row filter: `equals` takes `values`; `set` (not null) none."""
    cube = _identifier(reader, "cube", required=True)
    operator = reader.get("operator", str, default="equals")
    if operator not in SCOPE_OPERATORS:
        reader.fail(
            "operator", f"must be one of {', '.join(SCOPE_OPERATORS)}; got {operator!r}"
        )
    if operator == "set":
        if reader.data.get("values") is not None:
            reader.fail("values", "must be absent when operator is set")
        return {"cube": cube, "operator": operator}
    values = reader.get("values", list, required=True)
    return {"cube": cube, "operator": operator, "values": values}


def _anchor(reader: _Reader) -> Anchor:
    return Anchor(
        measure=reader.get("measure", str, required=True),
        value=reader.get("value", (int, float), required=True),
        source=reader.get("source", str, required=True),
        as_of=reader.data.get("as_of"),
        date_range=reader.get("date_range", list, default=[]),
        filters=reader.get("filters", dict, default={}),
    )


def _identity(reader: _Reader) -> Identity:
    return Identity(
        name=reader.get("name", str, required=True),
        left=reader.get("left", str, required=True),
        right=reader.get("right", str, required=True),
    )


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
                "triage line shows it",
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
    missing_cut = reader.get("missing_cut", str, default="")
    missing_filter = reader.get("missing_filter", str, default="")
    named = [
        k for k in ("group", "missing_cut", "missing_filter") if reader.data.get(k)
    ]
    if len(named) > 1:
        reader.fail(named[1], "set only one of group, missing_cut and missing_filter")
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
    return Decision(
        id=reader.get("id", str, required=True),
        comparison=comparison,
        call=call,
        reason=reader.get("reason", str, required=True),
        group=group,
        task=task,
        fingerprints=reader.get("fingerprints", dict, default={}),
        missing_cut=missing_cut,
        missing_filter=missing_filter,
    )


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
    comparisons = [_comparison(r) for r in _list_of(root, "comparisons")]
    if not comparisons:
        root.fail("comparisons", "needs at least one comparison")
    ids = [c.id for c in comparisons]
    for i, cid in enumerate(ids):
        if ids.count(cid) > 1:
            root.fail(f"comparisons[{i}].id", f"duplicate comparison id {cid!r}")

    anchors = [_anchor(r) for r in _list_of(root, "anchors")]
    time_dimension = _identifier(root, "time_dimension")
    # Row comparisons cast the time dimension to DATE on both sides; without
    # it a date grain joins TIMESTAMP text to DATE text and nothing matches.
    if not time_dimension and (anchors or any(c.rows for c in comparisons)):
        root.fail(
            "time_dimension", "is required when anchors or comparison rows are set"
        )

    return ViewConfig(
        view=_identifier(root, "view", required=True),
        fact=_table_ref(root, "fact", required=True),
        email=root.get("email", str),
        time_dimension=time_dimension,
        comparisons=comparisons,
        anchors=anchors,
        identities=[_identity(r) for r in _list_of(root, "identities")],
        decisions=[
            _decision(r, set(ids), _value_texts(tree, i))
            for i, r in enumerate(_list_of(root, "decisions"))
        ],
    )


def write_proof(path: Path, comparison_id: str, proof: dict[str, Any]) -> None:
    """Rewrite one comparison's `proof:` key, leaving the rest of the file as is.

    The edit is line-based so comments and layout elsewhere survive.

    Args:
        path: The validation file.
        comparison_id: The `id` of the comparison to update.
        proof: The new proof (`fingerprint`, `cells`, `proven_at`,
            `workbook_updated_at`, `probe_fingerprint`, `cuts`,
            `totals_skipped`, `missing_cuts`, `missing_filters`,
            `restricting_filters`).

    Raises:
        ConfigError: No comparison has that id.
    """
    path = Path(path)
    lines = path.read_text().splitlines()

    start = next(
        (
            i
            for i, line in enumerate(lines)
            if re.fullmatch(
                rf"\s*- id:\s*['\"]?{re.escape(comparison_id)}['\"]?\s*", line
            )
        ),
        None,
    )
    if start is None:
        raise ConfigError(
            f"{path}: comparisons: no comparison with id {comparison_id!r}"
        )

    item_indent = len(lines[start]) - len(lines[start].lstrip())
    key_indent = item_indent + 2

    # The comparison ends at the next line indented at or below its `- ` marker.
    end = len(lines)
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if line.strip() and len(line) - len(line.lstrip()) <= item_indent:
            end = i
            break

    proof_at = next(
        (
            i
            for i in range(start + 1, end)
            if re.match(rf"\s{{{key_indent}}}proof:", lines[i])
        ),
        None,
    )
    block = yaml.safe_dump(proof, default_flow_style=False, sort_keys=False)
    new = [" " * key_indent + "proof:"] + [
        " " * (key_indent + 2) + line for line in block.splitlines()
    ]

    if proof_at is None:
        # Insert after the last non-blank line of the comparison.
        insert = end
        while insert > start + 1 and not lines[insert - 1].strip():
            insert -= 1
        lines[insert:insert] = new
    else:
        proof_end = proof_at + 1
        while proof_end < end and (
            not lines[proof_end].strip()
            or len(lines[proof_end]) - len(lines[proof_end].lstrip()) > key_indent
        ):
            proof_end += 1
        while not lines[proof_end - 1].strip():
            proof_end -= 1
        lines[proof_at:proof_end] = new

    path.write_text("\n".join(lines) + "\n")
