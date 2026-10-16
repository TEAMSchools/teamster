"""Load and check a dashboard's checks file, and the SQL helpers that read it."""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .snapshot import slug

OWNERS = ("cube", "dashboard", "source", "undecided")
RESERVED = (
    "match",
    "value_differs",
    "dashboard_only",
    "cube_only",
    "outside_scope",
    "outside_period",
    "unexplained",
)
ALL = "(All)"
# Minutes past each hour when the dashboard's scheduled refreshes sign in; the
# checks file's tableau_quiet_minutes overrides it per dashboard.
DEFAULT_QUIET = (0, 10)
# A run priced under this many dollars of BigQuery goes ahead without asking.
DEFAULT_COST_CAP_USD = 5.0
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_P_REF = re.compile(r"\{p\}([A-Za-z_][A-Za-z0-9_]*)")


class ConfigError(ValueError):
    """The checks file is missing a key or holds a value the tool cannot use."""


@dataclass(frozen=True)
class Window:
    start: dt.time
    end: dt.time
    extract_after: dt.time
    tz: str


@dataclass(frozen=True)
class Expr:
    """One named value read from each side: a column name, or SQL with {p}."""

    name: str
    tableau: str
    cube: str


@dataclass(frozen=True)
class FieldMap:
    caption: str
    tableau: str | None = None
    cube: str | None = None
    cube_column: str | None = None
    values: dict[str, str] = field(default_factory=dict)
    cube_values: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ParamValue:
    tableau: str | None = None
    cube_column: str | None = None
    cube_filters: tuple[dict, ...] = ()


@dataclass(frozen=True)
class MeasureMap:
    column: str
    cube: str | None
    scale: float = 1.0


@dataclass(frozen=True)
class SheetMap:
    name: str
    view: str
    dims: dict[str, FieldMap]
    measures: dict[str, MeasureMap]
    students: str | None = None


@dataclass(frozen=True)
class Click:
    source_sheet: str
    mark: str = "largest"


@dataclass(frozen=True)
class Cut:
    id: str
    filters: dict[str, str] = field(default_factory=dict)
    params: dict[str, str] = field(default_factory=dict)
    click: Click | None = None


@dataclass(frozen=True)
class Cause:
    id: str
    description: str
    where: str
    owner: str
    # Its rows cannot move any mapped measure, so they never block a pass.
    inert: bool = False


@dataclass(frozen=True)
class CubeRows:
    view: str
    date: str
    members: tuple[str, ...]
    filters: tuple[dict, ...] = ()


@dataclass(frozen=True)
class Checks:
    dashboard: str
    workbook: str
    workbook_luid: str
    review_project_luid: str
    dashboards: tuple[str, ...]
    datasource: str
    dashboard_table: str
    period_start: dt.date
    window: Window
    cost_cap_usd: float
    quiet_minutes: tuple[int, int]
    cube: CubeRows
    key: tuple[Expr, ...]
    compare: tuple[Expr, ...]
    labels: tuple[Expr, ...]
    student_key: str
    date_key: str
    scope_key: str | None
    causes: tuple[Cause, ...]
    filters: dict[str, FieldMap]
    params: dict[str, dict[str, ParamValue]]
    sheets: dict[str, SheetMap]
    cuts: tuple[Cut, ...]
    excluded_sheets: dict[str, str]
    # The dashboard's own filter values, applied to every cut before its filters.
    # A card may start on several values; a cut's own filter replaces them all.
    defaults: dict[str, tuple[str, ...]] = field(default_factory=dict)


def side_sql(expr: str, prefix: str) -> str:
    """SQL for one side's value: a bare column gets the prefix, SQL gets {p}."""
    if _IDENT.match(expr):
        return f'"{prefix}{expr}"'
    return expr.replace("{p}", prefix)


def lit(value: str | None) -> str:
    """A SQL literal. Always quoted, so Hyper coerces it to the column's type."""
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def _time(s: str) -> dt.time:
    h, m = str(s).split(":")
    return dt.time(int(h), int(m))


def _req(d: dict, key: str, where: str = "checks file"):
    if key not in d or d[key] in (None, ""):
        raise ConfigError(f"{where}: missing {key}")
    return d[key]


def _exprs(d: dict | None, where: str) -> tuple[Expr, ...]:
    out = []
    for name, v in (d or {}).items():
        out.append(
            Expr(
                name,
                _req(v, "tableau", f"{where}.{name}"),
                _req(v, "cube", f"{where}.{name}"),
            )
        )
    return tuple(out)


def _field(caption: str, v: dict) -> FieldMap:
    return FieldMap(
        caption=caption,
        tableau=v.get("tableau"),
        cube=v.get("cube"),
        cube_column=v.get("cube_column"),
        values={str(k): str(x) for k, x in (v.get("values") or {}).items()},
        cube_values={str(k): str(x) for k, x in (v.get("cube_values") or {}).items()},
    )


def _cut(i: int, v: dict) -> Cut:
    click = v.get("click")
    return Cut(
        id=str(_req(v, "id", f"cuts[{i}]")),
        filters={str(k): str(x) for k, x in (v.get("filters") or {}).items()},
        params={str(k): str(x) for k, x in (v.get("params") or {}).items()},
        click=Click(click["source_sheet"], click.get("mark", "largest"))
        if click
        else None,
    )


def _default(caption: str, value) -> tuple[str, ...]:
    """A filter card's default as 1 or more values."""
    if isinstance(value, list):
        if not value:
            raise ConfigError(f"defaults.{caption} is an empty list; name its values")
        return tuple(str(v) for v in value)
    return (str(value),)


def _cube_columns(expr: str | None) -> list[str]:
    """Cube columns a Cube-side value reads: itself when bare, else each {p}name."""
    if not expr:
        return []
    if _IDENT.match(expr):
        return [expr]
    return _P_REF.findall(expr)


def _unique_slugs(kind: str, names: list[str]) -> None:
    """Refuse names that share an export file name, so no export overwrites another."""
    seen: dict[str, str] = {}
    for n in names:
        s = slug(n)
        if s in seen:
            raise ConfigError(
                f"{kind} {seen[s]} and {n} share the export name {s}; rename one"
            )
        seen[s] = n


def _cost_cap(d: dict) -> float:
    if "cost_cap_gb" in d:
        raise ConfigError(
            "cost_cap_gb is replaced by cost_cap_usd (dollars of BigQuery)"
        )
    return float(d.get("cost_cap_usd", DEFAULT_COST_CAP_USD))


def load_checks(path: str | Path, *, for_plan: bool = False) -> Checks:
    """Read a checks file and refuse what the tool cannot use.

    Args:
        path: The checks YAML file.
        for_plan: Allow an empty datasource, as in the committed skeleton that
            `plan` runs on to draft the rest.

    Returns:
        The checks as dataclasses.

    Raises:
        ConfigError: A key is missing, a cause is malformed, the cuts do not
            start with a bare default, 2 sheets or cuts share an export name, or
            a Cube-side column is not among cube.members.
    """
    d = yaml.safe_load(Path(path).read_text()) or {}
    w = _req(d, "window")
    cube = _req(d, "cube")
    rows = _req(d, "rows")
    key = _exprs(_req(rows, "key", "rows"), "rows.key")
    names = {e.name for e in key}
    for k in ("student_key", "date_key"):
        if _req(rows, k, "rows") not in names:
            raise ConfigError(
                f"rows.{k} must name a key part ({', '.join(sorted(names))})"
            )
    scope_key = rows.get("scope_key")
    if scope_key is not None and scope_key not in names:
        raise ConfigError("rows.scope_key must name a key part")
    if scope_key is not None:
        member = next(e.cube for e in key if e.name == scope_key)
        if not _IDENT.match(member):
            # capture asks Cube for the scope by this member
            raise ConfigError(
                f"rows.scope_key's cube side must be a bare Cube member, not {member}"
            )

    causes = []
    for i, c in enumerate(d.get("causes") or []):
        cid = str(_req(c, "id", f"causes[{i}]"))
        if cid in RESERVED:
            raise ConfigError(f"cause id {cid} is reserved for a bucket")
        if c.get("owner") not in OWNERS:
            raise ConfigError(f"cause {cid}: owner must be one of {', '.join(OWNERS)}")
        inert = c.get("inert", False)
        if not isinstance(inert, bool):
            raise ConfigError(f"cause {cid}: inert must be true or false")
        causes.append(
            Cause(
                cid,
                _req(c, "description", cid),
                _req(c, "where", cid),
                c["owner"],
                inert,
            )
        )
    if len({c.id for c in causes}) != len(causes):
        raise ConfigError("cause ids must be unique")

    cuts = tuple(_cut(i, c) for i, c in enumerate(_req(d, "cuts")))
    first = cuts[0]
    if first.id != "default" or first.filters or first.params or first.click:
        raise ConfigError(
            "the first cut must be {id: default} with no filters, params or click"
        )
    if len({c.id for c in cuts}) != len(cuts):
        raise ConfigError("cut ids must be unique")

    view = _req(cube, "view", "cube")
    sheets = {}
    for name, s in (d.get("sheets") or {}).items():
        s = s or {}
        sheets[name] = SheetMap(
            name=name,
            view=s.get("view") or view,
            dims={h: _field(h, v or {}) for h, v in (s.get("dims") or {}).items()},
            measures={
                h: MeasureMap(
                    h, (v or {}).get("cube"), float((v or {}).get("scale", 1.0))
                )
                for h, v in (s.get("measures") or {}).items()
            },
            students=s.get("students"),
        )
    params = {
        cap: {
            str(val): ParamValue(
                (pv or {}).get("tableau"),
                (pv or {}).get("cube_column"),
                tuple((pv or {}).get("cube_filters") or ()),
            )
            for val, pv in (vals or {}).items()
        }
        for cap, vals in (d.get("params") or {}).items()
    }
    filters = {cap: _field(cap, v or {}) for cap, v in (d.get("filters") or {}).items()}
    defaults = {
        str(k): _default(str(k), v) for k, v in (d.get("defaults") or {}).items()
    }
    for cap in defaults:
        if cap not in filters:
            raise ConfigError(f"defaults: {cap} has no entry under filters")
    _unique_slugs("sheets", list(sheets))
    _unique_slugs("cuts", [c.id for c in cuts])
    compare = _exprs(rows.get("compare"), "rows.compare")
    labels = _exprs(rows.get("labels"), "rows.labels")
    members = set(_req(cube, "members", "cube"))
    uses = [
        *((f"rows.{part}.{e.name}", e.cube) for part, es in
          (("key", key), ("compare", compare), ("labels", labels)) for e in es),
        *((f"filters.{c}", f.cube_column) for c, f in filters.items()),
        *((f"sheets.{s}.dims.{h}", f.cube_column)
          for s, sm in sheets.items() for h, f in sm.dims.items()),
        *((f"params.{c}.{v}", pv.cube_column)
          for c, vals in params.items() for v, pv in vals.items()),
    ]  # fmt: skip
    for where, expr in uses:
        for col in _cube_columns(expr):
            if col not in members:
                raise ConfigError(
                    f"{where}: Cube column {col} is not in cube.members, "
                    "so capture never fetches it"
                )
    quiet = d.get("tableau_quiet_minutes") or DEFAULT_QUIET
    return Checks(
        dashboard=_req(d, "dashboard"),
        workbook=_req(d, "workbook"),
        workbook_luid=_req(d, "workbook_luid"),
        review_project_luid=_req(d, "review_project_luid"),
        dashboards=tuple(_req(d, "dashboards")),
        datasource=(d.get("datasource") or "") if for_plan else _req(d, "datasource"),
        dashboard_table=_req(d, "dashboard_table"),
        period_start=dt.date.fromisoformat(str(_req(d, "period_start"))),
        window=Window(
            _time(_req(w, "start", "window")),
            _time(_req(w, "end", "window")),
            _time(_req(w, "extract_after", "window")),
            _req(w, "tz", "window"),
        ),
        cost_cap_usd=_cost_cap(d),
        quiet_minutes=(int(quiet[0]), int(quiet[1])),
        cube=CubeRows(
            view,
            _req(cube, "date", "cube"),
            tuple(_req(cube, "members", "cube")),
            tuple(cube.get("filters") or ()),
        ),
        key=key,
        compare=compare,
        labels=labels,
        student_key=rows["student_key"],
        date_key=rows["date_key"],
        scope_key=scope_key,
        causes=tuple(causes),
        filters=filters,
        params=params,
        sheets=sheets,
        cuts=cuts,
        excluded_sheets={
            str(k): str(v) for k, v in (d.get("excluded_sheets") or {}).items()
        },
        defaults=defaults,
    )
