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
DECISION_OWNERS = ("dashboard", "cube", "accepted")
# Checks-file sections that describe findings, not the Tableau-to-Cube mapping,
# so editing one does not change the mapping's fingerprint.
MAPPING_EXCLUDED = ("causes", "decisions", "must_cover", "probes")
# Marks a key absent from the checks file while loading, apart from an explicit null.
MISSING = object()
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
    # For a measure that names this parameter: the Cube member this value swaps
    # in, its view, and members whose name differs on that view.
    measure: str | None = None
    view: str | None = None
    rename: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class MeasureMap:
    column: str
    cube: str | None
    scale: float = 1.0
    # The parameter whose values swap this measure; `cube` is its default.
    param: str | None = None


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
class MustCover:
    """A measure the dashboard owner needs Cube to answer, and where it maps."""

    name: str
    source: str
    # (member, view); None when Cube has no such member yet.
    cube: tuple[str, str] | None
    column: str
    # (caption, value) of the selector that picks this measure, if any.
    param: tuple[str, str] | None
    # Names from rows.compare that explain this measure's row-level gaps.
    rows: tuple[str, ...]


@dataclass(frozen=True)
class Probe:
    """A pair of SQL texts over the extract that test one suspected formula gap."""

    id: str
    measure: str
    param: tuple[str, str] | None
    dashboard: str
    candidate: str


@dataclass(frozen=True)
class Decision:
    """Who owns a formula gap on a mapped measure, and the rule behind it."""

    measure: str
    param: tuple[str, str] | None
    owner: str
    rule: str
    probe: str | None
    cuts: tuple[str, ...]
    sheets: tuple[str, ...]
    task: str


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
    must_cover: tuple[MustCover, ...] = ()
    probes: tuple[Probe, ...] = ()
    decisions: tuple[Decision, ...] = ()


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


def _measure(v) -> str | None:
    """A selector value's measure; absent and null both store None."""
    return None if v is MISSING else v


def _pair(v: dict | None, where: str) -> tuple[str, str] | None:
    """A `{caption: value}` single pair, or None when absent."""
    if not v:
        return None
    if not isinstance(v, dict) or len(v) != 1:
        raise ConfigError(f"{where}: param must be a single {{caption: value}} pair")
    ((cap, val),) = v.items()
    return (str(cap), str(val))


def _mapped(
    column: str,
    param: tuple[str, str] | None,
    sheets: dict[str, SheetMap],
    params: dict[str, dict[str, ParamValue]],
) -> list[tuple[str, str | None, str]]:
    """(sheet, member, view) for the sheets exporting this measure header."""
    out = []
    for sm in sheets.values():
        m = sm.measures.get(column)
        if m is None:
            continue
        pv = None
        if param and m.param == param[0]:
            pv = params.get(param[0], {}).get(param[1])
        if pv is not None:
            out.append((sm.name, pv.measure, pv.view or sm.view))
        else:
            out.append((sm.name, m.cube, sm.view))
    return out


def _must_cover(
    d: dict,
    sheets: dict[str, SheetMap],
    params: dict[str, dict[str, ParamValue]],
    compare: tuple[Expr, ...],
) -> tuple[MustCover, ...]:
    names = {e.name for e in compare}
    out = []
    for i, e in enumerate(d.get("must_cover") or []):
        where = f"must_cover[{i}]"
        name = str(_req(e, "name", where))
        t = _req(e, "tableau", where)
        column = str(_req(t, "column", f"{where}.tableau"))
        param = _pair(t.get("param"), f"{where}.tableau")
        c = e.get("cube")
        cube = (
            (
                str(_req(c, "member", f"{where}.cube")),
                str(_req(c, "view", f"{where}.cube")),
            )
            if c
            else None
        )
        rows = tuple(str(r) for r in (e.get("rows") or ()))
        for r in rows:
            if r not in names:
                raise ConfigError(
                    f"must_cover {name}: rows names {r}, not in rows.compare"
                )
        if cube is not None:
            for sheet, member, view in _mapped(column, param, sheets, params):
                if member is not None and (member, view) != cube:
                    raise ConfigError(
                        f"must_cover {name}: cube {cube[0]} on {cube[1]} differs "
                        f"from {member} on {view}, which sheet {sheet} maps "
                        f"{column} to"
                    )
        out.append(
            MustCover(name, str(_req(e, "source", where)), cube, column, param, rows)
        )
    return tuple(out)


def _probes(d: dict) -> tuple[Probe, ...]:
    out = []
    for i, p in enumerate(d.get("probes") or []):
        where = f"probes[{i}]"
        out.append(
            Probe(
                str(_req(p, "id", where)),
                str(_req(p, "measure", where)),
                _pair(p.get("param"), where),
                str(_req(p, "dashboard", where)),
                str(_req(p, "candidate", where)),
            )
        )
    if len({p.id for p in out}) != len(out):
        raise ConfigError("probe ids must be unique")
    return tuple(out)


def _decisions(
    d: dict,
    sheets: dict[str, SheetMap],
    params: dict[str, dict[str, ParamValue]],
    probes: tuple[Probe, ...],
    cuts: tuple[Cut, ...],
) -> tuple[Decision, ...]:
    probe_ids = {p.id for p in probes}
    out = []
    for i, e in enumerate(d.get("decisions") or []):
        where = f"decisions[{i}]"
        measure = str(_req(e, "measure", where))
        param = _pair(e.get("param"), where)
        if not any(measure in sm.measures for sm in sheets.values()):
            raise ConfigError(f"{where}: {measure} is not a mapped sheet measure")
        if param and not any(
            sm.measures[measure].param == param[0]
            and param[1] in params.get(param[0], {})
            for sm in sheets.values()
            if measure in sm.measures
        ):
            raise ConfigError(
                f"{where}: {param[1]} is not a listed {param[0]} value for {measure}"
            )
        owner = e.get("owner")
        if owner not in DECISION_OWNERS:
            raise ConfigError(
                f"{where}: owner must be one of {', '.join(DECISION_OWNERS)}"
            )
        probe = e.get("probe")
        if probe is not None and probe not in probe_ids:
            raise ConfigError(f"{where}: probe {probe} is not under probes")
        dcuts = tuple(str(c) for c in (e.get("cuts") or ()))
        dsheets = tuple(str(s) for s in (e.get("sheets") or ()))
        if owner == "accepted" and not (dcuts or dsheets):
            raise ConfigError(f"{where}: an accepted decision needs cuts or sheets")
        for c in dcuts:
            if c not in {x.id for x in cuts}:
                raise ConfigError(f"{where}: cut {c} is not under cuts")
        for s in dsheets:
            if s not in sheets:
                raise ConfigError(f"{where}: sheet {s} is not under sheets")
        out.append(
            Decision(
                measure,
                param,
                owner,
                str(_req(e, "rule", where)),
                None if probe is None else str(probe),
                dcuts,
                dsheets,
                str(e.get("task") or ""),
            )
        )
    return tuple(out)


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
                    h,
                    (v or {}).get("cube"),
                    float((v or {}).get("scale", 1.0)),
                    (v or {}).get("param"),
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
                _measure((pv or {}).get("measure", MISSING)),
                (pv or {}).get("view"),
                {str(k): str(x) for k, x in ((pv or {}).get("rename") or {}).items()},
            )
            for val, pv in (vals or {}).items()
        }
        for cap, vals in (d.get("params") or {}).items()
    }
    raw_params = {
        cap: {str(val): pv or {} for val, pv in (vals or {}).items()}
        for cap, vals in (d.get("params") or {}).items()
    }
    for s, sm in sheets.items():
        for h, m in sm.measures.items():
            if m.param is None:
                continue
            if m.param not in params:
                raise ConfigError(f"sheets.{s}.measures.{h}: no param {m.param}")
            for val, pv in params[m.param].items():
                if "measure" not in raw_params[m.param][val]:
                    # the default member would be compared under this value
                    raise ConfigError(
                        f"params.{m.param}.{val}: {s}/{h} swaps on it, so it needs a measure"
                    )
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
    probes = _probes(d)
    must_cover = _must_cover(d, sheets, params, compare)
    decisions = _decisions(d, sheets, params, probes, cuts)
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
        must_cover=must_cover,
        probes=probes,
        decisions=decisions,
    )
