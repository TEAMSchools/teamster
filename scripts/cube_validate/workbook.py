"""Read a Tableau workbook, build its review copy, unpack its extracts.

Ported from the cell-first tool (68c59490a5); proven on the DDI Suite run.
"""

from __future__ import annotations

import datetime as dt
import re
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path

# trunk-ignore(bandit/B406): escape only writes entities into a string, it parses no XML
from xml.sax.saxutils import escape

import defusedxml.ElementTree as SafeET

_FIELD = re.compile(r"^\[([^\]]+)\]\.\[([^\]]+)\]$")
_DERIVED = re.compile(r"^[a-z]+:(.+):[a-z]+$")
_LITERAL = re.compile(r"\"([^\"]*)\"|'([^']*)'")
_USER = "{http://www.tableausoftware.com/xml/user}"


def is_number(s: str) -> bool:
    try:
        float(s.replace(",", "").rstrip("%"))
    except ValueError:
        return False
    return True


@dataclass(frozen=True)
class FilterCard:
    dashboard: str
    field: str
    caption: str
    datasource: str
    calculated: bool
    default_all: bool
    values: tuple[str, ...] = ()
    # What the card's sheet saves as selected when default_all is False.
    default_values: tuple[str, ...] = ()


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


def caption_of(el, field: str) -> str:
    """The caption Tableau shows for a column: its stored caption, else the raw
    field name. vf takes this caption, and ignores any other silently."""
    caption = el.get("caption") if el is not None else None
    return caption or field


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
            col_name = (c.get("name") or "").strip("[]")
            columns[(name, col_name)] = c

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
    caption = caption_of(col, field)
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
        default_values=_default_values(root, z.get("name") or "", z.get("param") or ""),
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


def _default_values(root, sheet: str, param: str) -> tuple[str, ...]:
    """The members a card's sheet saves as selected (empty when it saves All)."""
    if _default_all(root, sheet, param):
        return ()
    for w in root.iter("worksheet"):
        if w.get("name") != sheet:
            continue
        for f in w.iter("filter"):
            if f.get("column") == param:
                found = [_unquote(g.get("member") or "") for g in f.iter("groupfilter")]
                return tuple(v for v in found if v)
    return ()


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


def _xml_name(name: str) -> str:
    """A sheet name as the .twb writes it inside a single-quoted attribute."""
    return escape(name, {"'": "&apos;", '"': "&quot;"})


def _expose(text: str, sheets: list[str]) -> str:
    for name in sheets:
        pattern = re.compile(
            r"(<window class='worksheet') hidden='true'( name='"
            + re.escape(_xml_name(name))
            + r"')"
        )
        text, n = pattern.subn(r"\1\2", text)
        if n > 1:
            raise ReviewCopyError(f"{name}: {n} windows matched, expected at most 1")
    return text


def _strip_click_filters(text: str, sheet: str) -> str:
    start = text.find(f"<worksheet name='{_xml_name(sheet)}'>")
    if start < 0:
        raise ReviewCopyError(f"{sheet}: no worksheet by that name to strip")
    end = text.index("</worksheet>", start)
    block = _SELF_CLOSING_ACTION.sub("", text[start:end])
    block = _PAIRED_ACTION.sub("", block)
    block = _ACTION_SLICE.sub("", block)
    if "[Action (" in block:
        raise ReviewCopyError(f"{sheet}: a saved click filter survived")
    return text[:start] + block + text[end:]


_COLUMN = re.compile(r"<column [^>]*>")
_FORMAT = re.compile(r" default-format='[^']*'")


def _strip_measure_formats(text: str) -> tuple[str, int]:
    """Drops each measure column's own number format, which the CSV export uses.

    A parameter column keeps its format: it is not a measure anyone compares.
    """
    n = 0

    def one(m: re.Match) -> str:
        nonlocal n
        tag = m.group(0)
        if "role='measure'" not in tag or "param-domain-type" in tag:
            return tag
        out, k = _FORMAT.subn("", tag)
        n += k
        return out

    return _COLUMN.sub(one, text), n


def display_formats(twb_text: str) -> dict[tuple[str, str], str]:
    """Each worksheet measure's number format as the dashboard shows it.

    A sheet's own text-format on the field wins over the column's
    default-format, which only the CSV export follows.

    Returns:
        The format by (sheet, measure caption).
    """
    root = SafeET.fromstring(twb_text.encode("utf-8"))
    out: dict[tuple[str, str], str] = {}
    for ws in root.iter("worksheet"):
        sheet = ws.get("name") or ""
        own = {}
        for f in ws.iter("format"):
            field = f.get("field") or ""
            if f.get("attr") == "text-format" and f.get("value"):
                m = re.search(r"\]\.\[[a-z]+:([^:\]]+):", field)
                if m:
                    own[m.group(1)] = f.get("value")
        for col in ws.iter("column"):
            if col.get("role") != "measure" or col.get("param-domain-type"):
                continue
            name = (col.get("name") or "").strip("[]")
            fmt = own.get(name) or col.get("default-format")
            if fmt:
                out[(sheet, col.get("caption") or name)] = fmt
    return out


def review_copy(
    twb_text: str, dashboards: list[str], sheets: set[str] | None = None
) -> str:
    """The workbook with each named dashboard's sheets (only `sheets`, when given)
    exposed and clicks reproducible."""
    wb = read_workbook(twb_text)
    missing = [d for d in dashboards if d not in wb.dashboards]
    if missing:
        raise ReviewCopyError(f"no dashboard named {', '.join(missing)}")
    exposed = [
        s for d in dashboards for s in wb.dashboards[d] if sheets is None or s in sheets
    ]
    before = _hidden(twb_text)

    out = _expose(twb_text, exposed)
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

    # Exports then carry the raw value; cells round it the way the dashboard does.
    out, _ = _strip_measure_formats(out)
    if _strip_measure_formats(out)[1]:
        raise ReviewCopyError("a measure column still carries a number format")

    after = _hidden(out)
    still = [s for s in exposed if after.get(s)]
    if still:
        raise ReviewCopyError(f"still hidden: {', '.join(still)}")
    changed = [s for s in before if s not in exposed and before[s] != after.get(s)]
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


REPO = Path(__file__).resolve().parents[2]
XML_SCRIPTS = REPO / "docs" / "tableau-xml" / "scripts"


def _run(args: list[str]) -> None:
    # trunk-ignore(bandit/B603,bandit/B607): fixed repo scripts run through uv, no shell
    r = subprocess.run(  # noqa: S603 - fixed repo scripts, no shell
        ["uv", "run", "python", *args], capture_output=True, text=True, check=False
    )
    if r.returncode:
        raise ReviewCopyError(
            f"{Path(args[0]).name} failed:\n{r.stdout[-2000:]}{r.stderr[-2000:]}"
        )


def build_review_twbx(
    live_twbx: Path,
    out_dir: Path,
    dashboards: list[str],
    listed: set[str] | None = None,
) -> tuple[Path, list[str]]:
    """Edit the live workbook into a review copy and pass the tableau-workbook-xml gates."""
    base = twb_text(live_twbx)
    (out_dir / "base.twb").write_text(base, encoding="utf-8", newline="")
    wb0 = read_workbook(base)
    sheets = None
    if listed is not None:
        sheets = set(listed) | {
            a.source_sheet
            for a in wb0.actions
            if a.kind == "filter" and a.dashboard in dashboards
        }
    review = review_copy(base, dashboards, sheets)
    (out_dir / "review.twb").write_text(review, encoding="utf-8", newline="")
    _run(
        [
            str(XML_SCRIPTS / "check_twb.py"),
            str(out_dir / "review.twb"),
            "--ref",
            str(out_dir / "base.twb"),
        ]
    )
    out = out_dir / "review.twbx"
    _run(
        [
            str(XML_SCRIPTS / "repack.py"),
            str(out_dir / "review.twb"),
            str(live_twbx),
            str(out),
        ]
    )
    wb = read_workbook(review)
    keep = set(dashboards) | {
        s for d in dashboards for s in wb.dashboards[d] if sheets is None or s in sheets
    }
    return out, views_to_hide(review, keep)


def unpack_extracts(twbx: Path, out_dir: Path) -> dict[str, dict]:
    """Each datasource's .hyper from a downloaded .twbx, with its refresh time (UTC)."""
    out = {}
    root = SafeET.fromstring(twb_text(twbx))
    with zipfile.ZipFile(twbx) as z:
        for ds in root.iter("datasource"):
            conn = ds.find("extract/connection")
            if conn is None or conn.get("class") != "hyper" or not ds.get("caption"):
                continue
            name = Path(conn.get("dbname") or "").name
            member = next(n for n in z.namelist() if Path(n).name == name)
            (out_dir / name).write_bytes(z.read(member))
            raw = conn.get("update-time") or ""
            at = (
                dt.datetime.strptime(raw, "%m/%d/%Y %I:%M:%S %p")
                .replace(tzinfo=dt.UTC)
                .isoformat()
                if raw
                else None
            )
            out[ds.get("caption")] = {"file": name, "refreshed": at}
    return out


def twb_text(twbx: Path) -> str:
    """The .twb inside a .twbx."""
    with zipfile.ZipFile(twbx) as z:
        return z.read(next(n for n in z.namelist() if n.endswith(".twb"))).decode(
            "utf-8"
        )


def formulas(twb_text: str) -> dict[str, str]:
    """Each calculated column's caption and formula, for formula-gap cells."""
    root = SafeET.fromstring(twb_text)
    out: dict[str, str] = {}
    for c in root.iter("column"):
        calc = c.find("calculation")
        if calc is None or not calc.get("formula"):
            continue
        name = (c.get("name") or "").strip("[]")
        out.setdefault(caption_of(c, name), calc.get("formula") or "")
    return out
