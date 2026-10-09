"""The Tableau side of Cube validation: plan states, export them, clean up.

    uv run --with tableauhyperapi scripts/cube_validate_snapshot.py plan <checks.yml> [--twbx <file>]
    uv run --with tableauhyperapi scripts/cube_validate_snapshot.py open <checks.yml>
    uv run --with tableauhyperapi scripts/cube_validate_snapshot.py export <checks.yml> --states <file>
    uv run --with tableauhyperapi scripts/cube_validate_snapshot.py close <checks.yml>

`open`, `export` and `close` need the Tableau PAT, which only the pytest secrets
fixture provides, so they run inside a throwaway tests/test_zz_*.py.
Runbook: .claude/skills/cube-dashboard/SKILL.md.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass
from pathlib import Path

import defusedxml.ElementTree as SafeET

# [<datasource>].[<derivation>:<field>:<type>], or [<datasource>].[<field>]
_FIELD = re.compile(r"^\[([^\]]+)\]\.\[([^\]]+)\]$")
_DERIVED = re.compile(r"^[a-z]+:(.+):[a-z]+$")
_LITERAL = re.compile(r"\"([^\"]*)\"|'([^']*)'")
_USER = "{http://www.tableausoftware.com/xml/user}"


@dataclass(frozen=True)
class FilterCard:
    dashboard: str
    field: str
    caption: str
    datasource: str
    calculated: bool
    default_all: bool
    values: tuple[str, ...] = ()


@dataclass(frozen=True)
class Param:
    dashboard: str
    caption: str
    values: tuple[str, ...]
    default: str


@dataclass(frozen=True)
class Action:
    dashboard: str
    caption: str
    source_sheet: str
    kind: str
    target: str
    exclude: tuple[str, ...]


@dataclass
class Workbook:
    dashboards: dict[str, list[str]]
    filters: list[FilterCard]
    params: list[Param]
    actions: list[Action]


def default_caption(field: str) -> str:
    """The caption Tableau shows for a column that has none of its own."""
    if "_" not in field and field[:1].isupper():
        return field
    return " ".join(w[:1].upper() + w[1:] for w in field.split("_"))


def _unquote(v: str) -> str:
    return v[1:-1] if len(v) >= 2 and v[0] == v[-1] == '"' else v


def _split(param: str) -> tuple[str, str]:
    m = _FIELD.match(param)
    if not m:
        raise ValueError(f"not a field reference: {param}")
    inner = m.group(2)
    d = _DERIVED.match(inner)
    return m.group(1), d.group(1) if d else inner


def read_workbook(twb_text: str) -> Workbook:
    root = SafeET.fromstring(twb_text)
    columns: dict[tuple[str, str], object] = {}
    ds_caption: dict[str, str] = {}
    for ds in root.iter("datasource"):
        name = ds.get("name") or ""
        if ds.get("caption"):
            ds_caption[name] = ds.get("caption") or name
        for c in ds.findall("column"):
            columns[(name, (c.get("name") or "").strip("[]"))] = c

    dashboards: dict[str, list[str]] = {}
    filters: list[FilterCard] = []
    params: list[Param] = []
    for d in root.iter("dashboard"):
        dash = d.get("name") or ""
        sheets: list[str] = []
        for z in d.iter("zone"):
            kind = z.get("type-v2")
            if kind is None and z.get("name") and z.get("name") not in sheets:
                sheets.append(z.get("name") or "")
            elif kind == "filter":
                filters.append(_card(root, columns, ds_caption, dash, z))
            elif kind == "paramctrl":
                params.append(_param(columns, dash, z.get("param") or ""))
        dashboards[dash] = sheets
    actions = [_action(a) for a in root.iter("action")]
    return Workbook(dashboards, filters, params, actions)


def _card(root, columns, ds_caption, dash: str, z) -> FilterCard:
    ds, field = _split(z.get("param") or "")
    col = columns.get((ds, field))
    calc = col.find("calculation") if col is not None else None
    caption = (col.get("caption") if col is not None else None) or default_caption(
        field
    )
    values: tuple[str, ...] = ()
    if calc is not None:
        found = [a or b for a, b in _LITERAL.findall(calc.get("formula") or "")]
        values = tuple(dict.fromkeys(found))
    return FilterCard(
        dashboard=dash,
        field=field,
        caption=caption,
        datasource=ds_caption.get(ds, ds),
        calculated=calc is not None,
        default_all=_default_all(root, z.get("name") or "", z.get("param") or ""),
        values=values,
    )


def _default_all(root, sheet: str, param: str) -> bool:
    """True unless the card's own sheet saves a member selection for the field."""
    for w in root.iter("worksheet"):
        if w.get("name") != sheet:
            continue
        for f in w.iter("filter"):
            if f.get("column") != param:
                continue
            g = f.find("groupfilter")
            if g is None:
                return True
            return (
                g.get("function") == "level-members"
                or g.get(f"{_USER}ui-enumeration") == "all"
            )
    return True


def _param(columns, dash: str, ref: str) -> Param:
    _, name = _split(ref)
    col = columns[("Parameters", name)]
    caption = col.get("caption") or name
    default = _unquote(col.get("value") or "")
    if col.get("param-domain-type") != "list":
        return Param(dash, caption, (), default)
    values = tuple(_unquote(m.get("value") or "") for m in col.iter("member"))
    return Param(dash, caption, values, default)


def _action(a) -> Action:
    src = a.find("source")
    dash = src.get("dashboard") if src is not None else ""
    sheet = src.get("worksheet") if src is not None else ""
    cmd = a.find("command")
    if cmd is None:
        return Action(dash or "", a.get("caption") or "", sheet or "", "link", "", ())
    p = {x.get("name"): x.get("value") or "" for x in cmd.findall("param")}
    kind = {"tsc:tsl-filter": "filter", "tsc:brush": "highlight"}.get(
        cmd.get("command") or "", "link"
    )
    exclude = tuple(s for s in p.get("exclude", "").split(",") if s)
    return Action(
        dash or "",
        a.get("caption") or "",
        sheet or "",
        kind,
        p.get("target", ""),
        exclude,
    )


class ReviewCopyError(ValueError):
    """The review copy could not be built safely."""


_SELF_CLOSING_ACTION = re.compile(r"<filter [^>]*\[Action \([^>]*/>\s*")
_PAIRED_ACTION = re.compile(r"<filter [^>]*\[Action \([^>]*[^/]>.*?</filter>\s*", re.S)
_ACTION_SLICE = re.compile(r"<column>\[[^\]]+\]\.\[Action \([^\]]*\]</column>\s*")


def _hidden(text: str) -> dict[str, bool]:
    root = SafeET.fromstring(text)
    return {
        w.get("name") or "": w.get("hidden") == "true"
        for w in root.iter("window")
        if w.get("class") == "worksheet"
    }


def _expose(text: str, sheets: list[str]) -> str:
    for name in sheets:
        pattern = re.compile(
            r"(<window class='worksheet') hidden='true'( name='"
            + re.escape(name)
            + r"')"
        )
        text, n = pattern.subn(r"\1\2", text)
        if n > 1:
            raise ReviewCopyError(f"{name}: {n} windows matched, expected at most 1")
    return text


def _strip_click_filters(text: str, sheet: str) -> str:
    start = text.find(f"<worksheet name='{sheet}'>")
    if start < 0:
        return text
    end = text.index("</worksheet>", start)
    block = _SELF_CLOSING_ACTION.sub("", text[start:end])
    block = _PAIRED_ACTION.sub("", block)
    block = _ACTION_SLICE.sub("", block)
    if "[Action (" in block:
        raise ReviewCopyError(f"{sheet}: a saved click filter survived")
    return text[:start] + block + text[end:]


def review_copy(twb_text: str, dashboards: list[str]) -> str:
    """The workbook with each named dashboard's sheets exposed and clicks reproducible."""
    wb = read_workbook(twb_text)
    missing = [d for d in dashboards if d not in wb.dashboards]
    if missing:
        raise ReviewCopyError(f"no dashboard named {', '.join(missing)}")
    sheets = [s for d in dashboards for s in wb.dashboards[d]]
    before = _hidden(twb_text)

    out = _expose(twb_text, sheets)
    n_none = out.count("<param name='on-empty' value='none' />")
    out = out.replace(
        "<param name='on-empty' value='none' />",
        "<param name='on-empty' value='all' />",
    )
    if out.count("<param name='on-empty' value='none' />"):
        raise ReviewCopyError("an on-empty setting is still none")
    targets = {
        s
        for a in wb.actions
        if a.kind == "filter" and a.dashboard in dashboards
        for s in wb.dashboards.get(a.target, [])
        if s not in a.exclude
    }
    for s in sorted(targets):
        out = _strip_click_filters(out, s)

    after = _hidden(out)
    still = [s for s in sheets if after.get(s)]
    if still:
        raise ReviewCopyError(f"still hidden: {', '.join(still)}")
    changed = [s for s in before if s not in sheets and before[s] != after.get(s)]
    if changed:
        raise ReviewCopyError(f"other windows changed: {', '.join(changed)}")
    if n_none and "<param name='on-empty' value='all' />" not in out:
        raise ReviewCopyError("on-empty edit did not land")
    return out


def views_to_hide(twb_text: str, keep: set[str]) -> list[str]:
    """Publishable windows to hide on publish, so only the review views go live."""
    root = SafeET.fromstring(twb_text)
    publishable = [
        w.get("name") or ""
        for w in root.iter("window")
        if w.get("class") in ("worksheet", "dashboard") and w.get("hidden") != "true"
    ]
    return sorted(n for n in publishable if n not in keep)


EXTRACT = '"Extract"."Extract"'
BLANK_KEY = "∅"


class Hyper:
    """Read-only SQL over one .hyper file; use as a context manager."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def __enter__(self):
        # trunk-ignore(pyright/reportMissingImports): added per run with uv run --with
        from tableauhyperapi import Connection, HyperProcess, Telemetry

        self._hp = HyperProcess(Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU)
        self._con = Connection(self._hp.endpoint, str(self.path))
        return self

    def __exit__(self, *exc):
        self._con.close()
        self._hp.close()

    def query(self, sql: str) -> list[tuple]:
        with self._con.execute_query(sql) as result:
            return [tuple(r) for r in result]

    def columns(self) -> list[str]:
        # trunk-ignore(pyright/reportMissingImports): added per run with uv run --with
        from tableauhyperapi import TableName

        d = self._con.catalog.get_table_definition(TableName("Extract", "Extract"))
        return [c.name.unescaped for c in d.columns]


def _from(where: str | None) -> str:
    return EXTRACT + (f" where {where}" if where else "")


def _key(field: str) -> str:
    return f"coalesce(cast(\"{field}\" as text), '{BLANK_KEY}')"


def profile(hyper, fields, student="student_number", where=None):
    """Each field's values with their distinct students, largest first."""
    out = {}
    for f in fields:
        rows = hyper.query(
            f'select cast("{f}" as text), count(distinct "{student}") '
            f"from {_from(where)} group by 1 order by 2 desc, 1"
        )
        out[f] = [(v, int(n)) for v, n in rows]
    return out


def nesting(hyper, fields, where=None):
    """How well each finer field predicts each coarser one (Goodman-Kruskal lambda).

    Blank counts as a value. Lambda corrects for a lopsided parent: a parent with
    one dominant value is predicted well by anything, which is not nesting.
    """
    t = _from(where)
    n = hyper.query(f"select count(*) from {t}")[0][0]
    distinct = {
        f: int(hyper.query(f"select count(distinct {_key(f)}) from {t}")[0][0])
        for f in fields
    }
    base = {
        f: hyper.query(
            f"select max(c) from (select count(*) c from {t} group by {_key(f)}) x"
        )[0][0]
        / n
        for f in fields
    }
    scores = {}
    for child, parent in itertools.permutations(fields, 2):
        if distinct[child] <= distinct[parent] or base[parent] >= 1:
            continue
        hit = hyper.query(
            "select sum(m) from (select max(c) m from (select "
            f"{_key(child)} ch, {_key(parent)} pa, count(*) c from {t} "
            "group by 1, 2) x group by ch) y"
        )[0][0]
        scores[(child, parent)] = (hit / n - base[parent]) / (1 - base[parent])
    return scores, distinct
