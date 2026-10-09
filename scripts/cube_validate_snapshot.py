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

import re
from dataclasses import dataclass

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
