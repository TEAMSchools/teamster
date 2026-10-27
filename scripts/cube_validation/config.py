"""Load and validate the per-view Cube validation files.

Each file at `src/cube/validation/<view>.yml` records the dashboard-to-Cube
comparisons for one Cube view, the anchors and identities that check it, and
the decisions made about differences. Cube loads only `src/cube/model/`, so
these files never reach the semantic layer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NoReturn

import yaml

CALLS = ("deliberate", "fix_dashboard", "fix_cube", "domain_owner")
CALLS_NEEDING_TASK = ("fix_dashboard", "fix_cube", "domain_owner")


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


@dataclass(frozen=True)
class ViewConfig:
    view: str
    fact: str
    comparisons: list[Comparison]
    email: str | None = None
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


def _list_of(reader: _Reader, key: str) -> list[_Reader]:
    items = reader.get(key, list, default=[])
    return [reader.child(f"{key}[{i}]", item) for i, item in enumerate(items)]


def _pair(reader: _Reader) -> ColumnPair:
    return ColumnPair(
        dashboard=reader.get("dashboard", str, required=True),
        cube=reader.get("cube", str, required=True),
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
        proof = Proof(
            fingerprint=proof_reader.get("fingerprint", str, required=True),
            cells=proof_reader.data.get("cells"),
            proven_at=str(proof_reader.data.get("proven_at", "")),
        )

    return Comparison(
        id=reader.get("id", str, required=True),
        measure=reader.get("measure", str, required=True),
        confirmed=reader.get("confirmed", bool, default=False),
        workbook=reader.get("workbook", str),
        sheet=reader.get("sheet", str),
        dashboard_view=reader.get("dashboard_view", str),
        probe=probe,
        probe_sql=probe_sql,
        decimals=reader.get("decimals", int),
        dims=_pairs(reader, "dims"),
        filters=filters,
        defaults=reader.get("defaults", dict, default={}),
        cuts=reader.get("cuts", list, default=[]),
        scope=reader.get("scope", list, default=[]),
        rows=rows,
        proof=proof,
    )


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


def _decision(reader: _Reader, comparison_ids: set[str]) -> Decision:
    call = reader.get("call", str, required=True)
    if call not in CALLS:
        reader.fail("call", f"must be one of {', '.join(CALLS)}; got {call!r}")
    task = reader.get("task", str, default="")
    if call in CALLS_NEEDING_TASK and not task.strip():
        reader.fail("task", f"is required when call is {call}")
    comparison = reader.get("comparison", str, required=True)
    if comparison not in comparison_ids:
        reader.fail("comparison", f"{comparison!r} is not a comparison id")
    return Decision(
        id=reader.get("id", str, required=True),
        comparison=comparison,
        call=call,
        reason=reader.get("reason", str, required=True),
        group=reader.get("group", dict, default={}),
        task=task,
        fingerprints=reader.get("fingerprints", dict, default={}),
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
        data = yaml.safe_load(path.read_text())
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

    return ViewConfig(
        view=root.get("view", str, required=True),
        fact=root.get("fact", str, required=True),
        email=root.get("email", str),
        comparisons=comparisons,
        anchors=[_anchor(r) for r in _list_of(root, "anchors")],
        identities=[_identity(r) for r in _list_of(root, "identities")],
        decisions=[_decision(r, set(ids)) for r in _list_of(root, "decisions")],
    )


def write_proof(path: Path, comparison_id: str, proof: dict[str, Any]) -> None:
    """Rewrite one comparison's `proof:` key, leaving the rest of the file as is.

    The edit is line-based so comments and layout elsewhere survive.

    Args:
        path: The validation file.
        comparison_id: The `id` of the comparison to update.
        proof: The new proof (`fingerprint`, `cells`, `proven_at`).

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
