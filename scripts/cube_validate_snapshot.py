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

import argparse
import csv
import datetime as dt
import io
import itertools
import json
import os
import re
import shutil
import subprocess
import time
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

import defusedxml.ElementTree as SafeET
import yaml

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
            # trunk-ignore(bandit/B608): SQL over a local extract; names come from the workbook, not user input
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
    # trunk-ignore(bandit/B608): SQL over a local extract; names come from the workbook, not user input
    n = hyper.query(f"select count(*) from {t}")[0][0]
    distinct = {
        # trunk-ignore(bandit/B608): SQL over a local extract; names come from the workbook, not user input
        f: int(hyper.query(f"select count(distinct {_key(f)}) from {t}")[0][0])
        for f in fields
    }
    base = {
        f: hyper.query(
            # trunk-ignore(bandit/B608): SQL over a local extract; names come from the workbook, not user input
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
            # trunk-ignore(bandit/B608): SQL over a local extract; names come from the workbook, not user input
            "select sum(m) from (select max(c) m from (select "
            f"{_key(child)} ch, {_key(parent)} pa, count(*) c from {t} "
            "group by 1, 2) x group by ch) y"
        )[0][0]
        scores[(child, parent)] = (hit / n - base[parent]) / (1 - base[parent])
    return scores, distinct


NEST = 0.90
NEST_ASK = 0.85


@dataclass
class Trees:
    trees: dict[str, list[str]]
    cross_cuts: list[str]
    borderline: list[tuple[str, str, float]] = field(default_factory=list)


def _below(f: str, children: dict[str, set[str]]) -> set[str]:
    out, stack = set(), list(children[f])
    while stack:
        x = stack.pop()
        if x not in out:
            out.add(x)
            stack.extend(children[x])
    return out


def derive_trees(
    fields, scores, distinct, accept: set | frozenset = frozenset()
) -> Trees:
    edges = {(c, p) for (c, p), s in scores.items() if s >= NEST} | set(accept)
    borderline = sorted(
        (
            (c, p, round(s, 3))
            for (c, p), s in scores.items()
            if NEST_ASK <= s < NEST and (c, p) not in accept
        ),
        key=lambda x: -x[2],
    )
    children = {f: {c for c, p in edges if p == f} for f in fields}
    parents = {f: {p for c, p in edges if c == f} for f in fields}
    linked = {f for e in edges for f in e}

    def rank(chain):
        return (len(chain), [-distinct[x] for x in chain])

    memo: dict[str, list[str]] = {}

    def chain_from(f):
        if f not in memo:
            tails = [chain_from(c) for c in children[f]]
            memo[f] = [f, *max(tails, key=rank, default=[])]
        return memo[f]

    trees, seen = {}, set()
    for start in sorted(linked, key=lambda f: (distinct[f], f)):
        if start in seen:
            continue
        group, stack = set(), [start]
        while stack:
            x = stack.pop()
            if x not in group:
                group.add(x)
                stack.extend(children[x] | parents[x])
        seen |= group
        roots = [f for f in group if not parents[f]]
        order = max((chain_from(r) for r in roots), key=rank)
        for f in sorted(group - set(order), key=lambda f: (distinct[f], f)):
            below = _below(f, children)
            pos = next((i for i, s in enumerate(order) if s in below), len(order))
            order.insert(pos, f)
        trees[order[0]] = order
    cross = sorted(f for f in fields if f not in linked)
    return Trees(trees, cross, borderline)


ALL = "(All)"
BLANK = "(Blank)"
SMALL_CELL = 10
YEAR_FIELD = "academic_year"
# Person-level filters and parameter values: never exported, never in a draft.
PERSON_FIELD = re.compile(
    r"(lastfirst|student_name|first_name|last_name|teacher_name)$"
)
PERSON_VALUES = {"Student", "Students"}


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _value_slug(v: str) -> str:
    return {ALL: "all", BLANK: "blank"}.get(v, v)


@dataclass(frozen=True)
class State:
    dashboard: str
    filters: tuple[tuple[str, str], ...] = ()
    params: tuple[tuple[str, str], ...] = ()
    click: tuple[str, str] | None = None

    @property
    def id(self) -> str:
        parts = [f"{k}-{_value_slug(v)}" for k, v in sorted(self.filters + self.params)]
        if self.click:
            parts.append(f"click-{self.click[0]}-{self.click[1]}")
        return "--".join(
            [slug(self.dashboard), *(slug(p) for p in parts or ["default"])]
        )

    def as_dict(self) -> dict:
        d: dict = {"id": self.id, "dashboard": self.dashboard}
        if self.filters:
            d["filters"] = dict(self.filters)
        if self.params:
            d["params"] = dict(self.params)
        if self.click:
            d["click"] = {"action": self.click[0], "mark": self.click[1]}
        return d

    @classmethod
    def from_dict(cls, d: dict) -> State:
        click = d.get("click")
        return cls(
            d["dashboard"],
            tuple((d.get("filters") or {}).items()),
            tuple((d.get("params") or {}).items()),
            (click["action"], click["mark"]) if click else None,
        )


@dataclass(frozen=True)
class PlanItem:
    state: State
    tier: str
    why: str


def _ends(values) -> list[str]:
    """The largest value and the smallest with at least SMALL_CELL students."""
    named = [(v, n) for v, n in values if v is not None]
    if not named:
        return []
    big = max(named, key=lambda x: x[1])[0]
    small = [v for v, n in sorted(named, key=lambda x: x[1]) if n >= SMALL_CELL][:1]
    return list(dict.fromkeys([big, *small]))


def plan_states(wb, profiles, trees, years) -> list[PlanItem]:
    items: list[PlanItem] = []
    for dash in wb.dashboards:

        def add(tier, why, dash=dash, **kw):
            items.append(PlanItem(State(dash, **kw), tier, why))

        add("must", "default view")
        for p in (p for p in wb.params if p.dashboard == dash):
            if not p.values:
                add(
                    "skipped",
                    f"{p.caption}: free-entry parameter, default only",
                    params=((p.caption, p.default),),
                )
            for v in p.values:
                if v in PERSON_VALUES:
                    add(
                        "skipped",
                        f"{p.caption} = {v}: person-level",
                        params=((p.caption, v),),
                    )
                else:
                    add("must", "view-changing parameter", params=((p.caption, v),))

        for c in (c for c in wb.filters if c.dashboard == dash):
            prof = profiles.get(c.datasource, {}).get(c.field, [])
            t = trees.get(c.datasource, Trees({}, []))
            in_tree = {f for levels in t.trees.values() for f in levels}
            roots = {levels[0] for levels in t.trees.values()}
            one = lambda v, c=c: ((c.caption, v),)  # noqa: E731
            if PERSON_FIELD.search(c.field) and c.field not in in_tree:
                add("skipped", f"{c.caption}: person-level filter", filters=one(ALL))
                continue
            if c.calculated:
                for v in c.values or [v for v, _ in prof if v is not None]:
                    add("must", "calculated-field filter", filters=one(v))
                continue
            if not c.default_all:
                add("must", "saved default is not All", filters=one(ALL))
            if c.field == YEAR_FIELD:
                for y in years:
                    add("must", "academic year", filters=one(y))
                continue
            if any(v is None for v, _ in prof):
                add("must", "blank value", filters=one(BLANK))
            named = [v for v, _ in prof if v is not None]
            if c.field in roots:
                for v in named:
                    add("must", f"top of the {c.field} tree", filters=one(v))
            elif c.field in t.cross_cuts:
                for v in named:
                    add("must", "cross-cut", filters=one(v))
            elif c.field not in in_tree:
                for v in _ends(prof):
                    add(
                        "optional", "plain filter, largest and smallest", filters=one(v)
                    )

        for a in (a for a in wb.actions if a.dashboard == dash):
            if a.kind != "filter":
                add(
                    "skipped",
                    f"{a.caption}: {a.kind} action",
                    click=(a.caption, "largest"),
                )
                continue
            add("must", "click, largest mark", click=(a.caption, "largest"))
            add("must", "click, a small mark", click=(a.caption, "small"))

    seen: dict[str, PlanItem] = {}
    for i in items:
        seen.setdefault(i.state.id, i)
    return list(seen.values())


def plan_yaml(items: list[PlanItem]) -> str:
    out = {
        tier: [dict(i.state.as_dict(), why=i.why) for i in items if i.tier == tier]
        for tier in ("must", "optional", "skipped")
    }
    return yaml.safe_dump(out, sort_keys=False, allow_unicode=True)


SNAPSHOT_ROOT = Path.home() / ".cache" / "cube-validate"
KEEP_SNAPSHOTS = 2


def new_snapshot_dir(
    workbook: str, at: dt.datetime, root: Path = SNAPSHOT_ROOT
) -> Path:
    """A fresh snapshot folder; older ones beyond the newest KEEP_SNAPSHOTS - 1 go.

    Snapshots hold student-level rows, so they are kept outside the repo and few.
    """
    base = Path(root) / slug(workbook)
    base.mkdir(parents=True, exist_ok=True)
    old = sorted(p for p in base.iterdir() if p.is_dir())
    for p in old[: max(0, len(old) - (KEEP_SNAPSHOTS - 1))]:
        shutil.rmtree(p)
    out = base / at.strftime("%Y-%m-%dT%H%M")
    (out / "csv").mkdir(parents=True)
    (out / "extract").mkdir()
    return out


def latest_snapshot(workbook: str, root: Path = SNAPSHOT_ROOT) -> Path:
    base = Path(root) / slug(workbook)
    dirs = sorted(p for p in base.iterdir() if p.is_dir()) if base.exists() else []
    if not dirs:
        raise FileNotFoundError(f"no snapshot for {workbook} under {base}")
    return dirs[-1]


@dataclass
class Manifest:
    workbook: str
    workbook_luid: str
    copy_luid: str | None
    opened_at: str
    live_updated_at: str
    extracts: dict[str, dict]
    fields: dict[str, dict]
    states: dict[str, dict]
    closed: bool = False


def write_manifest(path: Path, m: Manifest) -> None:
    Path(path).write_text(json.dumps(asdict(m), indent=2, sort_keys=True))


def read_manifest(path: Path) -> Manifest:
    return Manifest(**json.loads(Path(path).read_text()))


def csv_rows(data: bytes) -> int:
    text = data.decode("utf-8-sig")
    return max(len(list(csv.reader(io.StringIO(text)))) - 1, 0)


def filter_ignored(
    parent: dict[str, bytes], current: dict[str, bytes], covers_all: bool
) -> bool:
    """A filter whose state exports exactly what its parent did, though it should not."""
    if covers_all or not current:
        return False
    if all(csv_rows(v) == 0 for v in current.values()):
        return False
    return all(current.get(s) == parent.get(s) for s in current)


def parent_of(state: State) -> State:
    if state.click or (state.params and not state.filters):
        return State(state.dashboard, (), (), None)
    return State(state.dashboard, state.filters[:-1], state.params, None)


TEMP_CB = "ddc817c2-6bc7-4bca-8be9-e385f95b9ebc"
#: Projects a review copy may land in. Production is never added here.
NON_PRODUCTION_PROJECTS = {TEMP_CB: "TEMP-CB"}
REVIEW_PREFIX = "ZZ-REVIEW "
STALE_COPY = dt.timedelta(hours=24)
REPO = Path(__file__).resolve().parents[1]
XML_SCRIPTS = REPO / "docs" / "tableau-xml" / "scripts"


class SessionError(RuntimeError):
    """The review copy could not be published, exported or removed safely."""


class RefreshedError(SessionError):
    """The live workbook changed mid-session, so the snapshot no longer holds."""


def retry(fn, attempts: int = 3, sleep=time.sleep, wait: float = 5.0):
    """Call fn until it succeeds; Tableau sign-ins fail transiently with 401002."""
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception:  # noqa: BLE001 - re-raised after the last attempt
            if attempt == attempts:
                raise
            sleep(wait * attempt)
    raise ValueError("retry needs attempts >= 1")


def vf_value(value: str, all_values: list[str]) -> str:
    """A filter value as Tableau's vf takes it: commas separate values."""

    def esc(v: str) -> str:
        return v.replace(",", "\\,")

    if value == ALL:
        return ",".join(esc(v) for v in all_values)
    if value == BLANK:
        return "Null"
    return esc(value)


def _is_number(s: str) -> bool:
    try:
        float(s.replace(",", "").rstrip("%"))
    except ValueError:
        return False
    return True


def pick_click_row(export: bytes, mark: str, dims: list[str] | None) -> dict[str, str]:
    """The dimension values of the mark a person would click: largest or smallest."""
    rows = list(csv.DictReader(io.StringIO(export.decode("utf-8-sig"))))
    if not rows:
        raise SessionError("the source sheet exported no marks to click")
    cols = list(rows[0])
    dims = dims or [c for c in cols if not all(_is_number(r[c]) for r in rows if r[c])]
    measure = next(c for c in cols if c not in dims)
    marks = [r for r in rows if not any(r[d] in ("All", "*") for d in dims)]
    if not marks:
        raise SessionError("every mark on the source sheet is a total")
    value = lambda r: float(r[measure].replace(",", "").rstrip("%") or 0)  # noqa: E731
    row = max(marks, key=value) if mark == "largest" else min(marks, key=value)
    return {d: row[d] for d in dims}


def _workbooks_in(server, project: str) -> list:
    import tableauserverclient as tsc

    return [w for w in tsc.Pager(server.workbooks) if w.project_id == project]


class Session:
    def __init__(self, server, project_luid: str, now=lambda: dt.datetime.now(dt.UTC)):
        if project_luid not in NON_PRODUCTION_PROJECTS:
            raise SessionError(
                f"{project_luid} is not an agreed non-production project"
            )
        self.server, self.project, self.now = server, project_luid, now
        self._views: dict = {}

    def sweep(self) -> list[str]:
        """Delete review copies older than STALE_COPY: leftovers of failed sessions."""
        cutoff, gone = self.now() - STALE_COPY, []
        for w in _workbooks_in(self.server, self.project):
            if (
                w.name.startswith(REVIEW_PREFIX)
                and w.created_at
                and w.created_at < cutoff
            ):
                self.server.workbooks.delete(w.id)
                gone.append(w.name)
        return gone

    def publish(self, twbx: Path, name: str, hidden: list[str]) -> str:
        import tableauserverclient as tsc

        if not name.startswith(REVIEW_PREFIX):
            raise SessionError(
                f"review copies carry the {REVIEW_PREFIX.strip()} prefix"
            )
        item = tsc.WorkbookItem(project_id=self.project, name=name, show_tabs=True)
        item.hidden_views = hidden
        item = self.server.workbooks.publish(item, str(twbx), mode="CreateNew")
        if item.project_id != self.project:
            raise SessionError(f"published to {item.project_name}, not TEMP-CB")
        self.copy = item
        return item.id

    def export_view(self, sheet: str, filters: list[tuple[str, str]]) -> bytes:
        import tableauserverclient as tsc

        if not self._views:
            self.server.workbooks.populate_views(self.copy)
            self._views = {v.name: v for v in self.copy.views}
        view = self._views.get(sheet)
        if view is None:
            raise SessionError(f"the review copy has no view named {sheet}")

        def fetch():
            opts = tsc.CSVRequestOptions()
            for k, v in filters:
                opts = opts.vf(k, v)
            self.server.views.populate_csv(view, opts)
            return b"".join(view.csv)

        return retry(fetch)

    def check_refresh(self, live_luid: str, recorded: str) -> None:
        now = self.server.workbooks.get_by_id(live_luid).updated_at
        if now and now.isoformat() != recorded:
            raise RefreshedError(
                f"the live workbook changed at {now.isoformat()} (recorded {recorded}); "
                "close this session and open a new one"
            )

    def close(self, copy_luid: str) -> None:
        self.server.workbooks.delete(copy_luid)
        if any(w.id == copy_luid for w in _workbooks_in(self.server, self.project)):
            raise SessionError(
                f"review copy {copy_luid} is still on the server; delete it in "
                f"Tableau (project TEMP-CB). The next open sweeps it after 24 hours."
            )


def _run(args: list[str]) -> None:
    # trunk-ignore(bandit/B603,bandit/B607): fixed repo scripts run through uv, no shell
    r = subprocess.run(  # noqa: S603 - fixed repo scripts, no shell
        ["uv", "run", "python", *args], capture_output=True, text=True, check=False
    )
    if r.returncode:
        raise SessionError(
            f"{Path(args[0]).name} failed:\n{r.stdout[-2000:]}{r.stderr[-2000:]}"
        )


def build_review_twbx(
    live_twbx: Path, out_dir: Path, dashboards: list[str]
) -> tuple[Path, list[str]]:
    """Edit the live workbook into a review copy and pass the tableau-workbook-xml gates."""
    with zipfile.ZipFile(live_twbx) as z:
        twb_name = next(n for n in z.namelist() if n.endswith(".twb"))
        base = z.read(twb_name).decode("utf-8")
    (out_dir / "base.twb").write_text(base, encoding="utf-8", newline="")
    review = review_copy(base, dashboards)
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
    keep = set(dashboards) | {s for d in dashboards for s in wb.dashboards[d]}
    return out, views_to_hide(review, keep)


def unpack_extracts(twbx: Path, out_dir: Path) -> dict[str, dict]:
    """Each datasource's .hyper from a downloaded .twbx, with its refresh time (UTC)."""
    out = {}
    with zipfile.ZipFile(twbx) as z:
        twb = z.read(next(n for n in z.namelist() if n.endswith(".twb"))).decode(
            "utf-8"
        )
        root = SafeET.fromstring(twb)
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


def _csv_path(snapdir: Path, sheet: str, state_id: str) -> Path:
    p = Path(snapdir) / "csv" / slug(sheet) / f"{state_id}.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _read_state(snapdir: Path, entry: dict | None) -> dict[str, bytes]:
    if not entry:
        return {}
    return {
        s: (Path(snapdir) / v["file"]).read_bytes() for s, v in entry["sheets"].items()
    }


def export_state(
    session, manifest, snapdir, wb, state, all_values, covers_all, dims_for
) -> dict:
    filters = [(k, vf_value(v, all_values.get(k, []))) for k, v in state.filters]
    filters += list(state.params)
    sheets = list(wb.dashboards[state.dashboard])
    click_filters: dict[str, str] = {}
    entry = {
        "state": state.as_dict(),
        "sheets": {},
        "status": "ok",
        "click_filters": {},
    }
    try:
        if state.click:
            action = next(a for a in wb.actions if a.caption == state.click[0])
            source = session.export_view(action.source_sheet, filters)
            click_filters = pick_click_row(
                source, state.click[1], dims_for.get(action.source_sheet)
            )
            filters += [(k, vf_value(v, [])) for k, v in click_filters.items()]
            sheets = [
                s for s in wb.dashboards[action.target] if s not in action.exclude
            ]
        data = {s: session.export_view(s, filters) for s in sheets}
    except Exception as e:  # noqa: BLE001 - recorded per state, the run goes on
        entry["status"], entry["error"] = (
            "export_failed",
            f"{type(e).__name__}: {str(e)[:300]}",
        )
        return entry
    for s, b in data.items():
        p = _csv_path(snapdir, s, state.id)
        p.write_bytes(b)
        entry["sheets"][s] = {"file": str(p.relative_to(snapdir)), "rows": csv_rows(b)}
    entry["click_filters"] = click_filters
    if state.filters and not state.click:
        parent = manifest.states.get(parent_of(state).id)
        last = state.filters[-1]
        covers = last[1] in covers_all.get(last[0], set())
        if filter_ignored(_read_state(snapdir, parent), data, covers):
            entry["status"] = "filter_ignored"
    return entry


def _load_checks(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text()) or {}


def _profiles_for(wb, extracts, snapdir, where_year=True):
    """Profiles and nesting per datasource, over the dashboard filter fields."""
    profiles, scores = {}, {}
    for ds, meta in extracts.items():
        fields = sorted(
            {c.field for c in wb.filters if c.datasource == ds and not c.calculated}
        )
        if not fields:
            continue
        with Hyper(Path(snapdir) / meta["file"]) as h:
            cols = set(h.columns())
            fields = [f for f in fields if f in cols]
            where = None
            if where_year and YEAR_FIELD in cols:
                # trunk-ignore(bandit/B608): SQL over a local extract; names come from the workbook, not user input
                where = f'"{YEAR_FIELD}" = (select max("{YEAR_FIELD}") from {EXTRACT})'
            profiles[ds] = profile(h, fields)
            scores[ds] = nesting(h, [f for f in fields if f != YEAR_FIELD], where)
    return profiles, scores


def _plan(a) -> int:
    checks = _load_checks(a.checks)
    out_dir = Path(a.out).parent if a.out else SNAPSHOT_ROOT / slug(checks["workbook"])
    out_dir.mkdir(parents=True, exist_ok=True)
    twbx = Path(a.twbx) if a.twbx else _download(checks["workbook_luid"], out_dir)[0]
    with zipfile.ZipFile(twbx) as z:
        twb = z.read(next(n for n in z.namelist() if n.endswith(".twb"))).decode(
            "utf-8"
        )
    wb = read_workbook(twb)
    keep = set(checks.get("dashboards") or wb.dashboards)
    wb = Workbook(
        {d: s for d, s in wb.dashboards.items() if d in keep},
        [c for c in wb.filters if c.dashboard in keep],
        [p for p in wb.params if p.dashboard in keep],
        [x for x in wb.actions if x.dashboard in keep],
    )
    extracts = unpack_extracts(twbx, out_dir)
    profiles, scores = _profiles_for(wb, extracts, out_dir)
    accept = {tuple(p) for p in checks.get("accept_nesting") or []}
    trees = {
        ds: derive_trees(
            [f for f in profiles[ds] if f != YEAR_FIELD], *scores[ds], accept=accept
        )
        for ds in profiles
    }
    years = sorted(
        {v for ds in profiles for v, _ in profiles[ds].get(YEAR_FIELD, []) if v},
        reverse=True,
    )[:2]
    items = plan_states(wb, profiles, trees, tuple(years))
    doc = {
        "trees": {ds: t.trees for ds, t in trees.items()},
        "cross_cuts": {ds: t.cross_cuts for ds, t in trees.items()},
        "borderline": {ds: [list(b) for b in t.borderline] for ds, t in trees.items()},
    }
    text = yaml.safe_dump(doc, sort_keys=False, allow_unicode=True) + plan_yaml(items)
    Path(a.out or out_dir / "plan.yml").write_text(text)
    print(
        f"plan: {sum(i.tier == 'must' for i in items)} must, "
        f"{sum(i.tier == 'optional' for i in items)} optional, "
        f"{sum(i.tier == 'skipped' for i in items)} skipped -> {a.out or out_dir / 'plan.yml'}"
    )
    return 0


def _server():
    import tableauserverclient as tsc

    auth = tsc.PersonalAccessTokenAuth(
        token_name=os.environ["TABLEAU_TOKEN_NAME"],
        personal_access_token=os.environ["TABLEAU_PERSONAL_ACCESS_TOKEN"],
        site_id=os.environ["TABLEAU_SITE_ID"],
    )
    return tsc.Server(
        os.environ["TABLEAU_SERVER_ADDRESS"], use_server_version=True
    ), auth


def _download(luid: str, out_dir: Path) -> tuple[Path, str]:
    server, auth = _server()

    def fetch():
        with server.auth.sign_in(auth):
            at = server.workbooks.get_by_id(luid).updated_at
            path = server.workbooks.download(
                luid, filepath=str(out_dir / "live"), include_extract=True
            )
        return Path(path), at.isoformat() if at else ""

    return retry(fetch)


def _states_for(checks: dict, path: str | None) -> list[State]:
    raw = yaml.safe_load(Path(path).read_text()) if path else checks.get("states")
    if isinstance(raw, dict):  # a plan file: take its must and optional lists
        raw = (raw.get("must") or []) + (raw.get("optional") or [])
    return [State.from_dict(d) for d in raw or []]


def _value_maps(manifest: Manifest, snapdir: Path):
    """Every value of each filter caption, and the values that cover every row."""
    all_values, covers = {}, {}
    by_ds: dict[str, list[tuple[str, str]]] = {}
    for caption, f in manifest.fields.items():
        by_ds.setdefault(f["datasource"], []).append((caption, f["field"]))
    for ds, pairs in by_ds.items():
        with Hyper(snapdir / manifest.extracts[ds]["file"]) as h:
            prof = profile(h, [f for _, f in pairs])
        for caption, f in pairs:
            vals = prof[f]
            total = sum(n for _, n in vals)
            all_values[caption] = [v for v, _ in vals if v is not None]
            covers[caption] = {ALL} | {
                v for v, n in vals if v is not None and n == total
            }
    return all_values, covers


def _open(a) -> int:
    checks = _load_checks(a.checks)
    server, auth = _server()
    at = dt.datetime.now(dt.UTC)
    snapdir = new_snapshot_dir(checks["workbook"], at)
    with server.auth.sign_in(auth):
        session = Session(server, checks["review_project_luid"])
        print("swept:", session.sweep() or "nothing")
        live_updated = server.workbooks.get_by_id(checks["workbook_luid"]).updated_at
        live_at = live_updated.isoformat() if live_updated else ""
        live = Path(
            server.workbooks.download(
                checks["workbook_luid"],
                filepath=str(snapdir / "live"),
                include_extract=True,
            )
        )
        extracts = unpack_extracts(live, snapdir / "extract")
        extracts = {
            ds: {**m, "file": f"extract/{m['file']}"} for ds, m in extracts.items()
        }
        twbx, hidden = build_review_twbx(live, snapdir, checks["dashboards"])
        wb = read_workbook(
            (snapdir / "review.twb").read_text(encoding="utf-8", newline="")
        )
        name = f"{REVIEW_PREFIX}{at:%Y-%m-%d %H%M} {checks['workbook']}"
        copy = session.publish(twbx, name, hidden)
        print(f"published {name} ({copy}) to TEMP-CB")
        fields = {
            c.caption: {"field": c.field, "datasource": c.datasource}
            for c in wb.filters
            if c.dashboard in checks["dashboards"]
        }
        m = Manifest(
            checks["workbook"],
            checks["workbook_luid"],
            copy,
            at.isoformat(),
            live_at,
            extracts,
            fields,
            {},
        )
        write_manifest(snapdir / "manifest.json", m)
        _export_all(session, m, snapdir, wb, checks, _states_for(checks, a.states))
    return 0


def _export_all(session, m, snapdir, wb, checks, states) -> None:
    all_values, covers = _value_maps(m, snapdir)
    dims_for = {
        s: list((v.get("dims") or {})) for s, v in (checks.get("sheets") or {}).items()
    }
    # Parents first, so the filter-took-effect check has something to compare with.
    for state in sorted(states, key=lambda s: (len(s.filters), s.id)):
        session.check_refresh(m.workbook_luid, m.live_updated_at)
        m.states[state.id] = export_state(
            session, m, snapdir, wb, state, all_values, covers, dims_for
        )
        write_manifest(snapdir / "manifest.json", m)
        print(f"  {state.id}: {m.states[state.id]['status']}")


def _export(a) -> int:
    checks = _load_checks(a.checks)
    snapdir = latest_snapshot(checks["workbook"])
    m = read_manifest(snapdir / "manifest.json")
    if m.closed:
        raise SessionError("this snapshot's session is closed; open a new one")
    if not m.copy_luid:
        raise SessionError("this snapshot has no review copy; open a new session")
    server, auth = _server()
    with server.auth.sign_in(auth):
        session = Session(server, checks["review_project_luid"])
        session.copy = server.workbooks.get_by_id(m.copy_luid)
        wb = read_workbook(
            (snapdir / "review.twb").read_text(encoding="utf-8", newline="")
        )
        _export_all(session, m, snapdir, wb, checks, _states_for(checks, a.states))
    return 0


def _close(a) -> int:
    checks = _load_checks(a.checks)
    snapdir = latest_snapshot(checks["workbook"])
    m = read_manifest(snapdir / "manifest.json")
    if not m.copy_luid:
        raise SessionError("this snapshot has no review copy; open a new session")
    server, auth = _server()
    with server.auth.sign_in(auth):
        Session(server, checks["review_project_luid"]).close(m.copy_luid)
    m.closed = True
    write_manifest(snapdir / "manifest.json", m)
    for p in (snapdir / "live.twbx", snapdir / "review.twbx"):
        p.unlink(missing_ok=True)
    print(f"closed: review copy {m.copy_luid} deleted and confirmed gone")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="cube_validate_snapshot")
    sub = p.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("plan")
    pl.add_argument("checks")
    pl.add_argument("--twbx")
    pl.add_argument("--out")
    for name in ("open", "export"):
        s = sub.add_parser(name)
        s.add_argument("checks")
        s.add_argument("--states", help="a YAML list of states, or a plan file")
    cl = sub.add_parser("close")
    cl.add_argument("checks")
    a = p.parse_args(argv)
    return {"plan": _plan, "open": _open, "export": _export, "close": _close}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
