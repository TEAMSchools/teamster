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
from dataclasses import dataclass, field
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


def derive_trees(fields, scores, distinct, accept=frozenset()) -> Trees:
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
