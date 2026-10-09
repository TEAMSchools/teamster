# Cube validation against what Tableau shows: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Two scripts and a skill that check Cube against the numbers a Tableau
dashboard shows, explain each gap from the dashboard's own extract, and draft a
GitHub issue per explained gap.

**Architecture:** `scripts/cube_validate_snapshot.py` owns everything on the
Tableau side: it reads the workbook, proposes which states to visit, publishes a
review copy, exports each sheet per state, and deletes the copy.
`scripts/cube_validate.py` owns the Cube side: it reads a snapshot, compares
each export with Cube, proposes the next descent level, explains gaps with SQL
over the extract, and writes verdicts, a digest and issue drafts. The
`cube-dashboard` skill runs the loop between them.

**Tech Stack:** Python 3.13, `tableauserverclient`, `tableauhyperapi` (added per
run with `uv run --with`), `httpx` + `pyjwt` (Cube REST), `sqlglot`,
`defusedxml`, `pyyaml`, pytest.

**Spec:**
`docs/superpowers/specs/2026-10-09-cube-validate-tableau-truth-design.md`

## Global Constraints

- Branch: `cristinabaldor/feat/claude-cube-dashboard-tableau-truth`, main
  checkout. Never stage `.devcontainer/tpl/` (the user's own change).
- v1 source to copy from: ref
  `origin/cristinabaldor/feat/claude-cube-validate-skill` at `51f4f21e4a`. Fetch
  it once: `git fetch origin cristinabaldor/feat/claude-cube-validate-skill`.
  Every "copy from v1" step names the function and the v1 line range.
- Run every test file with
  `uv run --with tableauhyperapi pytest <file> -q 2>&1 | tail -n 30`. Never bare
  `pytest` and never bare `uv run pytest` without a path.
- Both scripts are standalone files in `scripts/` with no PEP 723 header (v1 had
  none; their dependencies come from the project environment plus
  `--with tableauhyperapi`). Tests load them with `importlib`, registering
  `sys.modules[name]` before `exec_module` (`scripts/CLAUDE.md`).
- Review project: only `ddc817c2-6bc7-4bca-8be9-e385f95b9ebc` (TEMP-CB). A
  review copy's name starts with `ZZ-REVIEW ` followed by the date and time.
- Snapshot root: `~/.cache/cube-validate/<workbook-slug>/<YYYY-MM-DDTHHMM>/`.
  Keep the latest 2 per workbook.
- Constants: `SMALL_CELL = 10`, `NEST = 0.90`, `NEST_ASK = 0.85`,
  `STALE_COPY = 24 hours`, `KEEP_SNAPSHOTS = 2`, export retries 3.
- Test fixtures are synthetic. No real student, school or staff value is
  committed, printed by a test, or written to a commit message.
- Verdict order, strongest first: `fail`, `incomplete`, `fix_cube`,
  `fix_source`, `undecided`, `missing_member`, `pass`.
- Credentialed runs (Tableau PAT, `CUBE_API_SECRET`) happen only inside a
  throwaway `tests/test_zz_*.py` run with
  `uv run --with tableauhyperapi pytest <file> -s`, deleted afterwards. Never
  call `op`.
- Before pushing markdown or YAML, run
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`.

### Deliberate departures from the spec's examples

- `trees:` and `cross_cuts:` are keyed by datasource caption, because the DDI
  Suite's dashboards read 2 extracts whose fields differ. The spec's example
  showed one workbook-level tree.
- The cells file is `cells.jsonl`, not Parquet: no new dependency, and Claude
  can read it with `jq`.
- **Timing is checked against the live table** (spec revision 2026-10-09). When
  the extract SQL reproduces Tableau but Cube differs, `explain` runs the same
  SQL on the live `rpt_` table. If Cube equals it, the gap is only the extract's
  age: `pass`, noted as timing. If Cube's data is older than the live table, the
  cell is `incomplete`. The settle window and the `settle` command are dropped.
- **A cell the extract SQL cannot reproduce is `incomplete`**, not "unexplained"
  (`fail`), following the spec's rule that a gap the tool cannot attribute
  blames nobody.
- **DDI gap 4 (the extract leaves out rows) replays as `fail`**, not
  `incomplete`: the spec's acceptance table contradicted its own verdict table
  (an unexplained gap is `fail`). It lands under "Investigate".

## Review Focus

1. **A CSV export repeats a column name** (the DDI Network Overview exports
   `Schoolid` twice). Expected: both columns are kept, the second as
   `Schoolid (2)`. Pinned in Task 11.
2. **A parameter offers a person-level value** (DDI "Group By" offers
   `Student`). Expected: that value is planned as skipped, never exported.
   Pinned in Task 5.
3. **A filter value contains a comma.** Tableau's `vf` splits on commas.
   Expected: commas inside a value are escaped as `\,`. Pinned in Task 7.
4. **Tableau formats dimension values** ("9/15/2026", "1,234"). Expected: they
   join Cube's ISO dates and plain integers. Pinned in Task 9.
5. **A state exports a header-only or empty CSV** (2 spike exports were empty
   before the click fix). Expected: the sheet has 0 rows, Cube rows for that
   state become row-set mismatches, and nothing crashes. Pinned in Tasks 6
   and 13.

---

## Part A: the Tableau side (`scripts/cube_validate_snapshot.py`)

### Task 1: read the workbook (dashboards, filter cards, parameters, actions)

**Files:**

- Create: `scripts/cube_validate_snapshot.py`
- Create: `tests/scripts/fixtures/cube_validate/review.twb`
- Create: `tests/scripts/test_cube_validate_snapshot.py`

**Interfaces:**

- Produces:
  - `FilterCard(dashboard: str, field: str, caption: str, datasource: str, calculated: bool, default_all: bool, values: tuple[str, ...])`
    (frozen dataclass; `values` holds formula literals for calculated fields,
    else `()`)
  - `Param(dashboard: str, caption: str, values: tuple[str, ...], default: str)`
    (`values` is `()` for range or free-entry parameters)
  - `Action(dashboard: str, caption: str, source_sheet: str, kind: str, target: str, exclude: tuple[str, ...])`
    (`kind` is `filter`, `highlight` or `link`)
  - `Workbook(dashboards: dict[str, list[str]], filters: list[FilterCard], params: list[Param], actions: list[Action])`
  - `read_workbook(twb_text: str) -> Workbook`
  - `default_caption(field: str) -> str`

- [ ] **Step 1: Write the fixture workbook**

`tests/scripts/fixtures/cube_validate/review.twb`:

```xml
<?xml version='1.0' encoding='utf-8' ?>
<workbook source-build='2024.2.0' version='18.1' xmlns:user='http://www.tableausoftware.com/xml/user'>
  <datasources>
    <datasource hasconnection='false' inline='true' name='Parameters' version='18.1'>
      <column caption='Group By' datatype='string' name='[Group By (copy)]' param-domain-type='list' role='measure' type='nominal' value='&quot;School&quot;'>
        <calculation class='tableau' formula='&quot;School&quot;' />
        <members>
          <member value='&quot;School&quot;' />
          <member value='&quot;Teacher&quot;' />
          <member value='&quot;Student&quot;' />
        </members>
      </column>
      <column caption='Goal %' datatype='real' name='[Goal]' param-domain-type='range' role='measure' type='quantitative' value='0.8'>
        <calculation class='tableau' formula='0.8' />
      </column>
    </datasource>
    <datasource caption='rpt_demo (kipptaf_tableau)' inline='true' name='federated.demo1' version='18.1'>
      <connection class='federated'>
        <named-connections />
      </connection>
      <extract count='-1' enabled='true' units='records'>
        <connection class='hyper' dbname='Data/Extracts/federated_demo1.hyper' update-time='10/08/2026 05:39:00 AM' />
      </extract>
      <column datatype='string' name='[region]' role='dimension' type='nominal' />
      <column caption='School Name' datatype='string' name='[school]' role='dimension' type='nominal' />
      <column datatype='integer' name='[grade_level]' role='dimension' type='ordinal' />
      <column datatype='integer' name='[academic_year]' role='dimension' type='ordinal' />
      <column datatype='string' name='[iep_status]' role='dimension' type='nominal' />
      <column datatype='string' name='[student_name]' role='dimension' type='nominal' />
      <column caption='Is Tested' datatype='string' name='[Calculation_1]' role='dimension' type='nominal'>
        <calculation class='tableau' formula='IF [percent_correct] &gt;= 0 THEN &quot;Yes&quot; ELSE &quot;No&quot; END' />
      </column>
    </datasource>
  </datasources>
  <actions>
    <action caption='Table to Detail' name='[Action1]'>
      <activation auto-clear='true' type='on-select' />
      <source dashboard='Overview' type='sheet' worksheet='Overview - Table' />
      <command command='tsc:tsl-filter'>
        <param name='exclude' value='Overview - Table' />
        <param name='on-empty' value='none' />
        <param name='special-fields' value='all' />
        <param name='target' value='Overview' />
      </command>
    </action>
    <action caption='Open Report' name='[Action2]'>
      <activation type='on-select' />
      <source dashboard='Overview' type='sheet' worksheet='Overview - Table' />
      <link caption='Open Report' expression='https://example.org' />
    </action>
  </actions>
  <worksheets>
    <worksheet name='Overview - Table'>
      <table>
        <view>
          <datasources />
          <filter class='categorical' column='[federated.demo1].[none:iep_status:nk]'>
            <groupfilter function='member' level='[none:iep_status:nk]' member='&quot;No IEP&quot;' user:ui-enumeration='inclusive' />
          </filter>
          <filter class='categorical' column='[federated.demo1].[none:region:nk]'>
            <groupfilter function='level-members' level='[none:region:nk]' user:ui-enumeration='all' />
          </filter>
        </view>
      </table>
    </worksheet>
    <worksheet name='Overview - Detail'>
      <table>
        <view>
          <datasources />
          <filter class='categorical' column='[federated.demo1].[Action (Table to Detail)]'>
            <groupfilter function='level-members' level='[none:school:nk]' />
          </filter>
          <slices>
            <column>[federated.demo1].[Action (Table to Detail)]</column>
          </slices>
        </view>
      </table>
    </worksheet>
    <worksheet name='Scratch Sheet'>
      <table>
        <view>
          <datasources />
        </view>
      </table>
    </worksheet>
  </worksheets>
  <dashboards>
    <dashboard name='Overview'>
      <zones>
        <zone h='100000' id='1' type-v2='layout-basic' w='100000' x='0' y='0'>
          <zone h='40000' id='2' name='Overview - Table' w='50000' x='0' y='0' />
          <zone h='40000' id='3' name='Overview - Detail' w='50000' x='50000' y='0' />
          <zone h='5000' id='4' mode='checkdropdown' name='Overview - Table' param='[federated.demo1].[none:region:nk]' type-v2='filter' w='10000' x='0' y='90000' />
          <zone h='5000' id='5' mode='checkdropdown' name='Overview - Table' param='[federated.demo1].[none:school:nk]' type-v2='filter' w='10000' x='10000' y='90000' />
          <zone h='5000' id='6' mode='checkdropdown' name='Overview - Table' param='[federated.demo1].[none:grade_level:ok]' type-v2='filter' w='10000' x='20000' y='90000' />
          <zone h='5000' id='7' mode='checkdropdown' name='Overview - Table' param='[federated.demo1].[none:iep_status:nk]' type-v2='filter' w='10000' x='30000' y='90000' />
          <zone h='5000' id='8' mode='checkdropdown' name='Overview - Table' param='[federated.demo1].[none:student_name:nk]' type-v2='filter' w='10000' x='40000' y='90000' />
          <zone h='5000' id='9' mode='checkdropdown' name='Overview - Table' param='[federated.demo1].[none:Calculation_1:nk]' type-v2='filter' w='10000' x='50000' y='90000' />
          <zone h='5000' id='10' mode='checkdropdown' name='Overview - Table' param='[federated.demo1].[none:academic_year:ok]' type-v2='filter' w='10000' x='60000' y='90000' />
          <zone h='5000' id='11' mode='list' param='[Parameters].[Group By (copy)]' type-v2='paramctrl' w='10000' x='70000' y='90000' />
          <zone h='5000' id='12' mode='slider' param='[Parameters].[Goal]' type-v2='paramctrl' w='10000' x='80000' y='90000' />
        </zone>
      </zones>
    </dashboard>
  </dashboards>
  <windows>
    <window class='dashboard' name='Overview' />
    <window class='worksheet' hidden='true' name='Overview - Table' />
    <window class='worksheet' hidden='true' name='Overview - Detail' />
    <window class='worksheet' name='Scratch Sheet' />
  </windows>
</workbook>
```

- [ ] **Step 2: Write the failing tests**

`tests/scripts/test_cube_validate_snapshot.py`:

```python
"""Tests for scripts/cube_validate_snapshot.py. No live calls."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).parents[2] / "scripts" / "cube_validate_snapshot.py"
FIX = Path(__file__).parent / "fixtures" / "cube_validate"


def _load():
    spec = importlib.util.spec_from_file_location("cube_validate_snapshot", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    # Registration before exec_module lets the module's dataclasses resolve.
    sys.modules["cube_validate_snapshot"] = mod
    spec.loader.exec_module(mod)
    return mod


snap = _load()
TWB = (FIX / "review.twb").read_text(encoding="utf-8", newline="")


def test_read_workbook_lists_each_dashboards_sheets():
    wb = snap.read_workbook(TWB)
    assert wb.dashboards == {"Overview": ["Overview - Table", "Overview - Detail"]}


def test_filter_cards_carry_field_caption_and_default():
    wb = snap.read_workbook(TWB)
    cards = {c.field: c for c in wb.filters}
    assert set(cards) == {
        "region", "school", "grade_level", "iep_status", "student_name",
        "Calculation_1", "academic_year",
    }
    assert cards["school"].caption == "School Name"  # explicit caption wins
    assert cards["grade_level"].caption == "Grade Level"  # Tableau's default
    assert cards["region"].default_all is True
    assert cards["iep_status"].default_all is False  # saved as "No IEP" only
    assert cards["school"].datasource == "rpt_demo (kipptaf_tableau)"


def test_calculated_filter_values_come_from_formula_literals():
    wb = snap.read_workbook(TWB)
    calc = next(c for c in wb.filters if c.field == "Calculation_1")
    assert calc.calculated is True
    assert calc.caption == "Is Tested"
    assert calc.values == ("Yes", "No")


def test_parameters_list_values_and_range_has_none():
    wb = snap.read_workbook(TWB)
    params = {p.caption: p for p in wb.params}
    assert params["Group By"].values == ("School", "Teacher", "Student")
    assert params["Group By"].default == "School"
    assert params["Goal %"].values == ()


def test_actions_are_filter_or_link():
    wb = snap.read_workbook(TWB)
    acts = {a.caption: a for a in wb.actions}
    assert acts["Table to Detail"].kind == "filter"
    assert acts["Table to Detail"].source_sheet == "Overview - Table"
    assert acts["Table to Detail"].target == "Overview"
    assert acts["Table to Detail"].exclude == ("Overview - Table",)
    assert acts["Open Report"].kind == "link"


@pytest.mark.parametrize(
    ("field", "caption"),
    [("grade_level", "Grade Level"), ("c_504_status", "C 504 Status"), ("Title", "Title")],
)
def test_default_caption(field, caption):
    assert snap.default_caption(field) == caption
```

- [ ] **Step 3: Run the tests to verify they fail**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate_snapshot.py -q 2>&1 | tail -n 30`
Expected: FAIL, `FileNotFoundError` or `AttributeError` (the script does not
exist yet).

- [ ] **Step 4: Write the implementation**

`scripts/cube_validate_snapshot.py`:

```python
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
        dash or "", a.get("caption") or "", sheet or "", kind, p.get("target", ""), exclude
    )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate_snapshot.py -q 2>&1 | tail -n 30`
Expected: 8 passed.

- [ ] **Step 6: Commit**

```bash
git add scripts/cube_validate_snapshot.py tests/scripts/test_cube_validate_snapshot.py tests/scripts/fixtures/cube_validate/review.twb
git commit -m "feat(cube): read dashboards, filter cards, parameters and actions from a workbook

Refs #5856

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

### Task 2: build the review copy

**Files:**

- Modify: `scripts/cube_validate_snapshot.py`
- Test: `tests/scripts/test_cube_validate_snapshot.py`

**Interfaces:**

- Consumes: `read_workbook`, `Workbook` (Task 1)
- Produces:
  - `review_copy(twb_text: str, dashboards: list[str]) -> str`
  - `views_to_hide(twb_text: str, keep: set[str]) -> list[str]`
  - `class ReviewCopyError(ValueError)`

The 3 edits come from the spike (`.claude/scratch/cube-dashboard/review/`
scripts 1 and 3, note 2): expose each sheet on the named dashboards, set every
filter action's `on-empty` to `all`, and strip saved `[Action (...)]` filters
and slice entries from each filter action's target sheets.

- [ ] **Step 1: Write the failing tests**

Append to `tests/scripts/test_cube_validate_snapshot.py`:

```python
def test_review_copy_exposes_dashboard_sheets_only():
    out = snap.review_copy(TWB, ["Overview"])
    assert "<window class='worksheet' name='Overview - Table' />" in out
    assert "<window class='worksheet' name='Overview - Detail' />" in out
    assert "hidden='true'" not in out
    # A sheet on no named dashboard keeps its window untouched.
    assert "<window class='worksheet' name='Scratch Sheet' />" in out


def test_review_copy_sets_on_empty_all_and_strips_click_filters():
    out = snap.review_copy(TWB, ["Overview"])
    assert "<param name='on-empty' value='all' />" in out
    assert "value='none'" not in out
    assert "[Action (" not in out


def test_review_copy_is_valid_xml_and_leaves_the_rest_alone():
    out = snap.review_copy(TWB, ["Overview"])
    snap.SafeET.fromstring(out)
    # The saved "No IEP" filter on the table is not a click filter: it stays.
    assert "member='&quot;No IEP&quot;'" in out


def test_review_copy_refuses_a_dashboard_it_cannot_find():
    with pytest.raises(snap.ReviewCopyError, match="Nope"):
        snap.review_copy(TWB, ["Nope"])


def test_review_copy_detects_a_sheet_left_hidden(monkeypatch):
    # Break the expose step: the check must catch it, not pass it silently.
    monkeypatch.setattr(snap, "_expose", lambda text, sheets: text)
    with pytest.raises(snap.ReviewCopyError, match="still hidden"):
        snap.review_copy(TWB, ["Overview"])


def test_views_to_hide_keeps_only_the_named_views():
    out = snap.review_copy(TWB, ["Overview"])
    hide = snap.views_to_hide(out, {"Overview", "Overview - Table", "Overview - Detail"})
    assert hide == ["Scratch Sheet"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate_snapshot.py -q -k "review_copy or views_to_hide" 2>&1 | tail -n 30`
Expected: FAIL, `AttributeError: ... has no attribute 'review_copy'`.

- [ ] **Step 3: Write the implementation**

Append to `scripts/cube_validate_snapshot.py`:

```python
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
        "<param name='on-empty' value='none' />", "<param name='on-empty' value='all' />"
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate_snapshot.py -q 2>&1 | tail -n 30`
Expected: 14 passed.

- [ ] **Step 5: Check the DDI spike base, not just the fixture**

The spike's base workbook is on disk (gitignored). Run the edit on it and the
repo's workbook checker against the untouched base:

```bash
cd /workspaces/teamster && uv run python - <<'EOF'
import importlib.util, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("s", "scripts/cube_validate_snapshot.py")
m = importlib.util.module_from_spec(spec); sys.modules["s"] = m; spec.loader.exec_module(m)
base = Path(".claude/scratch/cube-dashboard/review/base.twb").read_text(encoding="utf-8", newline="")
out = m.review_copy(base, ["Module Dashboard"])
Path(".claude/scratch/cube-dashboard/review/plan_check.twb").write_text(out, encoding="utf-8", newline="")
print("ok")
EOF
uv run python docs/tableau-xml/scripts/check_twb.py .claude/scratch/cube-dashboard/review/plan_check.twb --ref .claude/scratch/cube-dashboard/review/base.twb > /tmp/ct.txt 2>&1; echo "rc=$?"; tail -n 3 /tmp/ct.txt
```

Expected: `ok`, then `rc=0` and `plan_check.twb: CLEAN`. If the spike files are
gone, skip this step and say so in the task report.

- [ ] **Step 6: Commit**

```bash
git add -u scripts/cube_validate_snapshot.py tests/scripts/test_cube_validate_snapshot.py
git commit -m "feat(cube): build a review copy that exposes sheets and reproduces clicks

Refs #5856

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

### Task 3: profile the extract and score how filter fields nest

**Files:**

- Modify: `scripts/cube_validate_snapshot.py`
- Test: `tests/scripts/test_cube_validate_snapshot.py`

**Interfaces:**

- Produces:
  - `class Hyper` (context manager over one `.hyper` file;
    `query(sql: str) -> list[tuple]`; `columns() -> list[str]`)
  - `profile(hyper: Hyper, fields: list[str], student: str = "student_number", where: str | None = None) -> dict[str, list[tuple[str | None, int]]]`
    (each field's values with distinct students, largest first)
  - `nesting(hyper: Hyper, fields: list[str], where: str | None = None) -> tuple[dict[tuple[str, str], float], dict[str, int]]`
    (Goodman-Kruskal lambda keyed `(child, parent)`, and distinct counts with
    blank counted)
  - `make_hyper(path: Path, columns: list[tuple[str, str]], rows: list[tuple])`
    (test helper in the test file, not the script)

- [ ] **Step 1: Write the failing tests**

Append to `tests/scripts/test_cube_validate_snapshot.py`:

```python
def make_hyper(path, columns, rows):
    """A synthetic .hyper with one table, "Extract"."Extract"."""
    hapi = pytest.importorskip("tableauhyperapi")
    types = {
        "text": hapi.SqlType.text(),
        "int": hapi.SqlType.int(),
        "double": hapi.SqlType.double(),
    }
    table = hapi.TableDefinition(
        hapi.TableName("Extract", "Extract"),
        [hapi.TableDefinition.Column(n, types[t], hapi.NULLABLE) for n, t in columns],
    )
    with hapi.HyperProcess(hapi.Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hp:
        with hapi.Connection(hp.endpoint, str(path), hapi.CreateMode.CREATE_AND_REPLACE) as c:
            c.catalog.create_schema("Extract")
            c.catalog.create_table(table)
            with hapi.Inserter(c, table) as ins:
                ins.add_rows(rows)
                ins.execute()
    return path


COLUMNS = [
    ("student_number", "int"),
    ("academic_year", "int"),
    ("region", "text"),
    ("school", "text"),
    ("grade_level", "int"),
    ("homeroom", "text"),
    ("iep_status", "text"),
    ("is_flag", "text"),
]


def demo_rows():
    """2 regions, 2 schools each, grades 5 and 6, 1 homeroom per school-grade."""
    rows, sid = [], 0
    for region, schools in (("North", ("Alpha", "Beta")), ("South", ("Gamma", "Delta"))):
        for school in schools:
            for grade in (5, 6):
                for i in range(12):
                    sid += 1
                    iep = "Has IEP" if i % 4 == 0 else "No IEP"
                    flag = "Yes" if i == 0 else None
                    rows.append((sid, 2026, region, school, grade, f"{school}-{grade}", iep, flag))
    return rows


@pytest.fixture
def demo_hyper(tmp_path):
    return make_hyper(tmp_path / "demo.hyper", COLUMNS, demo_rows())


def test_profile_counts_distinct_students_and_keeps_blank(demo_hyper):
    with snap.Hyper(demo_hyper) as h:
        prof = snap.profile(h, ["region", "is_flag"])
    assert prof["region"] == [("North", 48), ("South", 48)]
    assert (None, 88) in prof["is_flag"] and ("Yes", 8) in prof["is_flag"]


def test_profile_where_limits_rows(demo_hyper):
    with snap.Hyper(demo_hyper) as h:
        prof = snap.profile(h, ["school"], where="\"region\" = 'North'")
    assert sorted(v for v, _ in prof["school"]) == ["Alpha", "Beta"]


def test_nesting_finds_school_inside_region_and_grade_crossing_school(demo_hyper):
    fields = ["region", "school", "grade_level", "homeroom", "iep_status"]
    with snap.Hyper(demo_hyper) as h:
        scores, distinct = snap.nesting(h, fields)
    assert scores[("school", "region")] == pytest.approx(1.0)
    assert scores[("homeroom", "school")] == pytest.approx(1.0)
    assert scores[("homeroom", "grade_level")] == pytest.approx(1.0)
    # grade has fewer values than school, so it is never scored as school's child,
    # and school does not predict grade: they cross.
    assert ("grade_level", "school") not in scores
    assert scores[("school", "grade_level")] == pytest.approx(0.0)
    assert distinct["homeroom"] == 8


def test_nesting_scores_a_lopsided_parent_as_zero_not_one(demo_hyper):
    # is_flag is blank on 11 of 12 rows: "school predicts is_flag" must not
    # score near 1 just because blank is the majority everywhere.
    with snap.Hyper(demo_hyper) as h:
        scores, _ = snap.nesting(h, ["school", "is_flag"])
    assert scores[("school", "is_flag")] == pytest.approx(0.0)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate_snapshot.py -q -k "profile or nesting" 2>&1 | tail -n 30`
Expected: FAIL, `AttributeError: ... has no attribute 'Hyper'`.

- [ ] **Step 3: Write the implementation**

Add `import itertools` and `from pathlib import Path` to the imports, then
append:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate_snapshot.py -q 2>&1 | tail -n 30`
Expected: 18 passed.

- [ ] **Step 5: Commit**

```bash
git add -u scripts/cube_validate_snapshot.py tests/scripts/test_cube_validate_snapshot.py
git commit -m "feat(cube): profile extract filter values and score how fields nest

Refs #5856

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

### Task 4: derive trees from the nesting scores

**Files:**

- Modify: `scripts/cube_validate_snapshot.py`
- Test: `tests/scripts/test_cube_validate_snapshot.py`

**Interfaces:**

- Consumes: the `(scores, distinct)` pair from `nesting` (Task 3)
- Produces:
  - `Trees(trees: dict[str, list[str]], cross_cuts: list[str], borderline: list[tuple[str, str, float]])`
    (each tree is keyed by its root field and lists its levels top-down)
  - `derive_trees(fields: list[str], scores: dict[tuple[str, str], float], distinct: dict[str, int], accept: set[tuple[str, str]] = frozenset()) -> Trees`
    (`accept` holds borderline `(child, parent)` pairs the analyst accepted)

Rule: an edge `child → parent` exists when the score is at least `NEST`, or the
pair is in `accept`. Pairs from `NEST_ASK` up to `NEST` go to `borderline`. Each
connected group of edges is one tree. Its levels are the longest parent-to-child
chain (the spine). Every other field in the group goes just before the first
spine field it contains, or at the end if it contains none. Fields with no edge
are cross-cuts.

- [ ] **Step 1: Write the failing tests**

Append:

```python
# Scores as measured on the DDI weekly extract (2026-10-09), rounded.
DDI_SCORES = {
    ("head_of_school", "region"): 1.0,
    ("school", "region"): 1.0,
    ("school", "head_of_school"): 1.0,
    ("school", "school_level"): 1.0,
    ("homeroom_section", "region"): 0.941,
    ("homeroom_section", "head_of_school"): 0.960,
    ("homeroom_section", "school"): 0.909,
    ("homeroom_section", "grade_level"): 0.996,
    ("course_section", "grade_level"): 0.877,
    ("week_start_monday", "term"): 1.0,
    ("module_code", "module_type"): 1.0,
    ("school", "grade_level"): 0.10,
}
DDI_DISTINCT = {
    "region": 4, "school_level": 3, "head_of_school": 9, "school": 24,
    "grade_level": 13, "homeroom_section": 389, "course_section": 409,
    "term": 2, "week_start_monday": 21, "module_type": 6, "module_code": 20,
    "iep_status": 2,
}


def test_derive_trees_matches_the_ddi_measurement():
    t = snap.derive_trees(list(DDI_DISTINCT), DDI_SCORES, DDI_DISTINCT)
    assert t.trees["region"] == [
        "region", "head_of_school", "school_level", "school", "grade_level",
        "homeroom_section",
    ]
    assert t.trees["term"] == ["term", "week_start_monday"]
    assert t.trees["module_type"] == ["module_type", "module_code"]
    assert t.cross_cuts == ["course_section", "iep_status"]
    assert t.borderline == [("course_section", "grade_level", 0.877)]


def test_an_accepted_borderline_pair_joins_its_tree():
    t = snap.derive_trees(
        list(DDI_DISTINCT), DDI_SCORES, DDI_DISTINCT,
        accept={("course_section", "grade_level")},
    )
    assert "course_section" in t.trees["region"]
    assert t.borderline == []
    assert "course_section" not in t.cross_cuts
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate_snapshot.py -q -k derive_trees 2>&1 | tail -n 30`
Expected: FAIL, `AttributeError: ... has no attribute 'derive_trees'`.

- [ ] **Step 3: Write the implementation**

Add `from dataclasses import dataclass, field` (replacing the plain `dataclass`
import), then append:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate_snapshot.py -q 2>&1 | tail -n 30`
Expected: 20 passed.

- [ ] **Step 5: Commit**

```bash
git add -u scripts/cube_validate_snapshot.py tests/scripts/test_cube_validate_snapshot.py
git commit -m "feat(cube): derive filter trees and cross-cuts from nesting scores

Refs #5856

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

### Task 5: plan the states

**Files:**

- Modify: `scripts/cube_validate_snapshot.py`
- Test: `tests/scripts/test_cube_validate_snapshot.py`

**Interfaces:**

- Consumes: `Workbook`, `FilterCard`, `Param`, `Action` (Task 1), `Trees` (Task
  4), profiles from `profile` (Task 3)
- Produces:
  - `ALL = "(All)"`, `BLANK = "(Blank)"`, `SMALL_CELL = 10`
  - `State(dashboard: str, filters: tuple[tuple[str, str], ...] = (), params: tuple[tuple[str, str], ...] = (), click: tuple[str, str] | None = None)`
    (frozen; `.id -> str`; `.as_dict() -> dict`; `State.from_dict(d) -> State`)
  - `PlanItem(state: State, tier: str, why: str)` (`tier` is `must`, `optional`
    or `skipped`)
  - `plan_states(wb: Workbook, profiles: dict[str, dict[str, list[tuple[str | None, int]]]], trees: dict[str, Trees], years: tuple[str, ...]) -> list[PlanItem]`
    (`profiles` and `trees` are keyed by datasource caption)
  - `plan_yaml(items: list[PlanItem]) -> str`

- [ ] **Step 1: Write the failing tests**

Append:

```python
DS = "rpt_demo (kipptaf_tableau)"
PROFILES = {
    DS: {
        "region": [("North", 48), ("South", 48)],
        "school": [("Alpha", 24), ("Beta", 24), ("Gamma", 24), ("Delta", 6)],
        "grade_level": [("5", 48), ("6", 48)],
        "iep_status": [("No IEP", 72), ("Has IEP", 24), (None, 3)],
        "academic_year": [("2026", 96), ("2025", 90), ("2024", 80)],
        "student_name": [("someone", 1)],
    }
}
TREES = {DS: snap.Trees({"region": ["region", "school", "grade_level"]}, ["iep_status"])}


def _plan():
    wb = snap.read_workbook(TWB)
    return snap.plan_states(wb, PROFILES, TREES, ("2026", "2025"))


def _ids(items, tier):
    return {i.state.id for i in items if i.tier == tier}


def test_state_ids_are_stable_and_readable():
    s = snap.State("Overview", filters=(("School Name", "Alpha"), ("Region", "North")))
    assert s.id == "overview--region-north--school-name-alpha"
    assert snap.State("Overview").id == "overview--default"
    assert snap.State.from_dict(s.as_dict()) == s


def test_must_includes_default_params_tree_top_crosscuts_years_and_clicks():
    must = _ids(_plan(), "must")
    assert "overview--default" in must
    assert "overview--group-by-teacher" in must
    assert {"overview--region-north", "overview--region-south"} <= must
    assert {"overview--iep-status-no-iep", "overview--iep-status-has-iep"} <= must
    assert "overview--iep-status-blank" in must
    assert {"overview--academic-year-2026", "overview--academic-year-2025"} <= must
    assert "overview--academic-year-2024" not in must
    assert "overview--is-tested-yes" in must  # calculated filter, every value
    assert "overview--iep-status-all" in must  # saved default is not All
    assert "overview--click-table-to-detail-largest" in must
    assert "overview--click-table-to-detail-small" in must


def test_person_level_values_and_links_are_skipped_not_exported():
    items = _plan()
    skipped = _ids(items, "skipped")
    assert "overview--group-by-student" in skipped  # person-level parameter value
    assert "overview--group-by-student" not in _ids(items, "must")
    assert any(i.state.id.startswith("overview--student-name") for i in items if i.tier == "skipped")
    assert "overview--click-open-report-largest" in skipped
    assert any("free-entry" in i.why for i in items if i.tier == "skipped")


def test_tree_levels_below_the_top_are_left_to_the_descent():
    every = {i.state.id for i in _plan()}
    assert not any(i.startswith("overview--school-name-") for i in every)


def test_plan_yaml_groups_by_tier():
    text = snap.plan_yaml(_plan())
    assert text.index("must:") < text.index("optional:") < text.index("skipped:")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate_snapshot.py -q -k "state or plan" 2>&1 | tail -n 30`
Expected: FAIL, `AttributeError: ... has no attribute 'State'`.

- [ ] **Step 3: Write the implementation**

Add `import yaml` to the imports, then append:

```python
ALL = "(All)"
BLANK = "(Blank)"
SMALL_CELL = 10
YEAR_FIELD = "academic_year"
# Person-level filters and parameter values: never exported, never in a draft.
PERSON_FIELD = re.compile(r"(lastfirst|student_name|first_name|last_name|teacher_name)$")
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
        return "--".join([slug(self.dashboard), *(slug(p) for p in parts or ["default"])])

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
                add("skipped", f"{p.caption}: free-entry parameter, default only",
                    params=((p.caption, p.default),))
            for v in p.values:
                if v in PERSON_VALUES:
                    add("skipped", f"{p.caption} = {v}: person-level", params=((p.caption, v),))
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
                    add("optional", "plain filter, largest and smallest", filters=one(v))

        for a in (a for a in wb.actions if a.dashboard == dash):
            if a.kind != "filter":
                add("skipped", f"{a.caption}: {a.kind} action", click=(a.caption, "largest"))
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate_snapshot.py -q 2>&1 | tail -n 30`
Expected: 25 passed.

- [ ] **Step 5: Commit**

```bash
git add -u scripts/cube_validate_snapshot.py tests/scripts/test_cube_validate_snapshot.py
git commit -m "feat(cube): plan must, optional and skipped dashboard states

Refs #5856

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

### Task 6: the snapshot folder, manifest and filter-took-effect check

**Files:**

- Modify: `scripts/cube_validate_snapshot.py`
- Test: `tests/scripts/test_cube_validate_snapshot.py`

**Interfaces:**

- Consumes: `State`, `slug` (Task 5)
- Produces:
  - `SNAPSHOT_ROOT = Path.home() / ".cache" / "cube-validate"`,
    `KEEP_SNAPSHOTS = 2`
  - `new_snapshot_dir(workbook: str, at: dt.datetime, root: Path = SNAPSHOT_ROOT) -> Path`
    (creates `<root>/<slug>/<YYYY-MM-DDTHHMM>/` after deleting all but the
    newest `KEEP_SNAPSHOTS - 1` older folders)
  - `latest_snapshot(workbook: str, root: Path = SNAPSHOT_ROOT) -> Path`
  - `Manifest` dataclass: `workbook: str`, `workbook_luid: str`,
    `copy_luid: str | None`, `opened_at: str`, `live_updated_at: str`,
    `extracts: dict[str, dict]`
    (`{datasource: {"file": str, "refreshed": str}}`), `fields: dict[str, dict]`
    (`{caption: {"field": str, "datasource": str}}`), `states: dict[str, dict]`
    (`{state_id: {"state": dict, "sheets": {sheet: {"file": str, "rows": int}}, "status": str, "click_filters": dict}}`),
    `closed: bool = False`
  - `write_manifest(path: Path, m: Manifest) -> None`,
    `read_manifest(path: Path) -> Manifest`
  - `csv_rows(data: bytes) -> int` (data rows, header excluded)
  - `filter_ignored(parent: dict[str, bytes], current: dict[str, bytes], covers_all: bool) -> bool`
  - `parent_of(state: State) -> State` (the state without its last filter, or
    the default view for a parameter or click state)

- [ ] **Step 1: Write the failing tests**

Append:

```python
import datetime as dt


def test_new_snapshot_dir_keeps_the_latest_two(tmp_path):
    t0 = dt.datetime(2026, 10, 9, 8, 0)
    dirs = [snap.new_snapshot_dir("DDI Suite", t0 + dt.timedelta(hours=h), tmp_path) for h in range(3)]
    left = sorted(p.name for p in (tmp_path / "ddi-suite").iterdir())
    assert left == [dirs[1].name, dirs[2].name]
    assert snap.latest_snapshot("DDI Suite", tmp_path) == dirs[2]


def test_manifest_round_trips(tmp_path):
    m = snap.Manifest(
        workbook="DDI Suite", workbook_luid="w1", copy_luid="c1",
        opened_at="2026-10-09T08:00:00+00:00", live_updated_at="2026-10-09T05:00:00+00:00",
        extracts={DS: {"file": "federated_demo1.hyper", "refreshed": "2026-10-08T05:39:00+00:00"}},
        fields={"Region": {"field": "region", "datasource": DS}},
        states={},
    )
    snap.write_manifest(tmp_path / "manifest.json", m)
    assert snap.read_manifest(tmp_path / "manifest.json") == m


def test_csv_rows_counts_data_rows_and_survives_empty_exports():
    assert snap.csv_rows(b"\xef\xbb\xbfA,B\r\n1,2\r\n3,4\r\n") == 2
    assert snap.csv_rows(b"A,B\r\n") == 0
    assert snap.csv_rows(b"") == 0


def test_filter_ignored_when_every_sheet_is_unchanged():
    parent = {"S1": b"a\r\n1\r\n", "S2": b"b\r\n2\r\n"}
    assert snap.filter_ignored(parent, dict(parent), covers_all=False) is True
    assert snap.filter_ignored(parent, {"S1": b"a\r\n9\r\n", "S2": parent["S2"]}, covers_all=False) is False


def test_filter_unchanged_is_fine_when_the_value_covers_every_row():
    parent = {"S1": b"a\r\n1\r\n"}
    assert snap.filter_ignored(parent, dict(parent), covers_all=True) is False


def test_empty_exports_on_both_sides_are_not_read_as_ignored():
    # A state can legitimately empty a sheet the parent also left empty.
    parent = {"S1": b"a\r\n"}
    assert snap.filter_ignored(parent, {"S1": b"a\r\n"}, covers_all=False) is False


def test_parent_of_drops_the_last_filter():
    s = snap.State("Overview", filters=(("Region", "North"), ("School Name", "Alpha")))
    assert snap.parent_of(s) == snap.State("Overview", filters=(("Region", "North"),))
    assert snap.parent_of(snap.State("Overview", params=(("Group By", "Teacher"),))) == snap.State("Overview")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate_snapshot.py -q -k "snapshot or manifest or csv_rows or ignored or parent_of" 2>&1 | tail -n 30`
Expected: FAIL, `AttributeError: ... has no attribute 'new_snapshot_dir'`.

- [ ] **Step 3: Write the implementation**

Add `import csv`, `import datetime as dt`, `import io`, `import json`,
`import shutil` and `from dataclasses import asdict` to the imports, then
append:

```python
SNAPSHOT_ROOT = Path.home() / ".cache" / "cube-validate"
KEEP_SNAPSHOTS = 2


def new_snapshot_dir(workbook: str, at: dt.datetime, root: Path = SNAPSHOT_ROOT) -> Path:
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


def filter_ignored(parent: dict[str, bytes], current: dict[str, bytes], covers_all: bool) -> bool:
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate_snapshot.py -q 2>&1 | tail -n 30`
Expected: 32 passed.

- [ ] **Step 5: Commit**

```bash
git add -u scripts/cube_validate_snapshot.py tests/scripts/test_cube_validate_snapshot.py
git commit -m "feat(cube): snapshot folders, manifest and the filter-took-effect check

Refs #5856

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

### Task 7: the Tableau session (sweep, publish, export, download, close)

**Files:**

- Modify: `scripts/cube_validate_snapshot.py`
- Test: `tests/scripts/test_cube_validate_snapshot.py`

**Interfaces:**

- Consumes: `review_copy`, `views_to_hide` (Task 2), `State`, `ALL`, `BLANK`
  (Task 5), `Manifest`, `csv_rows`, `filter_ignored`, `parent_of` (Task 6),
  `profile` output (Task 3)
- Produces:
  - `NON_PRODUCTION_PROJECTS = {"ddc817c2-6bc7-4bca-8be9-e385f95b9ebc": "TEMP-CB"}`,
    `REVIEW_PREFIX = "ZZ-REVIEW "`, `STALE_COPY = dt.timedelta(hours=24)`
  - `class SessionError(RuntimeError)`, `class RefreshedError(SessionError)`
  - `vf_value(value: str, all_values: list[str]) -> str` (escapes commas; `ALL`
    becomes every value joined with commas; `BLANK` becomes `"Null"`)
  - `retry(fn, attempts: int = 3, sleep=time.sleep, wait: float = 5.0)` (from v1
    lines 1994-2003, verbatim)
  - `pick_click_row(export: bytes, mark: str, dims: list[str] | None) -> dict[str, str]`
    (the largest or smallest mark's dimension values)
  - `class Session` with `__init__(self, server, project_luid: str, now=...)`,
    `sweep() -> list[str]`,
    `publish(twbx: Path, name: str, hidden: list[str]) -> str`,
    `export_view(sheet: str, filters: list[tuple[str, str]]) -> bytes`,
    `check_refresh(live_luid: str, recorded: str) -> None`,
    `close(copy_luid: str) -> None`
  - `build_review_twbx(live_twbx: Path, out_dir: Path, dashboards: list[str]) -> tuple[Path, list[str]]`
    (the repacked review `.twbx` and the views to hide, after `check_twb.py` and
    `repack.py` pass)
  - `unpack_extracts(twbx: Path, out_dir: Path) -> dict[str, dict]`
    (`{datasource caption: {"file": name, "refreshed": iso}}`)

The `Session` takes a `server` object so tests pass a fake. `_workbooks_in` is a
module function so tests can replace it.

- [ ] **Step 1: Write the failing tests**

Append:

```python
from types import SimpleNamespace


class FakeWorkbooks:
    def __init__(self, items):
        self.items = {w.id: w for w in items}
        self.deleted, self.published = [], []

    def delete(self, luid):
        self.deleted.append(luid)
        self.items.pop(luid, None)

    def publish(self, item, path, mode):
        self.published.append((item.name, item.project_id, list(item.hidden_views), mode))
        new = SimpleNamespace(id="copy-1", name=item.name, project_id=item.project_id,
                              project_name="TEMP-CB", created_at=None)
        self.items[new.id] = new
        return new

    def get_by_id(self, luid):
        return SimpleNamespace(updated_at=dt.datetime(2026, 10, 9, 5, 0, tzinfo=dt.UTC))


def _session(monkeypatch, items):
    wbs = FakeWorkbooks(items)
    server = SimpleNamespace(workbooks=wbs)
    monkeypatch.setattr(snap, "_workbooks_in", lambda server, project: list(wbs.items.values()))
    now = lambda: dt.datetime(2026, 10, 9, 12, 0, tzinfo=dt.UTC)  # noqa: E731
    return snap.Session(server, snap.TEMP_CB, now=now), wbs


def test_session_refuses_a_production_project():
    with pytest.raises(snap.SessionError, match="non-production"):
        snap.Session(SimpleNamespace(), "some-production-project")


def test_sweep_deletes_only_old_review_copies(monkeypatch):
    old = SimpleNamespace(id="a", name="ZZ-REVIEW 2026-10-07 0800 DDI Suite",
                          created_at=dt.datetime(2026, 10, 7, 8, tzinfo=dt.UTC), project_id=snap.TEMP_CB)
    fresh = SimpleNamespace(id="b", name="ZZ-REVIEW 2026-10-09 1100 DDI Suite",
                            created_at=dt.datetime(2026, 10, 9, 11, tzinfo=dt.UTC), project_id=snap.TEMP_CB)
    mine = SimpleNamespace(id="c", name="My Draft", created_at=dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
                           project_id=snap.TEMP_CB)
    s, wbs = _session(monkeypatch, [old, fresh, mine])
    assert s.sweep() == ["ZZ-REVIEW 2026-10-07 0800 DDI Suite"]
    assert wbs.deleted == ["a"]


def test_publish_requires_the_prefix_and_creates_new(monkeypatch, tmp_path):
    s, wbs = _session(monkeypatch, [])
    with pytest.raises(snap.SessionError, match="ZZ-REVIEW"):
        s.publish(tmp_path / "x.twbx", "DDI Suite", [])
    luid = s.publish(tmp_path / "x.twbx", "ZZ-REVIEW 2026-10-09 1200 DDI Suite", ["Scratch Sheet"])
    assert luid == "copy-1"
    name, project, hidden, mode = wbs.published[0]
    assert project == snap.TEMP_CB and hidden == ["Scratch Sheet"] and mode == "CreateNew"


def test_close_confirms_the_copy_is_gone(monkeypatch):
    copy = SimpleNamespace(id="copy-1", name="ZZ-REVIEW x", created_at=None, project_id=snap.TEMP_CB)
    s, wbs = _session(monkeypatch, [copy])
    s.close("copy-1")
    assert wbs.deleted == ["copy-1"]


def test_close_raises_with_the_luid_when_the_copy_survives(monkeypatch):
    copy = SimpleNamespace(id="copy-1", name="ZZ-REVIEW x", created_at=None, project_id=snap.TEMP_CB)
    s, wbs = _session(monkeypatch, [copy])
    wbs.delete = lambda luid: None  # the server ignores the delete
    with pytest.raises(snap.SessionError, match="copy-1"):
        s.close("copy-1")


def test_check_refresh_stops_when_the_live_workbook_moved(monkeypatch):
    s, _ = _session(monkeypatch, [])
    s.check_refresh("w1", "2026-10-09T05:00:00+00:00")
    with pytest.raises(snap.RefreshedError):
        s.check_refresh("w1", "2026-10-08T05:00:00+00:00")


def test_vf_value_escapes_commas_and_expands_all_and_blank():
    assert snap.vf_value("KIPP, Newark", []) == "KIPP\\, Newark"
    assert snap.vf_value(snap.ALL, ["A", "B, C"]) == "A,B\\, C"
    assert snap.vf_value(snap.BLANK, []) == "Null"


def test_pick_click_row_takes_the_largest_or_smallest_mark():
    data = "Title,School,Score\r\nT1,All,50\r\nT1,Alpha,80\r\nT2,Beta,20\r\nT3,*,90\r\n".encode()
    assert snap.pick_click_row(data, "largest", ["Title", "School"]) == {"Title": "T1", "School": "Alpha"}
    assert snap.pick_click_row(data, "small", ["Title", "School"]) == {"Title": "T2", "School": "Beta"}


def test_retry_recovers_then_gives_up():
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 2:
            raise RuntimeError("401002")
        return "ok"

    assert snap.retry(flaky, sleep=lambda s: None) == "ok"
    with pytest.raises(RuntimeError):
        snap.retry(lambda: (_ for _ in ()).throw(RuntimeError("x")), sleep=lambda s: None)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate_snapshot.py -q -k "session or sweep or publish or close or refresh or vf_value or click_row or retry" 2>&1 | tail -n 30`
Expected: FAIL, `AttributeError: ... has no attribute 'Session'`.

- [ ] **Step 3: Write the implementation**

Add `import os`, `import subprocess`, `import time` and `import zipfile` to the
imports, then append:

```python
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
            raise SessionError(f"{project_luid} is not an agreed non-production project")
        self.server, self.project, self.now = server, project_luid, now
        self._views: dict[str, object] = {}

    def sweep(self) -> list[str]:
        """Delete review copies older than STALE_COPY: leftovers of failed sessions."""
        cutoff, gone = self.now() - STALE_COPY, []
        for w in _workbooks_in(self.server, self.project):
            if w.name.startswith(REVIEW_PREFIX) and w.created_at and w.created_at < cutoff:
                self.server.workbooks.delete(w.id)
                gone.append(w.name)
        return gone

    def publish(self, twbx: Path, name: str, hidden: list[str]) -> str:
        import tableauserverclient as tsc

        if not name.startswith(REVIEW_PREFIX):
            raise SessionError(f"review copies carry the {REVIEW_PREFIX.strip()} prefix")
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
    r = subprocess.run(  # noqa: S603 - fixed repo scripts, no shell
        ["uv", "run", "python", *args], capture_output=True, text=True, check=False
    )
    if r.returncode:
        raise SessionError(f"{Path(args[0]).name} failed:\n{r.stdout[-2000:]}{r.stderr[-2000:]}")


def build_review_twbx(live_twbx: Path, out_dir: Path, dashboards: list[str]) -> tuple[Path, list[str]]:
    """Edit the live workbook into a review copy and pass the tableau-workbook-xml gates."""
    with zipfile.ZipFile(live_twbx) as z:
        twb_name = next(n for n in z.namelist() if n.endswith(".twb"))
        base = z.read(twb_name).decode("utf-8")
    (out_dir / "base.twb").write_text(base, encoding="utf-8", newline="")
    review = review_copy(base, dashboards)
    (out_dir / "review.twb").write_text(review, encoding="utf-8", newline="")
    _run([str(XML_SCRIPTS / "check_twb.py"), str(out_dir / "review.twb"), "--ref", str(out_dir / "base.twb")])
    out = out_dir / "review.twbx"
    _run([str(XML_SCRIPTS / "repack.py"), str(out_dir / "review.twb"), str(live_twbx), str(out)])
    wb = read_workbook(review)
    keep = set(dashboards) | {s for d in dashboards for s in wb.dashboards[d]}
    return out, views_to_hide(review, keep)


def unpack_extracts(twbx: Path, out_dir: Path) -> dict[str, dict]:
    """Each datasource's .hyper from a downloaded .twbx, with its refresh time (UTC)."""
    out = {}
    with zipfile.ZipFile(twbx) as z:
        twb = z.read(next(n for n in z.namelist() if n.endswith(".twb"))).decode("utf-8")
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
                dt.datetime.strptime(raw, "%m/%d/%Y %I:%M:%S %p").replace(tzinfo=dt.UTC).isoformat()
                if raw
                else None
            )
            out[ds.get("caption")] = {"file": name, "refreshed": at}
    return out
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate_snapshot.py -q 2>&1 | tail -n 30`
Expected: 41 passed.

- [ ] **Step 5: Smoke-test the runtime path of the tableauserverclient calls**

`hasattr` and imports pass when an SDK call is wrong, so call each one against a
mock:

```bash
cd /workspaces/teamster && uv run python - <<'EOF'
import tableauserverclient as tsc
from unittest import mock
opts = tsc.CSVRequestOptions().vf("School Name", "KIPP\\, Newark")
print("vf ok:", type(opts).__name__)
item = tsc.WorkbookItem(project_id="p", name="ZZ-REVIEW x", show_tabs=True)
item.hidden_views = ["a"]
print("hidden_views ok:", item.hidden_views)
print("CreateNew is", tsc.Server.PublishMode.CreateNew)
EOF
```

Expected: 3 lines, `CreateNew is CreateNew`. If `PublishMode.CreateNew` is not
the string `"CreateNew"`, change `mode="CreateNew"` in `Session.publish` to
`mode=tsc.Server.PublishMode.CreateNew` and the test's expectation to match.

- [ ] **Step 6: Commit**

```bash
git add -u scripts/cube_validate_snapshot.py tests/scripts/test_cube_validate_snapshot.py
git commit -m "feat(cube): review-copy session with sweep, gated publish, export and close

Refs #5856

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

### Task 8: the snapshot command line (`plan`, `open`, `export`, `close`)

**Files:**

- Modify: `scripts/cube_validate_snapshot.py`
- Test: `tests/scripts/test_cube_validate_snapshot.py`

**Interfaces:**

- Consumes: everything in Tasks 1-7
- Produces:
  - `export_state(session: Session, manifest: Manifest, snapdir: Path, wb: Workbook, state: State, all_values: dict[str, list[str]], covers_all: dict[str, set[str]], dims_for: dict[str, list[str]]) -> dict`
    (one manifest state entry; writes CSVs under
    `snapdir/csv/<sheet-slug>/<state id>.csv`)
  - `main(argv: list[str] | None = None) -> int`
  - Checks-file keys this script reads: `workbook`, `workbook_luid`,
    `review_project_luid`, `dashboards` (list of dashboard names to review),
    `states` (list of state dicts, `State.from_dict` shape), `trees`,
    `cross_cuts`, `accept_nesting` (list of `[child, parent]`), and
    `sheets.<name>.dims` (captions, for click rows)

`export_state` sequence for one state:

1. Resolve filters: each `(caption, value)` through `vf_value`, with
   `all_values[caption]` for `ALL`. Parameters pass through unchanged.
2. For a click state: export the action's source sheet at the default view,
   `pick_click_row` the mark, and add its dimension values as filters. Export
   only the action's target sheets (the target dashboard's sheets minus
   `exclude`). Record the click filters in `click_filters`.
3. Export every other state's sheets: all sheets on its dashboard.
4. Status: `export_failed` if any export raised after retries; else
   `filter_ignored` if `filter_ignored(parent CSVs, these CSVs, covers)` holds,
   where the parent CSVs are read from the parent state's files; else `ok`.

- [ ] **Step 1: Write the failing tests**

Append:

```python
class FakeSession:
    def __init__(self, exports):
        self.exports, self.calls = exports, []

    def export_view(self, sheet, filters):
        self.calls.append((sheet, tuple(filters)))
        return self.exports(sheet, dict(filters))


def _manifest():
    return snap.Manifest("Demo", "w1", "copy-1", "t", "t", {}, {"Region": {"field": "region", "datasource": DS}}, {})


def test_export_state_writes_csvs_and_marks_ok(tmp_path):
    snapdir = tmp_path
    (snapdir / "csv").mkdir()
    wb = snap.read_workbook(TWB)
    def exports(sheet, f):
        return f"Region,N\r\n{f.get('Region', 'All')},1\r\n".encode()
    s, m = FakeSession(exports), _manifest()
    default = snap.State("Overview")
    m.states[default.id] = snap.export_state(s, m, snapdir, wb, default, {}, {}, {})
    north = snap.State("Overview", filters=(("Region", "North"),))
    entry = snap.export_state(s, m, snapdir, wb, north, {}, {}, {})
    assert entry["status"] == "ok"
    assert entry["sheets"]["Overview - Table"]["rows"] == 1
    assert (snapdir / "csv" / "overview-table" / f"{north.id}.csv").exists()


def test_export_state_flags_an_ignored_filter(tmp_path):
    (tmp_path / "csv").mkdir()
    wb = snap.read_workbook(TWB)
    s, m = FakeSession(lambda sheet, f: b"Region,N\r\nAll,9\r\n"), _manifest()
    default = snap.State("Overview")
    m.states[default.id] = snap.export_state(s, m, tmp_path, wb, default, {}, {}, {})
    north = snap.State("Overview", filters=(("Region", "North"),))
    assert snap.export_state(s, m, tmp_path, wb, north, {}, {}, {})["status"] == "filter_ignored"


def test_export_state_marks_a_failing_export(tmp_path):
    (tmp_path / "csv").mkdir()
    wb = snap.read_workbook(TWB)
    def boom(sheet, f):
        raise RuntimeError("429")
    entry = snap.export_state(FakeSession(boom), _manifest(), tmp_path, wb, snap.State("Overview"), {}, {}, {})
    assert entry["status"] == "export_failed"


def test_click_state_exports_targets_with_the_clicked_marks_values(tmp_path):
    (tmp_path / "csv").mkdir()
    wb = snap.read_workbook(TWB)
    def exports(sheet, f):
        if sheet == "Overview - Table" and not f:
            return b"Title,Score\r\nT1,80\r\nT2,20\r\n"
        return b"Title,Score\r\nT1,80\r\n"
    s = FakeSession(exports)
    state = snap.State("Overview", click=("Table to Detail", "largest"))
    entry = snap.export_state(s, _manifest(), tmp_path, wb, state, {}, {}, {"Overview - Table": ["Title"]})
    assert entry["click_filters"] == {"Title": "T1"}
    assert ("Overview - Detail", (("Title", "T1"),)) in s.calls
    assert list(entry["sheets"]) == ["Overview - Detail"]


def test_plan_command_writes_a_proposal_from_a_local_twbx(tmp_path, demo_hyper):
    twbx = tmp_path / "demo.twbx"
    with snap.zipfile.ZipFile(twbx, "w") as z:
        z.writestr("Demo.twb", TWB)
        z.write(demo_hyper, "Data/Extracts/federated_demo1.hyper")
    checks = tmp_path / "checks.yml"
    checks.write_text("workbook: Demo\nworkbook_luid: w1\ndashboards: [Overview]\n")
    out = tmp_path / "plan.yml"
    assert snap.main(["plan", str(checks), "--twbx", str(twbx), "--out", str(out)]) == 0
    text = out.read_text()
    assert "overview--default" in text and "trees:" in text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate_snapshot.py -q -k "export_state or click_state or plan_command" 2>&1 | tail -n 30`
Expected: FAIL, `AttributeError: ... has no attribute 'export_state'`.

- [ ] **Step 3: Write the implementation**

Add `import argparse` to the imports, then append:

```python
def _csv_path(snapdir: Path, sheet: str, state_id: str) -> Path:
    p = Path(snapdir) / "csv" / slug(sheet) / f"{state_id}.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _read_state(snapdir: Path, entry: dict | None) -> dict[str, bytes]:
    if not entry:
        return {}
    return {s: (Path(snapdir) / v["file"]).read_bytes() for s, v in entry["sheets"].items()}


def export_state(session, manifest, snapdir, wb, state, all_values, covers_all, dims_for) -> dict:
    filters = [(k, vf_value(v, all_values.get(k, []))) for k, v in state.filters]
    filters += list(state.params)
    sheets = list(wb.dashboards[state.dashboard])
    click_filters: dict[str, str] = {}
    entry = {"state": state.as_dict(), "sheets": {}, "status": "ok", "click_filters": {}}
    try:
        if state.click:
            action = next(a for a in wb.actions if a.caption == state.click[0])
            source = session.export_view(action.source_sheet, filters)
            click_filters = pick_click_row(source, state.click[1], dims_for.get(action.source_sheet))
            filters += [(k, vf_value(v, [])) for k, v in click_filters.items()]
            sheets = [s for s in wb.dashboards[action.target] if s not in action.exclude]
        data = {s: session.export_view(s, filters) for s in sheets}
    except Exception as e:  # noqa: BLE001 - recorded per state, the run goes on
        entry["status"], entry["error"] = "export_failed", f"{type(e).__name__}: {str(e)[:300]}"
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
        fields = sorted({c.field for c in wb.filters if c.datasource == ds and not c.calculated})
        if not fields:
            continue
        with Hyper(Path(snapdir) / meta["file"]) as h:
            cols = set(h.columns())
            fields = [f for f in fields if f in cols]
            where = None
            if where_year and YEAR_FIELD in cols:
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
        twb = z.read(next(n for n in z.namelist() if n.endswith(".twb"))).decode("utf-8")
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
        {v for ds in profiles for v, _ in profiles[ds].get(YEAR_FIELD, []) if v}, reverse=True
    )[:2]
    items = plan_states(wb, profiles, trees, tuple(years))
    doc = {
        "trees": {ds: t.trees for ds, t in trees.items()},
        "cross_cuts": {ds: t.cross_cuts for ds, t in trees.items()},
        "borderline": {ds: [list(b) for b in t.borderline] for ds, t in trees.items()},
    }
    text = yaml.safe_dump(doc, sort_keys=False, allow_unicode=True) + plan_yaml(items)
    Path(a.out or out_dir / "plan.yml").write_text(text)
    print(f"plan: {sum(i.tier == 'must' for i in items)} must, "
          f"{sum(i.tier == 'optional' for i in items)} optional, "
          f"{sum(i.tier == 'skipped' for i in items)} skipped -> {a.out or out_dir / 'plan.yml'}")
    return 0


def _server():
    import tableauserverclient as tsc

    auth = tsc.PersonalAccessTokenAuth(
        token_name=os.environ["TABLEAU_TOKEN_NAME"],
        personal_access_token=os.environ["TABLEAU_PERSONAL_ACCESS_TOKEN"],
        site_id=os.environ["TABLEAU_SITE_ID"],
    )
    return tsc.Server(os.environ["TABLEAU_SERVER_ADDRESS"], use_server_version=True), auth


def _download(luid: str, out_dir: Path) -> tuple[Path, str]:
    server, auth = _server()

    def fetch():
        with server.auth.sign_in(auth):
            at = server.workbooks.get_by_id(luid).updated_at
            path = server.workbooks.download(luid, filepath=str(out_dir / "live"), include_extract=True)
        return Path(path), at.isoformat()

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
            covers[caption] = {ALL} | {v for v, n in vals if v is not None and n == total}
    return all_values, covers


def _open(a) -> int:
    checks = _load_checks(a.checks)
    server, auth = _server()
    at = dt.datetime.now(dt.UTC)
    snapdir = new_snapshot_dir(checks["workbook"], at)
    with server.auth.sign_in(auth):
        session = Session(server, checks["review_project_luid"])
        print("swept:", session.sweep() or "nothing")
        live_at = server.workbooks.get_by_id(checks["workbook_luid"]).updated_at.isoformat()
        live = Path(server.workbooks.download(
            checks["workbook_luid"], filepath=str(snapdir / "live"), include_extract=True))
        extracts = unpack_extracts(live, snapdir / "extract")
        extracts = {ds: {**m, "file": f"extract/{m['file']}"} for ds, m in extracts.items()}
        twbx, hidden = build_review_twbx(live, snapdir, checks["dashboards"])
        wb = read_workbook((snapdir / "review.twb").read_text(encoding="utf-8", newline=""))
        name = f"{REVIEW_PREFIX}{at:%Y-%m-%d %H%M} {checks['workbook']}"
        copy = session.publish(twbx, name, hidden)
        print(f"published {name} ({copy}) to TEMP-CB")
        fields = {c.caption: {"field": c.field, "datasource": c.datasource}
                  for c in wb.filters if c.dashboard in checks["dashboards"]}
        m = Manifest(checks["workbook"], checks["workbook_luid"], copy, at.isoformat(),
                     live_at, extracts, fields, {})
        write_manifest(snapdir / "manifest.json", m)
        _export_all(session, m, snapdir, wb, checks, _states_for(checks, a.states))
    return 0


def _export_all(session, m, snapdir, wb, checks, states) -> None:
    all_values, covers = _value_maps(m, snapdir)
    dims_for = {s: list((v.get("dims") or {})) for s, v in (checks.get("sheets") or {}).items()}
    # Parents first, so the filter-took-effect check has something to compare with.
    for state in sorted(states, key=lambda s: (len(s.filters), s.id)):
        session.check_refresh(m.workbook_luid, m.live_updated_at)
        m.states[state.id] = export_state(session, m, snapdir, wb, state, all_values, covers, dims_for)
        write_manifest(snapdir / "manifest.json", m)
        print(f"  {state.id}: {m.states[state.id]['status']}")


def _export(a) -> int:
    checks = _load_checks(a.checks)
    snapdir = latest_snapshot(checks["workbook"])
    m = read_manifest(snapdir / "manifest.json")
    if m.closed:
        raise SessionError("this snapshot's session is closed; open a new one")
    server, auth = _server()
    with server.auth.sign_in(auth):
        session = Session(server, checks["review_project_luid"])
        session.copy = server.workbooks.get_by_id(m.copy_luid)
        wb = read_workbook((snapdir / "review.twb").read_text(encoding="utf-8", newline=""))
        _export_all(session, m, snapdir, wb, checks, _states_for(checks, a.states))
    return 0


def _close(a) -> int:
    checks = _load_checks(a.checks)
    snapdir = latest_snapshot(checks["workbook"])
    m = read_manifest(snapdir / "manifest.json")
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate_snapshot.py -q 2>&1 | tail -n 30`
Expected: 46 passed.

- [ ] **Step 5: Commit**

```bash
git add -u scripts/cube_validate_snapshot.py tests/scripts/test_cube_validate_snapshot.py
git commit -m "feat(cube): plan, open, export and close commands for review sessions

Refs #5856

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

## Part B: the Cube side (`scripts/cube_validate.py`)

### Task 9: port the proven v1 pieces

**Files:**

- Create: `scripts/cube_validate.py`
- Create: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Produces (copied verbatim from v1, `scripts/cube_validate.py` at
  `51f4f21e4a`):
  - `CUBE_LIMIT = 50_000` (v1 line 916)
  - `CubeError`, `ScopeError`, `_httpx_client`, `CubeClient` (v1 lines
    1819-1891);
    `CubeClient(url, secret, email, http=None, sleep=time.sleep, http_factory=None)`,
    `.load(query: dict) -> tuple[list[dict], list[str]]`
  - `DEFAULT_CUBE_URL`, `USER_EMAIL_CACHE`, `DEFAULT_OUT`, `BQ_PROJECT` (v1
    lines 1811-1816); `_user_email(given: str | None) -> str` (v1 lines
    3391-3398)
  - `_ISO_DATE`, `_WHOLE_FLOAT`, `norm_key(v) -> str`, `_num(v) -> float | None`
    (v1 lines 1599-1625)
  - `_filtered(sql: str, cond: str) -> str` (v1 lines 947-974)
  - `EXTRACT_TABLE`, `to_hyper_sql`, `_py_value`, `ExtractSource` (v1 lines
    1916, 1952-1991); `ExtractSource(path)` is a context manager and
    `__call__(sql) -> list[dict]`
  - `bigquery_rows`, `_CAPTION`, `live_table` (v1 lines 1893-1913)
  - `FIX_SIDES = ("cube", "dashboard", "source", "undecided")` (v1 line 920),
    `fix_sides(checks) -> dict[str, frozenset]` (v1 lines 1802-1808)
  - `CheckError(ValueError)` (v1 lines 924-926)
- Produces (new):
  - `norm_dim(v) -> str` (`norm_key` plus Tableau's `M/D/YYYY` dates and `1,234`
    integers)
  - `CubeClient.last_refresh: str | None` (the `lastRefreshTime` of the last
    `/load` answer: when the data behind it was last refreshed)
  - `table_modified(table: str, client=None) -> dt.datetime | None`

- [ ] **Step 1: Fetch the v1 branch and save the source**

```bash
cd /workspaces/teamster && git fetch origin cristinabaldor/feat/claude-cube-validate-skill
git show 51f4f21e4a:scripts/cube_validate.py > /tmp/v1_cube_validate.py
git show 51f4f21e4a:tests/scripts/test_cube_validate.py > /tmp/v1_test_cube_validate.py
grep -n "^class CubeClient\|^def _filtered\|^class ExtractSource" /tmp/v1_cube_validate.py
```

Expected: `CubeClient` at 1833, `_filtered` at 947, `ExtractSource` at 1967. If
the numbers differ, stop and report: the ranges below would be wrong.

- [ ] **Step 2: Write the failing tests**

Create `tests/scripts/test_cube_validate.py` with this header, then copy the v1
tests listed below it verbatim from `/tmp/v1_test_cube_validate.py`:

```python
"""Tests for scripts/cube_validate.py. No live calls."""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import sys
import threading
import time
from pathlib import Path

import pytest
import yaml

_SCRIPT = Path(__file__).parents[2] / "scripts" / "cube_validate.py"


def _load():
    spec = importlib.util.spec_from_file_location("cube_validate", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    # Registration before exec_module lets the module's dataclasses resolve.
    sys.modules["cube_validate"] = mod
    spec.loader.exec_module(mod)
    return mod


cv = _load()
SECRET = "x" * 32  # PyJWT warns on HS256 keys under 32 bytes
```

Copy verbatim (v1 test line ranges):

- `test_norm_key_` with its `@pytest.mark.parametrize` (216-236)
- `FakeResponse`, `FakeHttp` (524-539)
- `test_cube_client_polls_continue_wait_and_sends_raw_token`,
  `test_cube_client_row_limit_errors`, `test_cube_client_error_body_raises`
  (541-572)
- `test_py_value_converts_hyper_dates` (704-711)
- `StatusHttp`, `test_cube_client_backs_off_when_cube_is_overloaded`,
  `test_cube_client_gives_each_thread_its_own_http_client` (1872-1910)
- `test_filtered_handles_count_star_and_countif` (2664-2667)

Then add these new tests:

```python
def test_to_hyper_sql_names_the_extract_table():
    out = cv.to_hyper_sql(f"select count(distinct x) as n from `{cv.EXTRACT_TABLE}` where cast(y as string) = 'a'")
    assert '"Extract"."Extract"' in out and "TEXT" in out.upper()


@pytest.mark.parametrize(
    ("value", "expected"),
    [("9/15/2026", "2026-09-15"), ("1,234", "1234"), ("Newark", "Newark"), (None, "∅"), ("5", "5")],
)
def test_norm_dim_reads_tableau_formats(value, expected):
    assert cv.norm_dim(value) == expected


def test_fix_sides_groups_mismatches():
    sides = cv.fix_sides({"mismatches": {"a": {"fix": "cube"}, "b": {"fix": "dashboard"}}})
    assert sides["cube"] == {"a"} and sides["dashboard"] == {"b"} and sides["source"] == frozenset()


def test_cube_client_keeps_the_last_refresh_time():
    http = FakeHttp([{"data": [], "lastRefreshTime": "2026-10-09T10:00:00.000Z"}])
    client = cv.CubeClient("u", SECRET, "e", http=http, sleep=lambda _: None)
    assert client.last_refresh is None
    client.load({"measures": []})
    assert client.last_refresh == "2026-10-09T10:00:00.000Z"


def test_table_modified_reads_bigquery_metadata():
    from types import SimpleNamespace

    at = dt.datetime(2026, 10, 9, 10, tzinfo=dt.UTC)
    fake = SimpleNamespace(get_table=lambda t: SimpleNamespace(modified=at))
    assert cv.table_modified("p.d.t", client=fake) == at
```

- [ ] **Step 3: Run the tests to verify they fail**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate.py -q 2>&1 | tail -n 30`
Expected: FAIL, `FileNotFoundError` (the script does not exist yet).

- [ ] **Step 4: Write the implementation**

Create `scripts/cube_validate.py` with this header, then paste the v1 blocks
listed under **Interfaces** verbatim, in this order: constants, `CheckError`,
`FIX_SIDES`, `norm_key` block, `_filtered`, `fix_sides`, the Cube client block,
`bigquery_rows` and `live_table`, the extract block (`EXTRACT_TABLE` through
`ExtractSource`), `_user_email`.

Then make one change to the copied `CubeClient`: end `__init__` with
`self.last_refresh: str | None = None`, and in `load`, set
`self.last_refresh = body.get("lastRefreshTime")` on the line before
`rows = body.get("data", [])`. Cube's `/load` answer carries `lastRefreshTime`,
when the data behind it was last refreshed; `explain` compares it with the live
table's build time.

```python
"""The Cube side of Cube validation: compare, explain, report.

    uv run --with tableauhyperapi scripts/cube_validate.py compare <checks.yml>
    uv run --with tableauhyperapi scripts/cube_validate.py explain <checks.yml>
    uv run --with tableauhyperapi scripts/cube_validate.py drafts <checks.yml>

Reads the latest snapshot cube_validate_snapshot.py wrote. `compare` and
`explain` need CUBE_API_SECRET, which only the pytest secrets fixture provides,
so they run inside a throwaway tests/test_zz_*.py. `explain` also reads the live
`rpt_` tables in BigQuery through ADC.
Runbook: .claude/skills/cube-dashboard/SKILL.md.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import os
import re
import sys
import threading
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml
```

Then append the new function:

```python
_US_DATE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
_GROUPED_INT = re.compile(r"^-?\d{1,3}(,\d{3})+$")


def norm_dim(v) -> str:
    """norm_key, plus the date and number formats Tableau shows."""
    if isinstance(v, str):
        s = v.strip()
        if m := _US_DATE.match(s):
            return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
        if _GROUPED_INT.match(s):
            return s.replace(",", "")
    return norm_key(v)


def table_modified(table: str, client=None) -> dt.datetime | None:
    """When a BigQuery table last changed (UTC)."""
    if client is None:
        from google.cloud import bigquery

        client = bigquery.Client(project=BQ_PROJECT)
    return client.get_table(table).modified
```

- [ ] **Step 5: Run the tests to verify they pass**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate.py -q 2>&1 | tail -n 30`
Expected: all pass (10 from `test_norm_key_` parameters, 5 Cube client, 1
`_py_value`, 1 `_filtered`, 1 Hyper SQL, 5 `norm_dim`, 1 `fix_sides`, 1
`last_refresh`, 1 `table_modified`: 26 passed).

- [ ] **Step 6: Commit**

```bash
git add scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): port the Cube client and extract reader from v1

Refs #5856

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

### Task 10: load the checks file

**Files:**

- Modify: `scripts/cube_validate.py`
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Consumes: `CheckError`, `FIX_SIDES` (Task 9)
- Produces:
  - `Dim(cube: str | None, sql: str, person: bool | str = False)` (frozen)
  - `Measure(caption: str, cube: str | None, sql: str | None = None, num: str | None = None, den: str | None = None, scale: float = 1.0, round: int | None = None, table_calc: str | None = None, missing_members: list[str] = [], variants: list[dict] = [])`
  - `SheetMap(name: str, datasource: str, dims: dict[str, Dim], measures: dict[str, Measure])`
  - `TABLE_CALCS = {"percent_of_total", "running_sum"}`
  - `load_checks(path) -> dict`: the YAML with `sheets` as `{name: SheetMap}`
    and defaults filled for `mismatches`, `rows`, `filters`, `param_filters`,
    `cube_filters`, `extract_filters`

`round` says how many decimals the dashboard shows a value with when the export
carries no `%` sign. Without it, a plain number is compared as a raw value.

- [ ] **Step 1: Write the failing tests**

Append:

```python
DS = "rpt_demo (kipptaf_tableau)"
CHECKS = {
    "workbook": "Demo",
    "workbook_luid": "w1",
    "student_count": "demo.count_students",
    "scope": {"filter": "Region"},
    "filters": {"Region": {"cube": "demo.region"}},
    "rows": {"111": ["demo.avg_score"]},
    "sheets": {
        "Overview - Table": {
            "datasource": DS,
            "dims": {
                "Region": {"cube": "demo.region", "sql": "region"},
                "School Name": {"cube": "demo.school", "sql": "school"},
                "Student": {"cube": None, "sql": "student_name", "person": True},
            },
            "measures": {
                "Avg Score": {"cube": "demo.avg_score", "sql": "avg(score)", "round": 2},
                "% Complete": {
                    "cube": "demo.pct_complete",
                    "num": "count(distinct if(is_complete = 1, student_number, null))",
                    "den": "count(distinct student_number)",
                },
            },
        }
    },
    "mismatches": {},
}


def _write(tmp_path, d):
    p = tmp_path / "checks.yml"
    p.write_text(yaml.safe_dump(d, sort_keys=False))
    return p


def test_load_checks_builds_sheet_maps(tmp_path):
    c = cv.load_checks(_write(tmp_path, CHECKS))
    s = c["sheets"]["Overview - Table"]
    assert s.dims["School Name"] == cv.Dim("demo.school", "school")
    assert s.dims["Student"].person is True
    assert s.measures["Avg Score"].round == 2
    assert s.measures["% Complete"].num.startswith("count(distinct")
    assert c["cube_filters"] == [] and c["extract_filters"] == []


def test_load_checks_rejects_a_measure_without_sql(tmp_path):
    bad = json.loads(json.dumps(CHECKS))
    bad["sheets"]["Overview - Table"]["measures"]["Avg Score"].pop("sql")
    with pytest.raises(cv.CheckError, match="give sql, or num and den"):
        cv.load_checks(_write(tmp_path, bad))


def test_load_checks_checks_mismatches_and_variants(tmp_path):
    bad = json.loads(json.dumps(CHECKS))
    bad["mismatches"] = {"dup": {"title": "fix(cube): x", "what": "y", "fix": "nobody"}}
    with pytest.raises(cv.CheckError, match="fix must be one of"):
        cv.load_checks(_write(tmp_path, bad))
    bad["mismatches"]["dup"]["fix"] = "cube"
    bad["sheets"]["Overview - Table"]["measures"]["Avg Score"]["variants"] = [
        {"explains": ["other"], "sql": "avg(x)"}
    ]
    with pytest.raises(cv.CheckError, match="unknown other"):
        cv.load_checks(_write(tmp_path, bad))


def test_load_checks_rows_must_name_mapped_members(tmp_path):
    bad = json.loads(json.dumps(CHECKS))
    bad["rows"] = {"111": ["demo.nope"]}
    with pytest.raises(cv.CheckError, match="demo.nope"):
        cv.load_checks(_write(tmp_path, bad))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate.py -q -k "load_checks" 2>&1 | tail -n 30`
Expected: FAIL, `AttributeError: ... has no attribute 'load_checks'`.

- [ ] **Step 3: Write the implementation**

Append:

```python
TABLE_CALCS = {"percent_of_total", "running_sum"}


@dataclass(frozen=True)
class Dim:
    cube: str | None
    sql: str
    # Identifies a person: outputs show "a student", or this label, in place of values.
    person: bool | str = False


@dataclass
class Measure:
    caption: str
    cube: str | None
    sql: str | None = None
    num: str | None = None
    den: str | None = None
    scale: float = 1.0
    round: int | None = None
    table_calc: str | None = None
    missing_members: list[str] = field(default_factory=list)
    variants: list[dict] = field(default_factory=list)


@dataclass
class SheetMap:
    name: str
    datasource: str
    dims: dict[str, Dim]
    measures: dict[str, Measure]


def _measure(where: str, caption: str, m: dict, known: set[str]) -> Measure:
    if not m.get("sql") and not (m.get("num") and m.get("den")):
        raise CheckError(f"{where} / {caption}: give sql, or num and den")
    if m.get("table_calc") and m["table_calc"] not in TABLE_CALCS:
        raise CheckError(f"{where} / {caption}: table_calc must be one of {sorted(TABLE_CALCS)}")
    missing = list(m.get("missing_members") or [])
    for v in m.get("variants") or []:
        if not v.get("explains"):
            raise CheckError(f"{where} / {caption}: a variant needs explains")
        if not any(v.get(k) for k in ("sql", "num", "where", "cube_filters")):
            raise CheckError(
                f"{where} / {caption}: a variant needs sql, num and den, where, or cube_filters"
            )
        unknown = set(v["explains"]) - known - set(missing)
        if unknown:
            raise CheckError(f"{where} / {caption}: variant explains unknown {', '.join(sorted(unknown))}")
    return Measure(
        caption, m.get("cube"), m.get("sql"), m.get("num"), m.get("den"),
        float(m.get("scale", 1)), m.get("round"), m.get("table_calc"),
        missing, list(m.get("variants") or []),
    )


def load_checks(path) -> dict:
    raw = yaml.safe_load(Path(path).read_text()) or {}
    for key in ("workbook", "workbook_luid", "student_count", "sheets"):
        if key not in raw:
            raise CheckError(f"{path}: missing '{key}'")
    mismatches = raw.get("mismatches") or {}
    for name, m in mismatches.items():
        for k in ("title", "what", "fix"):
            if k not in m:
                raise CheckError(f"mismatch {name}: missing '{k}'")
        if m["fix"] not in FIX_SIDES:
            raise CheckError(f"mismatch {name}: fix must be one of {', '.join(FIX_SIDES)}")
        m.setdefault("labels", [])
        m.setdefault("related", [])
        m.setdefault("where", "tableau")
    sheets = {}
    for name, s in raw["sheets"].items():
        dims = {
            c: Dim(d.get("cube"), d.get("sql") or "", d.get("person", False))
            for c, d in (s.get("dims") or {}).items()
        }
        measures = {
            c: _measure(name, c, m, set(mismatches)) for c, m in (s.get("measures") or {}).items()
        }
        sheets[name] = SheetMap(name, s.get("datasource", ""), dims, measures)
    members = {m.cube for s in sheets.values() for m in s.measures.values() if m.cube}
    for gid, ms in (raw.get("rows") or {}).items():
        unknown = set(ms) - members
        if unknown:
            raise CheckError(f"row {gid}: {', '.join(sorted(unknown))} is not mapped on any sheet")
    return {
        **raw,
        "sheets": sheets,
        "mismatches": mismatches,
        "rows": raw.get("rows") or {},
        "filters": raw.get("filters") or {},
        "param_filters": raw.get("param_filters") or {},
        "cube_filters": raw.get("cube_filters") or [],
        "extract_filters": raw.get("extract_filters") or [],
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate.py -q 2>&1 | tail -n 30`
Expected: 30 passed.

- [ ] **Step 5: Commit**

```bash
git add -u scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): checks file with sheet mappings, mismatches and variants

Refs #5856

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

### Task 11: read exports and compare at the precision shown

**Files:**

- Modify: `scripts/cube_validate.py`
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Produces:
  - `Export(columns: list[str], rows: list[dict[str, str]])`
  - `read_export(data: bytes) -> Export` (a repeated header becomes `Name (2)`)
  - `Shown(value: float, decimals: int | None)` (frozen; `decimals` is `None`
    for a raw value)
  - `parse_shown(s: str | None, round_to: int | None = None) -> Shown | None`
  - `matches_shown(cube: float | None, shown: Shown | None) -> bool`
  - `matches_raw(a: float | None, b: float | None) -> bool`

Rules: a value with `%` or thousands separators is formatted, so it matches
within half a unit of its last shown digit. A plain number is raw and matches
within 1e-6 relative, unless the measure gives `round`. "", "All", "*" and text
do not parse.

- [ ] **Step 1: Write the failing tests**

Append:

```python
def test_read_export_keeps_repeated_columns():
    e = cv.read_export(b"\xef\xbb\xbfGrade Level,Schoolid,Schoolid,Mastery\r\n5,A,B,0.5\r\n")
    assert e.columns == ["Grade Level", "Schoolid", "Schoolid (2)", "Mastery"]
    assert e.rows == [{"Grade Level": "5", "Schoolid": "A", "Schoolid (2)": "B", "Mastery": "0.5"}]


def test_read_export_of_nothing_is_empty():
    assert cv.read_export(b"") == cv.Export([], [])
    assert cv.read_export(b"A,B\r\n") == cv.Export(["A", "B"], [])


@pytest.mark.parametrize(
    ("text", "round_to", "value", "decimals"),
    [
        ("36.24%", None, 0.3624, 4),
        ("100%", None, 1.0, 2),
        ("1,234", None, 1234.0, 0),
        ("0.362381", None, 0.362381, None),
        ("36.24", 2, 36.24, 2),
        ("-1.5", None, -1.5, None),
    ],
)
def test_parse_shown(text, round_to, value, decimals):
    s = cv.parse_shown(text, round_to)
    assert s.value == pytest.approx(value) and s.decimals == decimals


@pytest.mark.parametrize("text", ["", "All", "*", "Newark", None])
def test_parse_shown_rejects_non_numbers(text):
    assert cv.parse_shown(text) is None


def test_matches_shown_uses_the_shown_precision():
    assert cv.matches_shown(0.362381, cv.parse_shown("36.24%"))
    assert not cv.matches_shown(0.3630, cv.parse_shown("36.24%"))
    # A raw "1" means exactly 1, never "anything that rounds to 1".
    assert not cv.matches_shown(0.6, cv.parse_shown("1"))
    assert cv.matches_shown(1.0000000001, cv.parse_shown("1"))
    assert cv.matches_shown(None, None) and not cv.matches_shown(None, cv.parse_shown("1"))


def test_matches_raw():
    assert cv.matches_raw(0.8, 0.8000000001) and not cv.matches_raw(0.8, 0.81)
    assert cv.matches_raw(None, None) and not cv.matches_raw(None, 0.0)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate.py -q -k "export or shown or raw" 2>&1 | tail -n 30`
Expected: FAIL, `AttributeError: ... has no attribute 'read_export'`.

- [ ] **Step 3: Write the implementation**

Append:

```python
@dataclass
class Export:
    columns: list[str]
    rows: list[dict[str, str]]


def read_export(data: bytes) -> Export:
    rows = list(csv.reader(io.StringIO(data.decode("utf-8-sig"))))
    if not rows:
        return Export([], [])
    seen: dict[str, int] = {}
    cols = []
    for c in rows[0]:
        seen[c] = seen.get(c, 0) + 1
        cols.append(c if seen[c] == 1 else f"{c} ({seen[c]})")
    return Export(cols, [dict(zip(cols, r, strict=False)) for r in rows[1:] if r])


@dataclass(frozen=True)
class Shown:
    value: float
    decimals: int | None  # None: a raw value, compared almost exactly


_SHOWN = re.compile(r"^(-?)(\d{1,3}(?:,\d{3})+|\d*)(?:\.(\d+))?(%?)$")


def parse_shown(s: str | None, round_to: int | None = None) -> Shown | None:
    t = (s or "").strip()
    m = _SHOWN.match(t)
    if not t or not m or not (m.group(2) or m.group(3)):
        return None
    sign, whole, frac, pct = m.group(1), m.group(2), m.group(3) or "", m.group(4)
    value = float(f"{sign}{whole.replace(',', '') or '0'}.{frac or '0'}")
    if pct:
        return Shown(value / 100, len(frac) + 2)
    if "," in whole:
        return Shown(value, len(frac))
    return Shown(value, round_to)


def matches_shown(cube: float | None, shown: Shown | None) -> bool:
    if cube is None or shown is None:
        return cube is None and shown is None
    if shown.decimals is None:
        return abs(cube - shown.value) <= 1e-6 * max(1.0, abs(cube))
    return abs(cube - shown.value) <= 0.5 * 10 ** -shown.decimals + 1e-9 * max(1.0, abs(cube))


def matches_raw(a: float | None, b: float | None) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= 1e-6 * max(1.0, abs(a), abs(b))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate.py -q 2>&1 | tail -n 30`
Expected: 45 passed.

- [ ] **Step 5: Commit**

```bash
git add -u scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): read Tableau exports and compare at the precision shown

Refs #5856

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

### Task 12: Cube filters for a state, and the scope guard

**Files:**

- Modify: `scripts/cube_validate.py`
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Consumes: `load_checks` output (Task 10), `norm_dim`, `_num`, `CUBE_LIMIT`,
  `ScopeError` (Task 9)
- Produces:
  - `ALL = "(All)"`, `BLANK = "(Blank)"`, `TOTAL = "All"`, `MULTI = "*"`
  - `state_filters(entry: dict, checks: dict) -> tuple[list[dict], list[str]]`
    (Cube filters for a manifest state entry, and the captions that have no Cube
    member)
  - `hard_filters(checks: dict, datasource: str) -> list[dict]`
  - `scope_guard(load, checks: dict, extract_counts: dict[str, int]) -> None`

A caption resolves through `checks["filters"]` first, then any sheet dimension
with that caption. Parameters resolve through
`checks["param_filters"] [caption][value]`; a parameter with no entry adds no
Cube filter.

- [ ] **Step 1: Write the failing tests**

Append:

```python
def _checks(tmp_path, **extra):
    d = json.loads(json.dumps(CHECKS))
    d.update(extra)
    return cv.load_checks(_write(tmp_path, d))


def test_state_filters_translate_captions_all_and_blank(tmp_path):
    c = _checks(tmp_path)
    entry = {"state": {"dashboard": "Overview", "filters": {"Region": "North", "School Name": cv.ALL}},
             "click_filters": {"School Name": "Alpha"}}
    filters, missing = cv.state_filters(entry, c)
    assert filters == [
        {"member": "demo.region", "operator": "equals", "values": ["North"]},
        {"member": "demo.school", "operator": "equals", "values": ["Alpha"]},
    ]
    assert missing == []
    blank = {"state": {"dashboard": "Overview", "filters": {"Region": cv.BLANK}}}
    assert cv.state_filters(blank, c)[0] == [{"member": "demo.region", "operator": "notSet"}]


def test_state_filters_report_captions_with_no_member(tmp_path):
    c = _checks(tmp_path)
    entry = {"state": {"dashboard": "Overview", "filters": {"Grade Level": "5"}}}
    assert cv.state_filters(entry, c) == ([], ["Grade Level"])


def test_parameters_add_filters_only_when_mapped(tmp_path):
    pf = {"Subject": {"Math": [{"member": "demo.subject", "operator": "equals", "values": ["Math"]}]}}
    c = _checks(tmp_path, param_filters=pf)
    entry = {"state": {"dashboard": "Overview", "params": {"Subject": "Math", "Group By": "Teacher"}}}
    assert cv.state_filters(entry, c)[0] == pf["Subject"]["Math"]


def test_hard_filters_apply_per_datasource(tmp_path):
    c = _checks(tmp_path, cube_filters=[
        {"member": "demo.is_test", "operator": "equals", "values": ["false"]},
        {"member": "demo.other", "operator": "set", "datasource": "elsewhere"},
    ])
    assert cv.hard_filters(c, DS) == [{"member": "demo.is_test", "operator": "equals", "values": ["false"]}]


def test_scope_guard_stops_when_cube_misses_a_region(tmp_path):
    c = _checks(tmp_path)
    load = lambda q: ([{"demo.region": "North", "demo.count_students": "40"}], [])  # noqa: E731
    cv.scope_guard(load, c, {"North": 40, "South": 0})
    with pytest.raises(cv.ScopeError, match="South"):
        cv.scope_guard(load, c, {"North": 40, "South": 12})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate.py -q -k "state_filters or parameters_add or hard_filters or scope_guard" 2>&1 | tail -n 30`
Expected: FAIL, `AttributeError: ... has no attribute 'ALL'`.

- [ ] **Step 3: Write the implementation**

Append:

```python
ALL = "(All)"
BLANK = "(Blank)"
TOTAL = "All"  # a total row in a Tableau export
MULTI = "*"  # a mark that covers several values


def _caption_members(checks: dict) -> dict[str, str]:
    out = {c: d.cube for s in checks["sheets"].values() for c, d in s.dims.items() if d.cube}
    out.update({c: f["cube"] for c, f in checks["filters"].items() if f.get("cube")})
    return out


def state_filters(entry: dict, checks: dict) -> tuple[list[dict], list[str]]:
    st = entry["state"]
    members = _caption_members(checks)
    pairs = list((st.get("filters") or {}).items()) + list((entry.get("click_filters") or {}).items())
    out, missing = [], []
    for caption, value in pairs:
        member = members.get(caption)
        if member is None:
            missing.append(caption)
        elif value == BLANK:
            out.append({"member": member, "operator": "notSet"})
        elif value != ALL:
            out.append({"member": member, "operator": "equals", "values": [str(value)]})
    for caption, value in (st.get("params") or {}).items():
        out += checks["param_filters"].get(caption, {}).get(value, [])
    return out, missing


def hard_filters(checks: dict, datasource: str) -> list[dict]:
    return [
        {k: v for k, v in f.items() if k != "datasource"}
        for f in checks["cube_filters"]
        if f.get("datasource") in (None, datasource)
    ]


def scope_guard(load, checks: dict, extract_counts: dict[str, int]) -> None:
    """Stop when Cube shows no students for a scope value the dashboard has."""
    caption = checks["scope"]["filter"]
    member = _caption_members(checks)[caption]
    rows, _ = load({"measures": [checks["student_count"]], "dimensions": [member], "limit": CUBE_LIMIT})
    cube = {norm_dim(r.get(member)): _num(r.get(checks["student_count"])) or 0 for r in rows}
    short = sorted(v for v, n in extract_counts.items() if n > 0 and not cube.get(norm_dim(v)))
    if short:
        raise ScopeError(
            f"Cube shows no students for {caption} {', '.join(short)}, which the dashboard "
            "has: this Cube identity sees less than the dashboard does"
        )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate.py -q 2>&1 | tail -n 30`
Expected: 50 passed.

- [ ] **Step 5: Commit**

```bash
git add -u scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): translate dashboard states into Cube filters; scope guard

Refs #5856

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

### Task 13: compare one export with Cube

**Files:**

- Modify: `scripts/cube_validate.py`
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Consumes: `SheetMap`, `Measure` (Task 10), `Export`, `parse_shown`,
  `matches_shown` (Task 11), `hard_filters`, `TOTAL`, `MULTI` (Task 12)
- Produces:
  - `Cell` dataclass: `sheet: str`, `state: str`, `key: dict[str, str]`,
    `measure: str`, `shown: str | None`, `tableau: float | None`,
    `cube: float | None`, `n_students: int | None`, `status: str` (`match`,
    `mismatch`, `not_comparable`, `missing_member`), `reason: str = ""`,
    `rollups: list[str] = []`, `verdict: str | None = None`,
    `explained_by: list[str] = []`, `extract: float | None = None`,
    `variant: float | None = None`, `cube_variant: float | None = None`
  - `apply_calc(meas: Measure, raw: dict[tuple, float | None], scale: float) -> dict[tuple, float | None]`
  - `compare_export(sheet: SheetMap, state_id: str, export: Export, load, filters: list[dict], missing: list[str], checks: dict) -> list[Cell]`
  - `write_cells(path: Path, cells: list[Cell])`,
    `read_cells(path: Path) -> list[Cell]` (JSON lines)

Per export: rows containing `*` are not comparable. Rows are grouped by which
dimensions read `All`; each group is one Cube query at the remaining dimensions.
A Tableau row without a Cube row, or a Cube row (with any non-zero measure)
without a Tableau row, is a mismatch. An export with no header uses every mapped
dimension as its grain, so Cube's rows still show up.

- [ ] **Step 1: Write the failing tests**

Append:

```python
def _sheet(tmp_path, **measure_extra):
    d = json.loads(json.dumps(CHECKS))
    d["sheets"]["Overview - Table"]["measures"]["Avg Score"].update(measure_extra)
    c = cv.load_checks(_write(tmp_path, d))
    return c, c["sheets"]["Overview - Table"]


class FakeCube:
    """Answers each query from rows keyed by the school, or the total."""

    def __init__(self, by_school, total):
        self.by_school, self.total, self.queries = by_school, total, []

    def __call__(self, q):
        self.queries.append(q)
        if "demo.school" in q["dimensions"]:
            return [{"demo.school": k, **v} for k, v in self.by_school.items()], ["rollup_a"]
        return [dict(self.total)], []


def _row(avg, n=20):
    return {"demo.avg_score": str(avg), "demo.count_students": str(n), "demo.pct_complete": "0.8"}


def test_compare_matches_rows_and_totals(tmp_path):
    c, sheet = _sheet(tmp_path)
    export = cv.read_export(b"School Name,Avg Score\r\nAlpha,48.50\r\nBeta,50.00\r\nAll,49.25\r\n")
    cube = FakeCube({"Alpha": _row(48.5), "Beta": _row(50)}, _row(49.25, 40))
    cells = cv.compare_export(sheet, "s1", export, cube, [], [], c)
    assert [(x.key, x.status) for x in cells] == [
        ({"School Name": "Alpha"}, "match"),
        ({"School Name": "Beta"}, "match"),
        ({"School Name": "All"}, "match"),
    ]
    assert len(cube.queries) == 2 and cube.queries[1]["dimensions"] == []
    assert cells[0].n_students == 20 and cells[0].rollups == ["rollup_a"]


def test_compare_flags_value_gaps_and_one_sided_slices(tmp_path):
    c, sheet = _sheet(tmp_path)
    export = cv.read_export(b"School Name,Avg Score\r\nAlpha,48.50\r\nGamma,30.00\r\n")
    cube = FakeCube({"Alpha": _row(47.0), "Beta": _row(50)}, _row(0))
    cells = {x.key["School Name"]: x for x in cv.compare_export(sheet, "s1", export, cube, [], [], c)}
    assert cells["Alpha"].status == "mismatch" and cells["Alpha"].cube == 47.0
    assert cells["Gamma"].reason == "Tableau shows this slice; Cube does not"
    assert cells["Beta"].reason == "Cube has this slice; Tableau does not"
    assert cells["Beta"].tableau is None


def test_multi_value_marks_and_unmapped_columns_are_not_comparable(tmp_path):
    c, sheet = _sheet(tmp_path)
    export = cv.read_export(b"School Name,Avg Score,Mystery\r\n*,48.50,1\r\n")
    cells = cv.compare_export(sheet, "s1", export, FakeCube({}, _row(0)), [], [], c)
    reasons = sorted(x.reason for x in cells if x.status == "not_comparable")
    assert reasons == ["multi-value mark", "unmapped column"]


def test_a_filter_with_no_member_blocks_the_state(tmp_path):
    c, sheet = _sheet(tmp_path)
    export = cv.read_export(b"School Name,Avg Score\r\nAlpha,48.50\r\n")
    cells = cv.compare_export(sheet, "s1", export, FakeCube({}, _row(0)), [], ["Grade Level"], c)
    assert cells[0].status == "not_comparable" and "Grade Level" in cells[0].reason


def test_a_dimension_with_no_member_is_a_missing_member(tmp_path):
    c, sheet = _sheet(tmp_path)
    export = cv.read_export(b"Student,Avg Score\r\nsomeone,48.50\r\n")
    cells = cv.compare_export(sheet, "s1", export, FakeCube({}, _row(0)), [], [], c)
    assert cells[0].status == "missing_member" and "Student" in cells[0].reason


def test_an_empty_export_still_shows_cubes_rows(tmp_path):
    c, sheet = _sheet(tmp_path)
    for data in (b"", b"School Name,Avg Score\r\n"):
        cells = cv.compare_export(sheet, "s1", cv.read_export(data), FakeCube({"Alpha": _row(48.5)}, _row(0)), [], [], c)
        assert any(x.reason == "Cube has this slice; Tableau does not" for x in cells)


def test_percent_of_total_is_rebuilt_from_cubes_rows(tmp_path):
    c, sheet = _sheet(tmp_path, table_calc="percent_of_total", round=None)
    export = cv.read_export(b"School Name,Avg Score\r\nAlpha,25%\r\nBeta,75%\r\n")
    cube = FakeCube({"Alpha": _row(10), "Beta": _row(30)}, _row(0))
    cells = cv.compare_export(sheet, "s1", export, cube, [], [], c)
    assert [x.status for x in cells] == ["match", "match"]


def test_cells_round_trip(tmp_path):
    cell = cv.Cell("S", "s1", {"A": "x"}, "M", "1", 1.0, 1.0, 20, "match")
    cv.write_cells(tmp_path / "cells.jsonl", [cell])
    assert cv.read_cells(tmp_path / "cells.jsonl") == [cell]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate.py -q -k "compare or not_comparable or blocks_the_state or missing_member or empty_export or percent_of_total or round_trip" 2>&1 | tail -n 30`
Expected: FAIL, `AttributeError: ... has no attribute 'compare_export'`.

- [ ] **Step 3: Write the implementation**

Append:

```python
@dataclass
class Cell:
    sheet: str
    state: str
    key: dict[str, str]
    measure: str
    shown: str | None
    tableau: float | None
    cube: float | None
    n_students: int | None
    status: str
    reason: str = ""
    rollups: list[str] = field(default_factory=list)
    verdict: str | None = None
    explained_by: list[str] = field(default_factory=list)
    extract: float | None = None
    variant: float | None = None
    cube_variant: float | None = None


def _int(v) -> int | None:
    n = _num(v)
    return None if n is None else int(n)


def apply_calc(meas: Measure, raw: dict, scale: float) -> dict:
    """Values as the sheet shows them: scaled, or rebuilt as its table calculation."""
    if meas.table_calc == "percent_of_total":
        total = sum(v for v in raw.values() if v is not None)
        return {k: (v / total if v is not None and total else None) for k, v in raw.items()}
    if meas.table_calc == "running_sum":
        out, run = {}, 0.0
        for k in sorted(raw):
            run += raw[k] or 0.0
            out[k] = run * scale
        return out
    return {k: (None if v is None else v * scale) for k, v in raw.items()}


def compare_export(sheet, state_id, export, load, filters, missing, checks) -> list[Cell]:
    def cell(key, m, shown=None, tableau=None, cube=None, n=None, status="mismatch", reason="", rollups=()):
        return Cell(sheet.name, state_id, key, m, shown, tableau, cube, n, status, reason, list(rollups))

    cols = export.columns
    # No header at all: compare at every mapped dimension Cube has, so its rows still show.
    dims = [c for c in cols if c in sheet.dims] if cols else [d for d in sheet.dims if sheet.dims[d].cube]
    measures = [c for c in cols if c in sheet.measures] if cols else list(sheet.measures)
    cells = [cell({}, c, status="not_comparable", reason="unmapped column")
             for c in cols if c not in sheet.dims and c not in sheet.measures]
    if missing:
        reason = f"filter {', '.join(missing)} has no Cube member"
        return cells + [cell({}, m, status="not_comparable", reason=reason) for m in measures]

    groups: dict[tuple[str, ...], list[dict]] = {}
    for r in export.rows:
        if any(r.get(d) == MULTI for d in dims):
            key = {d: r.get(d, "") for d in dims}
            cells += [cell(key, m, r.get(m), status="not_comparable", reason="multi-value mark") for m in measures]
            continue
        groups.setdefault(tuple(d for d in dims if r.get(d) == TOTAL), []).append(r)
    if not groups:
        groups[()] = []

    student = checks["student_count"]
    for totals, rows in groups.items():
        grain = [d for d in dims if d not in totals]
        blocked = [d for d in grain if sheet.dims[d].cube is None]
        no_member = [m for m in measures if sheet.measures[m].cube is None]
        if blocked:
            reason = f"dimension {', '.join(blocked)} has no Cube member"
            for r in rows:
                key = {d: r.get(d, "") for d in dims}
                cells += [cell(key, m, r.get(m), status="missing_member", reason=reason) for m in measures]
            continue
        members = sorted({sheet.measures[m].cube for m in measures if sheet.measures[m].cube} | {student})
        q = {
            "measures": members,
            "dimensions": [sheet.dims[d].cube for d in grain],
            "filters": filters + hard_filters(checks, sheet.datasource),
            "limit": CUBE_LIMIT,
        }
        cube_rows, rollups = load(q)
        by_key = {tuple(norm_dim(cr.get(sheet.dims[d].cube)) for d in grain): cr for cr in cube_rows}
        values = {
            m: apply_calc(
                sheet.measures[m],
                {k: _num(cr.get(sheet.measures[m].cube)) for k, cr in by_key.items()},
                sheet.measures[m].scale,
            )
            for m in measures
            if m not in no_member
        }
        fixed = {d: TOTAL for d in totals}
        seen = set()
        for r in rows:
            k = tuple(norm_dim(r.get(d)) for d in grain)
            seen.add(k)
            cr = by_key.get(k)
            key = {**{d: r.get(d, "") for d in grain}, **fixed}
            n = _int(cr.get(student)) if cr else None
            for m in measures:
                meas, text = sheet.measures[m], r.get(m)
                shown = parse_shown(text, meas.round)
                if m in no_member:
                    cells.append(cell(key, m, text, status="missing_member", reason="measure has no Cube member"))
                elif shown is None and (text or "").strip():
                    cells.append(cell(key, m, text, status="not_comparable", reason="value does not parse"))
                elif cr is None:
                    cells.append(cell(key, m, text, shown and shown.value, None, None, "mismatch",
                                      "Tableau shows this slice; Cube does not", rollups))
                else:
                    v = values[m].get(k)
                    ok = matches_shown(v, shown)
                    cells.append(cell(key, m, text, shown and shown.value, v, n,
                                      "match" if ok else "mismatch", "", rollups))
        for k, cr in by_key.items():
            if k in seen:
                continue
            vals = {m: values[m].get(k) for m in values}
            if all(v in (None, 0) for v in vals.values()):
                continue
            key = {**dict(zip(grain, k, strict=True)), **fixed}
            for m, v in vals.items():
                cells.append(cell(key, m, None, None, v, _int(cr.get(student)), "mismatch",
                                  "Cube has this slice; Tableau does not", rollups))
    return cells


def write_cells(path: Path, cells: list[Cell]) -> None:
    Path(path).write_text("".join(json.dumps(asdict(c)) + "\n" for c in cells))


def read_cells(path: Path) -> list[Cell]:
    p = Path(path)
    if not p.exists():
        return []
    return [Cell(**json.loads(line)) for line in p.read_text().splitlines() if line]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate.py -q 2>&1 | tail -n 30`
Expected: 58 passed.

- [ ] **Step 5: Commit**

```bash
git add -u scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): compare each Tableau export with Cube at the export's grain

Refs #5856

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

### Task 14: choose the next descent level

**Files:**

- Modify: `scripts/cube_validate.py`
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Consumes: `Cell` (Task 13); manifest `states` and `fields` (Task 6 shape)
- Produces:
  - `SMALL_CELL = 10`
  - `state_status(cells: list[Cell]) -> dict[str, str]` (`mismatch` or `match`
    per state id)
  - `next_states(states: dict[str, dict], status: dict[str, str], trees: dict[str, dict[str, list[str]]], cross_cuts: dict[str, list[str]], fields: dict[str, dict], children) -> list[dict]`
    (`children(datasource, where: list[tuple[str, str]], field) -> list[tuple[str | None, int]]`;
    returns state dicts with `dashboard` and `filters`, the shape
    `State.from_dict` reads)
  - `child_values_sql(where: list[tuple[str, str]], field: str, student: str = "student_number") -> str`

Rules, from the spec's descent:

- Only states whose filters walk one tree from its root (no parameters, no
  click) descend.
- A mismatching node gets every child with at least `SMALL_CELL` students; a
  matching node gets its largest and smallest such child.
- A mismatching node whose exported children all matched, or that sits at the
  tree's last level, is split once by every cross-cut value.
- States already in the manifest are never proposed again.

- [ ] **Step 1: Write the failing tests**

Append:

```python
TREES = {DS: {"region": ["region", "school", "grade_level"]}}
CROSS = {DS: ["iep_status"]}
FIELDS = {
    "Region": {"field": "region", "datasource": DS},
    "School Name": {"field": "school", "datasource": DS},
    "Grade Level": {"field": "grade_level", "datasource": DS},
    "IEP": {"field": "iep_status", "datasource": DS},
}
KIDS = {
    "school": [("Alpha", 30), ("Beta", 20), ("Gamma", 12), ("Tiny", 4)],
    "grade_level": [("5", 15), ("6", 15)],
    "iep_status": [("No IEP", 25), ("Has IEP", 5)],
}


def _entry(filters, status="ok"):
    return {"state": {"dashboard": "Overview", "filters": filters}, "status": status, "sheets": {}}


def children(ds, where, f):
    return KIDS[f]


def test_a_matching_node_samples_its_largest_and_smallest_children():
    states = {"n": _entry({"Region": "North"})}
    out = cv.next_states(states, {"n": "match"}, TREES, CROSS, FIELDS, children)
    assert [s["filters"]["School Name"] for s in out] == ["Alpha", "Gamma"]


def test_a_mismatching_node_gets_every_child_above_the_small_cell_size():
    states = {"n": _entry({"Region": "North"})}
    out = cv.next_states(states, {"n": "mismatch"}, TREES, CROSS, FIELDS, children)
    assert [s["filters"]["School Name"] for s in out] == ["Alpha", "Beta", "Gamma"]


def test_a_narrowed_gap_is_split_by_each_cross_cut():
    states = {
        "n": _entry({"Region": "North"}),
        "a": _entry({"Region": "North", "School Name": "Alpha"}),
        "b": _entry({"Region": "North", "School Name": "Beta"}),
    }
    out = cv.next_states(states, {"n": "mismatch", "a": "match", "b": "match"}, TREES, CROSS, FIELDS, children)
    iep = [s for s in out if "IEP" in s["filters"] and s["filters"].get("School Name") is None]
    assert [s["filters"]["IEP"] for s in iep] == ["No IEP"]  # "Has IEP" has 5 students


def test_states_already_exported_are_not_proposed_again():
    states = {"n": _entry({"Region": "North"}), "a": _entry({"Region": "North", "School Name": "Alpha"}),
              "g": _entry({"Region": "North", "School Name": "Gamma"})}
    out = cv.next_states(states, {"n": "match", "a": "match", "g": "match"}, TREES, CROSS, FIELDS, children)
    assert all(s["filters"].get("School Name") not in ("Alpha", "Gamma") or "Grade Level" in s["filters"] for s in out)


def test_non_tree_states_and_failed_exports_do_not_descend():
    states = {"p": {"state": {"dashboard": "Overview", "params": {"Group By": "Teacher"}}, "status": "ok", "sheets": {}},
              "x": _entry({"Region": "North"}, status="filter_ignored")}
    assert cv.next_states(states, {"p": "mismatch", "x": "mismatch"}, TREES, CROSS, FIELDS, children) == []


def test_state_status():
    cells = [cv.Cell("S", "a", {}, "M", "1", 1, 1, 20, "match"), cv.Cell("S", "a", {}, "M", "1", 1, 2, 20, "mismatch"),
             cv.Cell("S", "b", {}, "M", "1", 1, 1, 20, "match")]
    assert cv.state_status(cells) == {"a": "mismatch", "b": "match"}


def test_child_values_sql_filters_and_groups():
    sql = cv.child_values_sql([("region", "North"), ("iep_status", cv.BLANK)], "school")
    assert "cast(region as string) = 'North'" in sql and "iep_status is null" in sql
    assert sql.rstrip().endswith("group by 1")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate.py -q -k "node or narrowed or already_exported or descend or state_status or child_values" 2>&1 | tail -n 30`
Expected: FAIL, `AttributeError: ... has no attribute 'next_states'`.

- [ ] **Step 3: Write the implementation**

Append:

```python
SMALL_CELL = 10


def state_status(cells: list[Cell]) -> dict[str, str]:
    out: dict[str, str] = {}
    for c in cells:
        if c.status == "mismatch":
            out[c.state] = "mismatch"
        else:
            out.setdefault(c.state, "match")
    return out


def _sql_lit(v) -> str:
    return "'" + str(v).replace("\\", "\\\\").replace("'", "\\'") + "'"


def _cond(field_sql: str, value) -> str | None:
    if value == ALL:
        return None
    if value == BLANK:
        return f"{field_sql} is null"
    return f"cast({field_sql} as string) = {_sql_lit(value)}"


def child_values_sql(where, field, student="student_number") -> str:
    conds = [c for f, v in where if (c := _cond(f, v))]
    cond = " and ".join(conds) or "true"
    return (
        f"select cast({field} as string) as v, count(distinct {student}) as n "
        f"from `{EXTRACT_TABLE}` where {cond} group by 1"
    )


def _sig(st: dict) -> tuple:
    return (
        st["dashboard"],
        tuple(sorted((st.get("filters") or {}).items())),
        tuple(sorted((st.get("params") or {}).items())),
        tuple(sorted((st.get("click") or {}).items())),
    )


def _is_child(k: dict, st: dict) -> bool:
    kf, sf = k.get("filters") or {}, st.get("filters") or {}
    return (
        k["dashboard"] == st["dashboard"]
        and not k.get("params")
        and not k.get("click")
        and len(kf) == len(sf) + 1
        and all(kf.get(c) == v for c, v in sf.items())
    )


def _tree_path(st, trees, fields):
    if st.get("params") or st.get("click") or not st.get("filters"):
        return None
    caps = list(st["filters"])
    if any(c not in fields for c in caps):
        return None
    ds = fields[caps[0]]["datasource"]
    fs = [fields[c]["field"] for c in caps]
    for levels in (trees.get(ds) or {}).values():
        if levels[: len(fs)] == fs:
            return ds, levels
    return None


def _ends_pair(kids):
    if not kids:
        return []
    big = max(kids, key=lambda x: x[1])
    small = min(kids, key=lambda x: x[1])
    return [big] if big == small else [big, small]


def next_states(states, status, trees, cross_cuts, fields, children) -> list[dict]:
    caption_of = {(f["datasource"], f["field"]): c for c, f in fields.items()}
    have = {_sig(e["state"]) for e in states.values()}
    out: list[dict] = []

    def add(st):
        if _sig(st) not in have:
            have.add(_sig(st))
            out.append(st)

    for sid, e in sorted(states.items()):
        st = e["state"]
        path = _tree_path(st, trees, fields)
        if e.get("status") != "ok" or path is None:
            continue
        ds, levels = path
        where = [(fields[c]["field"], v) for c, v in st["filters"].items()]
        bad = status.get(sid) == "mismatch"
        depth = len(st["filters"])
        kids_done = [s for s, k in states.items() if _is_child(k["state"], st)]
        if bad and (depth == len(levels) or (kids_done and all(status.get(s) != "mismatch" for s in kids_done))):
            for cut in cross_cuts.get(ds, []):
                cap = caption_of.get((ds, cut))
                for v, n in children(ds, where, cut) if cap else []:
                    if v is not None and n >= SMALL_CELL:
                        add({"dashboard": st["dashboard"], "filters": {**st["filters"], cap: v}})
        if kids_done or depth >= len(levels):
            continue
        cap = caption_of.get((ds, levels[depth]))
        if not cap:
            continue
        kids = [(v, n) for v, n in children(ds, where, levels[depth]) if v is not None and n >= SMALL_CELL]
        for v, _ in kids if bad else _ends_pair(kids):
            add({"dashboard": st["dashboard"], "filters": {**st["filters"], cap: v}})
    return out
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate.py -q 2>&1 | tail -n 30`
Expected: 65 passed.

- [ ] **Step 5: Commit**

```bash
git add -u scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): pick the next descent level from mismatches and samples

Refs #5856

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

### Task 15: explain gaps with the extract (trust gate, timing, variants)

**Files:**

- Modify: `scripts/cube_validate.py`
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Consumes: `Cell`, `apply_calc` (Task 13), `state_filters`, `hard_filters`
  (Task 12), `parse_shown`, `matches_shown`, `matches_raw` (Task 11),
  `_filtered`, `fix_sides`, `table_modified` (Tasks 9-10), `_cond` (Task 14)
- Produces:
  - `state_where(entry: dict, checks: dict, fields: dict, sheet: SheetMap, public_only: bool = False) -> list[str]`
  - `extract_sql(sheet: SheetMap, meas: Measure, grain: list[str], where: list[str]) -> str`
  - `extract_values(rows: list[dict], n_grain: int) -> dict[tuple, float | None]`
  - `cell_verdict(c: Cell, sides: dict[str, frozenset], meas: Measure) -> str`
  - `Live(rows, modified, cube_refreshed)`: 3 callables.
    `rows(datasource, sql) -> list[dict]` runs extract SQL on the live `rpt_`
    table; `modified(datasource) -> dt.datetime | None` is when that table last
    changed; `cube_refreshed(query) -> dt.datetime | None` is Cube's
    `lastRefreshTime` for a query
  - `explain_cells(cells: list[Cell], checks: dict, states: dict[str, dict], fields: dict, run_extract, load, live: Live | None = None) -> None`
    (`run_extract(datasource, sql) -> list[dict]`; sets `verdict`, `reason`,
    `extract`, `explained_by`, `variant`, `cube_variant` on each cell)

Order of judgement for a mismatched cell:

1. The measure failed the trust gate: `incomplete`, "extract SQL does not
   reproduce Tableau for this measure".
2. The extract SQL does not reproduce this cell: `incomplete`, "extract SQL does
   not reproduce this cell".
3. With `live` given, the same SQL on the live `rpt_` table equals Cube: `pass`,
   "timing: the extract is older than Cube; Cube matches the live table".
4. The first variant whose dashboard side equals its Cube side explains the
   cell; `cell_verdict` turns its `explains` into a verdict.
5. Nothing explains it: `incomplete` when Cube's data is older than the live
   table ("re-run explain after Cube refreshes"), else `fail` with both refresh
   times in the reason.

A matching cell is `pass`; a `missing_member` cell is `missing_member`; a
`not_comparable` cell gets no verdict.

- [ ] **Step 1: Write the failing tests**

Append:

```python
def test_extract_sql_selects_grain_and_measure():
    _, sheet = _sheet_plain()
    sql = cv.extract_sql(sheet, sheet.measures["% Complete"], ["School Name"], ["(cast(region as string) = 'North')"])
    assert sql.startswith("select school as g0, count(distinct if(is_complete = 1")
    assert "as m_num" in sql and "as m_den" in sql and sql.endswith("group by 1")


def _sheet_plain():
    import tempfile

    d = Path(tempfile.mkdtemp())
    c = cv.load_checks(_write(d, CHECKS))
    return c, c["sheets"]["Overview - Table"]


def test_extract_values_divides_num_by_den():
    rows = [{"g0": "Alpha", "m_num": 16, "m_den": 20}, {"g0": "Beta", "m_num": 0, "m_den": 0}]
    assert cv.extract_values(rows, 1) == {("Alpha",): 0.8, ("Beta",): None}


def test_state_where_translates_filters_and_hides_private_ones(tmp_path):
    c = _checks(tmp_path, extract_filters=[{"sql": "not is_test", "private": True}, {"sql": "enrolled"}])
    sheet = c["sheets"]["Overview - Table"]
    entry = {"state": {"dashboard": "Overview", "filters": {"Region": "North"}}, "click_filters": {"School Name": "Alpha"}}
    fields = {"Region": {"field": "region", "datasource": DS}}
    assert cv.state_where(entry, c, fields, sheet) == [
        "cast(region as string) = 'North'", "cast(school as string) = 'Alpha'", "not is_test", "enrolled",
    ]
    assert "not is_test" not in cv.state_where(entry, c, fields, sheet, public_only=True)


def test_cell_verdict_by_who_fixes():
    sides = {"cube": frozenset({"a"}), "dashboard": frozenset({"b"}), "source": frozenset({"c"}),
             "undecided": frozenset({"d"})}
    meas = cv.Measure("M", "demo.m", sql="x", missing_members=["demo.extra"])
    cell = lambda names: cv.Cell("S", "s", {}, "M", "1", 1, 2, 20, "mismatch", explained_by=names)  # noqa: E731
    assert cv.cell_verdict(cell([]), sides, meas) == "fail"
    assert cv.cell_verdict(cell(["a", "b"]), sides, meas) == "fix_cube"
    assert cv.cell_verdict(cell(["c"]), sides, meas) == "fix_source"
    assert cv.cell_verdict(cell(["d"]), sides, meas) == "undecided"
    assert cv.cell_verdict(cell(["demo.extra"]), sides, meas) == "missing_member"
    assert cv.cell_verdict(cell(["b"]), sides, meas) == "pass"


def _timing(tmp_path, live_value, cube_at):
    c = _checks(tmp_path)
    cell = cv.Cell("Overview - Table", "s", {}, "Avg Score", "48.50", 48.5, 49.0, 40, "mismatch")
    states = {"s": {"state": {"dashboard": "Overview"}, "status": "ok", "sheets": {}}}
    live = cv.Live(
        rows=lambda ds, sql: [{"m": live_value}],
        modified=lambda ds: dt.datetime(2026, 10, 9, 10, tzinfo=dt.UTC),
        cube_refreshed=lambda q: cube_at,
    )
    cv.explain_cells([cell], c, states, {}, lambda ds, sql: [{"m": 48.5}], lambda q: ([], []), live)
    return cell


def test_cube_matching_the_live_table_is_a_timing_pass(tmp_path):
    cell = _timing(tmp_path, 49.0, dt.datetime(2026, 10, 9, 11, tzinfo=dt.UTC))
    assert cell.verdict == "pass" and cell.reason.startswith("timing")


def test_stale_cube_is_incomplete_not_fail(tmp_path):
    cell = _timing(tmp_path, 48.0, dt.datetime(2026, 10, 9, 8, tzinfo=dt.UTC))
    assert cell.verdict == "incomplete" and "older than the live table" in cell.reason


def test_fresh_cube_that_differs_from_the_live_table_fails(tmp_path):
    cell = _timing(tmp_path, 48.0, dt.datetime(2026, 10, 9, 11, tzinfo=dt.UTC))
    assert cell.verdict == "fail" and "2026-10-09 10:00" in cell.reason
```

The end-to-end behaviour of `explain_cells` (trust gate, variants, verdicts) is
pinned by the replay in Task 19, which runs real SQL over a synthetic extract.

- [ ] **Step 2: Run the tests to verify they fail**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate.py -q -k "extract_sql or extract_values or state_where or cell_verdict or timing or live_table or stale_cube" 2>&1 | tail -n 30`
Expected: FAIL, `AttributeError: ... has no attribute 'extract_sql'`.

- [ ] **Step 3: Write the implementation**

Append:

```python
def state_where(entry, checks, fields, sheet, public_only=False) -> list[str]:
    st = entry["state"]
    dims_sql = {c: d.sql for c, d in sheet.dims.items()}
    out = []
    pairs = list((st.get("filters") or {}).items()) + list((entry.get("click_filters") or {}).items())
    for caption, value in pairs:
        f = (fields.get(caption) or {}).get("field") or dims_sql.get(caption)
        if f and (c := _cond(f, value)):
            out.append(c)
    for f in checks["extract_filters"]:
        if f.get("datasource") not in (None, sheet.datasource):
            continue
        if public_only and f.get("private"):
            continue
        out.append(f["sql"])
    return out


def extract_sql(sheet, meas, grain, where) -> str:
    sel = [f"{sheet.dims[d].sql} as g{i}" for i, d in enumerate(grain)]
    sel += [f"{meas.sql} as m"] if meas.sql else [f"{meas.num} as m_num", f"{meas.den} as m_den"]
    # Backticks: sqlglot quotes the name, which to_hyper_sql swaps for the extract table.
    sql = f"select {', '.join(sel)} from `{EXTRACT_TABLE}`"
    if where:
        sql += " where " + " and ".join(f"({w})" for w in where)
    if grain:
        sql += " group by " + ", ".join(str(i + 1) for i in range(len(grain)))
    return sql


def extract_values(rows, n_grain) -> dict:
    out = {}
    for r in rows:
        k = tuple(norm_dim(r[f"g{i}"]) for i in range(n_grain))
        if "m" in r:
            out[k] = _num(r["m"])
        else:
            num, den = _num(r["m_num"]), _num(r["m_den"])
            out[k] = None if not den else (num or 0.0) / den
    return out


def cell_verdict(c, sides, meas) -> str:
    names = set(c.explained_by)
    if not names:
        return "fail"
    for side, verdict in (("cube", "fix_cube"), ("source", "fix_source"), ("undecided", "undecided")):
        if names & sides.get(side, frozenset()):
            return verdict
    if names & set(meas.missing_members):
        return "missing_member"
    return "pass"  # every cause is a dashboard fix: Cube is right


def _grain(c: Cell) -> tuple[tuple[str, ...], tuple[str, ...]]:
    return (tuple(d for d, v in c.key.items() if v != TOTAL), tuple(d for d, v in c.key.items() if v == TOTAL))


def _key(c: Cell, grain) -> tuple:
    return tuple(norm_dim(c.key[d]) for d in grain)


def _reproduces(value, c: Cell, meas: Measure) -> bool:
    if (c.shown or "").strip():
        return matches_shown(value, parse_shown(c.shown, meas.round))
    return value in (None, 0.0)


def _has_state(st: dict) -> bool:
    return bool(st.get("filters") or st.get("params") or st.get("click"))


def _trust(cells, checks, states, fields, run_extract) -> dict[tuple[str, str], bool]:
    """A measure's SQL is trusted once it reproduces every comparable cell of one state."""
    pools: dict[tuple[str, str], dict[str, list[Cell]]] = {}
    for c in cells:
        if c.status in ("match", "mismatch") and (c.shown or "").strip():
            pools.setdefault((c.sheet, c.measure), {}).setdefault(c.state, []).append(c)
    out = {}
    for (sname, mname), by_state in pools.items():
        defaults = sorted(s for s in by_state if not _has_state(states[s]["state"]))
        state = defaults[0] if defaults else sorted(by_state)[0]
        sheet = checks["sheets"][sname]
        meas = sheet.measures[mname]
        where = state_where(states[state], checks, fields, sheet)
        ok = True
        groups: dict[tuple, list[Cell]] = {}
        for c in by_state[state]:
            groups.setdefault(_grain(c)[0], []).append(c)
        for grain, group in groups.items():
            rows = run_extract(sheet.datasource, extract_sql(sheet, meas, list(grain), where))
            ext = apply_calc(meas, extract_values(rows, len(grain)), 1.0)
            ok = ok and all(_reproduces(ext.get(_key(c, grain)), c, meas) for c in group)
        out[(sname, mname)] = ok
    return out


def _cube_at(load, sheet, meas, grain, filters) -> dict:
    q = {"measures": [meas.cube], "dimensions": [sheet.dims[d].cube for d in grain],
         "filters": filters, "limit": CUBE_LIMIT}
    rows, _ = load(q)
    raw = {tuple(norm_dim(r.get(sheet.dims[d].cube)) for d in grain): _num(r.get(meas.cube)) for r in rows}
    return apply_calc(meas, raw, meas.scale)


def _variant(v, sheet, meas, grain, where, base, run_extract, load):
    dash = None
    if v.get("where"):
        alt = Measure(meas.caption, meas.cube, table_calc=meas.table_calc,
                      sql=_filtered(meas.sql, v["where"]) if meas.sql else None,
                      num=None if meas.sql else _filtered(meas.num, v["where"]),
                      den=None if meas.sql else _filtered(meas.den, v["where"]))
    elif v.get("sql") or v.get("num"):
        alt = Measure(meas.caption, meas.cube, sql=v.get("sql"), num=v.get("num"),
                      den=v.get("den"), table_calc=meas.table_calc)
    else:
        alt = None
    if alt is not None:
        rows = run_extract(sheet.datasource, extract_sql(sheet, alt, list(grain), where))
        dash = apply_calc(alt, extract_values(rows, len(grain)), 1.0)
    cube = _cube_at(load, sheet, meas, grain, base + v["cube_filters"]) if v.get("cube_filters") else None
    return v["explains"], dash, cube


@dataclass
class Live:
    """The live warehouse side of the timing check."""

    rows: Callable[[str, str], list[dict]]  # extract SQL run on the live rpt_ table
    modified: Callable[[str], dt.datetime | None]  # when that table last changed
    cube_refreshed: Callable[[dict], dt.datetime | None]  # Cube's lastRefreshTime


def explain_cells(cells, checks, states, fields, run_extract, load, live=None) -> None:
    sides = fix_sides(checks)
    batches: dict[tuple, list[Cell]] = {}
    for c in cells:
        if c.status == "match":
            c.verdict = "pass"
        elif c.status == "missing_member":
            c.verdict = "missing_member"
        elif c.status == "mismatch":
            batches.setdefault((c.sheet, c.state, _grain(c)[0], c.measure), []).append(c)
    trusted = _trust(cells, checks, states, fields, run_extract)
    for (sname, state, grain, mname), batch in batches.items():
        sheet = checks["sheets"][sname]
        meas = sheet.measures[mname]
        if not trusted.get((sname, mname)):
            for c in batch:
                c.verdict, c.reason = "incomplete", "extract SQL does not reproduce Tableau for this measure"
            continue
        entry = states[state]
        where = state_where(entry, checks, fields, sheet)
        base = state_filters(entry, checks)[0] + hard_filters(checks, sheet.datasource)
        rows = run_extract(sheet.datasource, extract_sql(sheet, meas, list(grain), where))
        ext = apply_calc(meas, extract_values(rows, len(grain)), 1.0)
        live_v, times = None, (None, None)
        if live is not None:
            lrows = live.rows(sheet.datasource, extract_sql(sheet, meas, list(grain), where))
            live_v = apply_calc(meas, extract_values(lrows, len(grain)), 1.0)
            q = {"measures": [meas.cube], "dimensions": [sheet.dims[d].cube for d in grain],
                 "filters": base, "limit": CUBE_LIMIT}
            times = (live.cube_refreshed(q), live.modified(sheet.datasource))
        variants = [_variant(v, sheet, meas, grain, where, base, run_extract, load) for v in meas.variants]
        for c in batch:
            k = _key(c, grain)
            c.extract = ext.get(k)
            if not _reproduces(c.extract, c, meas):
                c.verdict, c.reason = "incomplete", "extract SQL does not reproduce this cell"
                continue
            if live_v is not None and matches_raw(live_v.get(k), c.cube):
                c.verdict = "pass"
                c.reason = "timing: the extract is older than Cube; Cube matches the live table"
                continue
            for names, dash, cube in variants:
                d_v = c.extract if dash is None else dash.get(k)
                c_v = c.cube if cube is None else cube.get(k)
                if matches_raw(c_v, d_v):
                    c.explained_by, c.variant = list(names), d_v
                    c.cube_variant = None if cube is None else c_v
                    break
            c.verdict = cell_verdict(c, sides, meas)
            cube_at, table_at = times
            if c.verdict == "fail" and cube_at and table_at:
                if cube_at < table_at:
                    c.verdict = "incomplete"
                    c.reason = (
                        f"Cube's data (refreshed {cube_at:%Y-%m-%d %H:%M}) is older than the live "
                        f"table (built {table_at:%Y-%m-%d %H:%M}); re-run explain after Cube refreshes"
                    )
                else:
                    c.reason = (
                        f"Cube refreshed {cube_at:%Y-%m-%d %H:%M}; the live table was built "
                        f"{table_at:%Y-%m-%d %H:%M}"
                    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate.py -q 2>&1 | tail -n 30`
Expected: 72 passed.

- [ ] **Step 5: Commit**

```bash
git add -u scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): explain gaps from the extract behind a trust gate

Refs #5856

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

### Task 16: verdicts per Asana row, and `latest.json`

**Files:**

- Modify: `scripts/cube_validate.py`
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Consumes: `Cell` with `verdict` (Task 15)
- Produces:
  - `ORDER = ("fail", "incomplete", "fix_cube", "fix_source", "undecided", "missing_member", "pass")`
  - `worst(verdicts) -> str` (`incomplete` when there are none)
  - `row_results(cells: list[Cell], checks: dict) -> dict[str, dict]` (per row
    gid: `verdict`, `cells`, `by_verdict`, `mismatches`, `reopen_for`)
  - `write_latest(path: Path, workbook: str, run_date: str, rows: dict) -> None`
    (merges into the existing file; `sync.py` reads `verdict` and `reopen_for`
    per gid)

- [ ] **Step 1: Write the failing tests**

Append:

```python
def test_worst_follows_the_verdict_order():
    assert cv.worst(["pass", "undecided", "fix_cube"]) == "fix_cube"
    assert cv.worst(["pass", None]) == "pass"
    assert cv.worst([]) == "incomplete"


def test_row_results_take_the_worst_cell_of_the_rows_members(tmp_path):
    c = _checks(tmp_path, rows={"111": ["demo.avg_score"], "222": ["demo.pct_complete"]})
    cells = [
        cv.Cell("Overview - Table", "s", {}, "Avg Score", "1", 1, 1, 20, "match", verdict="pass"),
        cv.Cell("Overview - Table", "s", {}, "Avg Score", "1", 1, 2, 20, "mismatch", verdict="fix_cube",
                explained_by=["dup"]),
        cv.Cell("Overview - Table", "s", {}, "% Complete", None, None, None, None, "not_comparable"),
    ]
    rows = cv.row_results(cells, c)
    assert rows["111"]["verdict"] == "fix_cube" and rows["111"]["mismatches"] == ["dup"]
    assert rows["222"]["verdict"] == "incomplete"  # nothing comparable: never a pass


def test_write_latest_merges_rows(tmp_path):
    p = tmp_path / "latest.json"
    p.write_text(json.dumps({"999": {"verdict": "pass"}}))
    cv.write_latest(p, "Demo", "2026-10-09", {"111": {"verdict": "fail", "reopen_for": []}})
    data = json.loads(p.read_text())
    assert data["999"]["verdict"] == "pass"
    assert data["111"] == {"verdict": "fail", "reopen_for": [], "dashboard": "Demo", "run_date": "2026-10-09"}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate.py -q -k "worst or row_results or write_latest" 2>&1 | tail -n 30`
Expected: FAIL, `AttributeError: ... has no attribute 'worst'`.

- [ ] **Step 3: Write the implementation**

Append:

```python
ORDER = ("fail", "incomplete", "fix_cube", "fix_source", "undecided", "missing_member", "pass")


def worst(verdicts) -> str:
    found = [v for v in verdicts if v]
    return min(found, key=ORDER.index) if found else "incomplete"


def _members(checks) -> dict[tuple[str, str], Measure]:
    return {(s.name, m.caption): m for s in checks["sheets"].values() for m in s.measures.values()}


def row_results(cells, checks) -> dict[str, dict]:
    by_cell = _members(checks)
    out = {}
    for gid, members in checks["rows"].items():
        mine = [c for c in cells if c.verdict and (m := by_cell.get((c.sheet, c.measure))) and m.cube in members]
        reopen = sorted({
            mm for c in mine if c.verdict == "missing_member"
            for mm in by_cell[(c.sheet, c.measure)].missing_members
        })
        out[gid] = {
            "verdict": worst(c.verdict for c in mine),
            "cells": len(mine),
            "by_verdict": dict(Counter(c.verdict for c in mine)),
            "mismatches": sorted({n for c in mine for n in c.explained_by}),
            "reopen_for": reopen,
        }
    return out


def write_latest(path: Path, workbook: str, run_date: str, rows: dict) -> None:
    p = Path(path)
    data = json.loads(p.read_text()) if p.exists() else {}
    for gid, r in rows.items():
        data[gid] = {**r, "dashboard": workbook, "run_date": run_date}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, sort_keys=True))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate.py -q 2>&1 | tail -n 30`
Expected: 75 passed.

- [ ] **Step 5: Commit**

```bash
git add -u scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): row verdicts and latest.json for sync.py

Refs #5856

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

### Task 17: coverage report, digest and issue drafts (with privacy)

**Files:**

- Modify: `scripts/cube_validate.py`
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Consumes: cells with verdicts (Task 15), `row_results`, `write_latest` (Task
  16), `extract_sql`, `state_where` (Task 15), `fix_sides`
- Produces:
  - `_issue_labels`, `_OTHER_SIDE`, `_ANSWERS` (v1 lines 3150-3159 and
    3181-3204, verbatim)
  - `masked_key(c: Cell, checks: dict) -> dict[str, str]`
  - `coverage_markdown(states: dict[str, dict], cells: list[Cell]) -> str`
  - `digest_markdown(workbook: str, cells: list[Cell], checks: dict) -> str`
  - `issue_drafts(workbook: str, cells: list[Cell], checks: dict, states: dict[str, dict], fields: dict) -> dict[str, str]`
    (slug → markdown with a `title:` and `labels:` front block, then the
    bug-template body)
  - `write_outputs(out_dir: Path, workbook: str, run_date: str, cells: list[Cell], checks: dict, states: dict, fields: dict) -> Path`
    (writes `<date>-<slug>-coverage.md`, `<date>-<slug>-digest.md`, the
    `<date>-<slug>-issues/` drafts and `latest.json`; returns the digest path)

Privacy rules (from the spec): a `person` dimension shows "a student" or its
label; a cell under `SMALL_CELL` students shows "small cell" in place of its
values; drafts use `state_where(..., public_only=True)`, so private extract
filters never reach a draft.

- [ ] **Step 1: Write the failing tests**

Append:

```python
def _explained(tmp_path):
    c = _checks(tmp_path, mismatches={
        "dup": {"title": "fix(cube): duplicate rows", "what": "Cube counts some rows twice.", "fix": "cube"},
        "filed": {"title": "fix(tableau): x", "what": "y", "fix": "dashboard", "issue": 4321},
    })
    cells = [
        cv.Cell("Overview - Table", "s", {"School Name": "All"}, "Avg Score", "48.50", 48.5, 47.0, 40,
                "mismatch", verdict="fix_cube", explained_by=["dup"], extract=48.5, variant=48.5, cube_variant=48.5),
        cv.Cell("Overview - Table", "s", {"School Name": "Alpha"}, "Avg Score", "48.50", 48.5, 47.0, 4,
                "mismatch", verdict="fix_cube", explained_by=["dup"]),
        cv.Cell("Overview - Table", "s", {"Student": "Real Name"}, "Avg Score", "9", 9, 8, 30,
                "mismatch", verdict="fail"),
    ]
    states = {"s": {"state": {"dashboard": "Overview"}, "status": "ok", "sheets": {}}}
    return c, cells, states


def test_person_keys_are_masked(tmp_path):
    c, cells, _ = _explained(tmp_path)
    assert cv.masked_key(cells[2], c) == {"Student": "a student"}


def test_digest_groups_by_who_fixes_and_hides_small_cells_and_names(tmp_path):
    c, cells, _ = _explained(tmp_path)
    text = cv.digest_markdown("Demo", cells, c)
    assert text.index("## Fix in Cube") < text.index("## Investigate")
    assert "duplicate rows" in text and "small cell" in text
    assert "Real Name" not in text and "a student" in text


def test_one_draft_per_unfiled_mismatch_with_examples_coarsest_first(tmp_path):
    c, cells, states = _explained(tmp_path)
    drafts = cv.issue_drafts("Demo", cells, c, states, {})
    assert list(drafts) == ["dup"]
    body = drafts["dup"]
    assert body.startswith("title: fix(cube): duplicate rows\nlabels: fix, cube, validation\n")
    for heading in ("## What's happening", "## Steps to reproduce", "## Where", "<summary>For Claude</summary>"):
        assert heading in body
    assert body.index("School Name = All") < body.index("small cell")


def test_drafts_never_carry_private_filters(tmp_path):
    c, cells, states = _explained(tmp_path)
    c["extract_filters"] = [{"sql": "student_number not in (1, 2)", "private": True}]
    assert "student_number not in" not in cv.issue_drafts("Demo", cells, c, states, {})["dup"]


def test_coverage_lists_skipped_states_and_not_comparable_causes():
    states = {"a": {"state": {"dashboard": "D"}, "status": "ok"},
              "b": {"state": {"dashboard": "D"}, "status": "filter_ignored"},
              "c": {"state": {"dashboard": "D"}, "status": "export_failed", "error": "429"}}
    cells = [cv.Cell("S", "a", {}, "M", None, None, None, None, "not_comparable", "multi-value mark")]
    text = cv.coverage_markdown(states, cells)
    assert "filter_ignored: b" in text and "export_failed: c" in text and "multi-value mark: 1" in text


def test_write_outputs_writes_every_file(tmp_path):
    c, cells, states = _explained(tmp_path)
    digest = cv.write_outputs(tmp_path / "out", "Demo", "2026-10-09", cells, c, states, {})
    out = tmp_path / "out"
    assert digest.exists() and (out / "2026-10-09-demo-coverage.md").exists()
    assert (out / "2026-10-09-demo-issues" / "dup.md").exists()
    assert json.loads((out / "latest.json").read_text())["111"]["verdict"] == "fail"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate.py -q -k "masked or digest or draft or coverage or write_outputs" 2>&1 | tail -n 30`
Expected: FAIL, `AttributeError: ... has no attribute 'masked_key'`.

- [ ] **Step 3: Write the implementation**

Paste `_issue_labels`, `_OTHER_SIDE` and `_ANSWERS` from v1 (lines 3150-3159 and
3181-3204), then append:

````python
_SIDE_TITLES = (
    ("cube", "Fix in Cube"),
    ("dashboard", "Fix in the dashboard"),
    ("source", "Fix in the source"),
    ("undecided", "Owner to decide"),
)


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _fmt(v) -> str:
    return "nothing" if v is None else f"{v:.4g}"


def masked_key(c: Cell, checks: dict) -> dict[str, str]:
    dims = checks["sheets"][c.sheet].dims if c.sheet in checks["sheets"] else {}
    out = {}
    for d, v in c.key.items():
        p = dims[d].person if d in dims else False
        out[d] = (p if isinstance(p, str) else "a student") if p else v
    return out


def _where_text(c: Cell, checks) -> str:
    key = masked_key(c, checks)
    return ", ".join(f"{d} = {v}" for d, v in key.items()) or "the whole sheet"


def _example(c: Cell, checks, fix: str | None = None) -> str:
    if c.n_students is None or c.n_students < SMALL_CELL:
        return f"{c.sheet}, {_where_text(c, checks)}: small cell"
    text = f"{c.sheet}, {_where_text(c, checks)}: the dashboard shows {c.shown}, Cube gives {_fmt(c.cube)}"
    if fix and c.variant is not None:
        text += f", the other formula gives {_fmt(c.variant)}"
    if c.cube_variant is not None:
        text += f"; Cube without the affected rows gives {_fmt(c.cube_variant)}"
    return text


def _coarsest(cells: list[Cell]) -> list[Cell]:
    return sorted(cells, key=lambda c: (sum(v != TOTAL for v in c.key.values()), -(c.n_students or 0)))


def coverage_markdown(states, cells) -> str:
    by_status: dict[str, list[str]] = {}
    for sid, e in sorted(states.items()):
        by_status.setdefault(e.get("status", "ok"), []).append(sid)
    lines = ["# Coverage", "", f"States visited: {len(by_status.get('ok', []))}", ""]
    for status in ("filter_ignored", "export_failed"):
        if by_status.get(status):
            lines.append(f"- {status}: {', '.join(by_status[status])}")
    causes = Counter(c.reason for c in cells if c.status == "not_comparable")
    if causes:
        lines += ["", "Cells not compared:", *(f"- {r}: {n}" for r, n in causes.most_common())]
    return "\n".join(lines) + "\n"


def digest_markdown(workbook, cells, checks) -> str:
    sides = fix_sides(checks)
    lines = [f"# {workbook}: Cube against Tableau", ""]
    lines.append("Verdicts: " + ", ".join(f"{v} {n}" for v, n in Counter(c.verdict for c in cells if c.verdict).most_common()))
    for side, title in _SIDE_TITLES:
        slugs = sorted(s for s in sides[side] if any(s in c.explained_by for c in cells))
        if not slugs:
            continue
        lines += ["", f"## {title}", ""]
        for s in slugs:
            m = checks["mismatches"][s]
            mine = _coarsest([c for c in cells if s in c.explained_by])
            ref = f"#{m['issue']}" if m.get("issue") else "draft"
            lines.append(f"- **{m['title']}** ({ref}): {m['what']} {len(mine)} cells.")
            lines += [f"  - {_example(c, checks, side)}" for c in mine[:3]]
    fails = _coarsest([c for c in cells if c.verdict == "fail"])
    if fails:
        lines += ["", "## Investigate", ""]
        for (sheet, measure), n in Counter((c.sheet, c.measure) for c in fails).most_common():
            lines.append(f"- {sheet} / {measure}: {n} cells")
        lines += [f"  - {_example(c, checks)}" for c in fails[:5]]
    unsure = Counter(c.reason for c in cells if c.verdict == "incomplete")
    if unsure:
        lines += ["", "## Could not tell", "", *(f"- {r}: {n} cells" for r, n in unsure.most_common())]
    return "\n".join(lines) + "\n"


def issue_drafts(workbook, cells, checks, states, fields) -> dict[str, str]:
    out = {}
    for s, m in checks["mismatches"].items():
        mine = _coarsest([c for c in cells if s in c.explained_by])
        if m.get("issue") or not mine:
            continue
        first = mine[0]
        sheet = checks["sheets"][first.sheet]
        meas = sheet.measures[first.measure]
        grain = list(_grain(first)[0])
        where = state_where(states[first.state], checks, fields, sheet, public_only=True)
        query = extract_sql(sheet, meas, grain, where)
        alt = [v for v in meas.variants if s in v["explains"]]
        labels = _issue_labels(m)
        related = " ".join(f"#{n}" for n in m.get("related") or [])
        body = [
            f"title: {m['title']}",
            f"labels: {', '.join(labels)}",
            "",
            "## What's happening",
            "",
            m["what"],
            "",
            f"On the {workbook} dashboard, {len(mine)} cells differ between Tableau and Cube "
            "because of this. Examples, coarsest first:",
            "",
            *(f"- {_example(c, checks, m['fix'])}" for c in mine[:5]),
            "",
            "## Steps to reproduce",
            "",
            "1. Run the query below over the dashboard's extract. It gives what Tableau shows.",
            f"2. Query Cube's `{meas.cube}` at the same grain and filters.",
            "3. Compare the two with the other formula below.",
            "",
            "```sql",
            query,
            "```",
            "",
            "The other formula:",
            "",
            "```yaml",
            yaml.safe_dump(alt, sort_keys=False).strip(),
            "```",
            "",
            "## Where",
            "",
            f"- **Code location / dbt project:** {m.get('where', 'tableau')}",
            "- **Environment:** prod",
            f"- **Run, PR, or dashboard link (if any):** {workbook}",
            *([f"- **Related:** {related}"] if related else []),
            "",
            _ANSWERS[m["fix"]],
            "",
            "<details>",
            "<summary>For Claude</summary>",
            "",
            f"> Checks file `.claude/skills/cube-dashboard/checks/{_slug(workbook)}.yml`, "
            f"mismatch `{s}`. Rerun `cube_validate.py explain` after the fix; the cells "
            "above must turn `pass`.",
            "",
            "</details>",
        ]
        out[s] = "\n".join(body) + "\n"
    return out


def write_outputs(out_dir, workbook, run_date, cells, checks, states, fields) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stem = f"{run_date}-{_slug(workbook)}"
    (out / f"{stem}-coverage.md").write_text(coverage_markdown(states, cells))
    digest = out / f"{stem}-digest.md"
    digest.write_text(digest_markdown(workbook, cells, checks))
    drafts = issue_drafts(workbook, cells, checks, states, fields)
    if drafts:
        (out / f"{stem}-issues").mkdir(exist_ok=True)
        for s, text in drafts.items():
            (out / f"{stem}-issues" / f"{s}.md").write_text(text)
    write_latest(out / "latest.json", workbook, run_date, row_results(cells, checks))
    return digest
````

- [ ] **Step 4: Run the tests to verify they pass**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate.py -q 2>&1 | tail -n 30`
Expected: 81 passed. If `test_one_draft_per_unfiled_mismatch...` fails on the
labels line, read v1's `_issue_labels`: it orders labels as type, side,
`labels`, then `validation`; fix the test's expected line to that order, not the
function.

- [ ] **Step 5: Commit**

```bash
git add -u scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): coverage report, digest and issue drafts with masking

Refs #5856

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

### Task 18: the command line (`compare`, `explain`, `drafts`)

**Files:**

- Modify: `scripts/cube_validate.py`
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Consumes: everything in Tasks 9-17
- Produces:
  - `SNAPSHOT_ROOT = Path.home() / ".cache" / "cube-validate"`
  - `latest_snapshot(workbook: str, root: Path = SNAPSHOT_ROOT) -> Path` (same
    rule as the snapshot script; duplicated because `scripts/` files are
    standalone)
  - `class Extracts` (opens one `ExtractSource` per datasource on demand;
    `__call__(datasource, sql) -> list[dict]`; `close()`)
  - `run_compare(checks, snapdir: Path, load, extracts) -> tuple[list[Cell], list[dict]]`
    (new cells for states not yet compared, and the next states)
  - `main(argv: list[str] | None = None) -> int`

Outputs inside the snapshot: `cells.jsonl`, `next_states.yml` (the list
`cube_validate_snapshot.py export --states` reads).

- [ ] **Step 1: Write the failing tests**

Append:

```python
def test_run_compare_compares_new_states_and_proposes_the_next(tmp_path):
    c = _checks(tmp_path, trees={DS: {"region": ["region", "school"]}}, cross_cuts={DS: []})
    snapdir = tmp_path / "snap"
    (snapdir / "csv").mkdir(parents=True)
    (snapdir / "csv" / "n.csv").write_bytes(b"School Name,Avg Score\r\nAlpha,48.50\r\n")
    manifest = {
        "workbook": "Demo", "extracts": {DS: {"file": "x.hyper", "refreshed": None}},
        "fields": {"Region": {"field": "region", "datasource": DS},
                   "School Name": {"field": "school", "datasource": DS}},
        "states": {"n": {"state": {"id": "n", "dashboard": "Overview", "filters": {"Region": "North"}},
                         "status": "ok", "click_filters": {},
                         "sheets": {"Overview - Table": {"file": "csv/n.csv", "rows": 1}}}},
    }
    (snapdir / "manifest.json").write_text(json.dumps(manifest))
    cube = FakeCube({"Alpha": _row(47.0)}, _row(0))
    extracts = lambda ds, sql: [{"v": "Alpha", "n": 30}, {"v": "Beta", "n": 12}]  # noqa: E731
    cells, nxt = cv.run_compare(c, snapdir, cube, extracts)
    assert [x.status for x in cells] == ["mismatch"]
    assert [s["filters"]["School Name"] for s in nxt] == ["Alpha", "Beta"]
    # A second run compares nothing new.
    cv.write_cells(snapdir / "cells.jsonl", cells)
    assert cv.run_compare(c, snapdir, cube, extracts)[0] == []


def test_main_needs_a_command():
    with pytest.raises(SystemExit):
        cv.main([])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate.py -q -k "run_compare or main_needs" 2>&1 | tail -n 30`
Expected: FAIL, `AttributeError: ... has no attribute 'run_compare'`.

- [ ] **Step 3: Write the implementation**

Append:

```python
SNAPSHOT_ROOT = Path.home() / ".cache" / "cube-validate"


def latest_snapshot(workbook: str, root: Path = SNAPSHOT_ROOT) -> Path:
    base = Path(root) / _slug(workbook)
    dirs = sorted(p for p in base.iterdir() if p.is_dir()) if base.exists() else []
    if not dirs:
        raise FileNotFoundError(f"no snapshot for {workbook} under {base}; run the snapshot open step")
    return dirs[-1]


class Extracts:
    """One ExtractSource per datasource, opened on first use."""

    def __init__(self, snapdir: Path, extracts: dict[str, dict]):
        self.snapdir, self.meta, self.open = Path(snapdir), extracts, {}

    def __call__(self, datasource: str, sql: str) -> list[dict]:
        if datasource not in self.open:
            src = ExtractSource(self.snapdir / self.meta[datasource]["file"])
            self.open[datasource] = src.__enter__()
        return self.open[datasource](sql)

    def close(self) -> None:
        for src in self.open.values():
            src.__exit__(None, None, None)
        self.open = {}


def run_compare(checks, snapdir, load, extracts):
    snapdir = Path(snapdir)
    m = json.loads((snapdir / "manifest.json").read_text())
    done = {c.state for c in read_cells(snapdir / "cells.jsonl")}
    cells: list[Cell] = []
    for sid, e in sorted(m["states"].items()):
        if e.get("status") != "ok" or sid in done:
            continue
        filters, missing = state_filters(e, checks)
        for sheet_name, meta in e["sheets"].items():
            sheet = checks["sheets"].get(sheet_name)
            if sheet is None:
                cells.append(Cell(sheet_name, sid, {}, "", None, None, None, None, "not_comparable", "unmapped sheet"))
                continue
            export = read_export((snapdir / meta["file"]).read_bytes())
            cells += compare_export(sheet, sid, export, load, filters, missing, checks)
    every = read_cells(snapdir / "cells.jsonl") + cells

    def children(ds, where, f):
        rows = extracts(ds, child_values_sql(where, f))
        return [(r["v"], int(r["n"])) for r in rows]

    nxt = next_states(m["states"], state_status(every), checks.get("trees") or {},
                      checks.get("cross_cuts") or {}, m["fields"], children)
    return cells, nxt


def _client() -> CubeClient:
    url = os.environ.get("CUBE_API_URL", DEFAULT_CUBE_URL)
    return CubeClient(url, os.environ["CUBE_API_SECRET"], _user_email(None))


def _live(client: CubeClient) -> Live:
    """Extract SQL on each datasource's live rpt_ table, with both sides' refresh times."""
    built: dict[str, dt.datetime | None] = {}

    def rows(ds, sql):
        return bigquery_rows(sql.replace(EXTRACT_TABLE, live_table(ds)))

    def modified(ds):
        if ds not in built:
            built[ds] = table_modified(live_table(ds))
        return built[ds]

    def cube_refreshed(q):
        client.load(q)
        t = client.last_refresh
        return dt.datetime.fromisoformat(t.replace("Z", "+00:00")) if t else None

    return Live(rows, modified, cube_refreshed)


def _compare(a) -> int:
    checks = load_checks(a.checks)
    snapdir = latest_snapshot(checks["workbook"])
    m = json.loads((snapdir / "manifest.json").read_text())
    client, extracts = _client(), Extracts(snapdir, m["extracts"])
    try:
        if checks.get("scope"):
            cap = checks["scope"]["filter"]
            f = m["fields"][cap]
            rows = extracts(f["datasource"], child_values_sql([], f["field"]))
            scope_guard(client.load, checks, {r["v"]: int(r["n"]) for r in rows if r["v"] is not None})
        cells, nxt = run_compare(checks, snapdir, client.load, extracts)
    finally:
        extracts.close()
    write_cells(snapdir / "cells.jsonl", read_cells(snapdir / "cells.jsonl") + cells)
    (snapdir / "next_states.yml").write_text(yaml.safe_dump(nxt, sort_keys=False, allow_unicode=True))
    counts = Counter(c.status for c in cells)
    print(f"compared {len(cells)} cells: " + ", ".join(f"{k} {v}" for k, v in counts.most_common()))
    print(f"next descent level: {len(nxt)} states -> {snapdir / 'next_states.yml'}")
    return 0


def _explain(a) -> int:
    checks = load_checks(a.checks)
    snapdir = latest_snapshot(checks["workbook"])
    m = json.loads((snapdir / "manifest.json").read_text())
    cells = read_cells(snapdir / "cells.jsonl")
    client, extracts = _client(), Extracts(snapdir, m["extracts"])
    try:
        explain_cells(cells, checks, m["states"], m["fields"], extracts, client.load, _live(client))
    finally:
        extracts.close()
    write_cells(snapdir / "cells.jsonl", cells)
    counts = Counter(c.verdict for c in cells if c.verdict)
    print("verdicts: " + ", ".join(f"{k} {v}" for k, v in counts.most_common()))
    return 0


def _drafts(a) -> int:
    checks = load_checks(a.checks)
    snapdir = latest_snapshot(checks["workbook"])
    m = json.loads((snapdir / "manifest.json").read_text())
    cells = read_cells(snapdir / "cells.jsonl")
    digest = write_outputs(Path(a.out), checks["workbook"], dt.date.today().isoformat(),
                           cells, checks, m["states"], m["fields"])
    print(f"digest: {digest}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="cube_validate")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("compare", "explain"):
        sub.add_parser(name).add_argument("checks")
    d = sub.add_parser("drafts")
    d.add_argument("checks")
    d.add_argument("--out", default=str(DEFAULT_OUT))
    a = p.parse_args(argv)
    return {"compare": _compare, "explain": _explain, "drafts": _drafts}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate.py -q 2>&1 | tail -n 30`
Expected: 83 passed.

- [ ] **Step 5: Commit**

```bash
git add -u scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): compare, explain and drafts commands

Refs #5856

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

### Task 19: synthetic replay of the DDI gap types

**Files:**

- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Consumes: `read_export`, `compare_export`, `explain_cells`, `ExtractSource`,
  `load_checks`, `worst`

This is the offline acceptance test. One sheet, 2 schools, 5 measures, each
carrying one known DDI gap type. Real SQL runs over a synthetic `.hyper`; a fake
Cube answers with each gap built in.

| Measure             | Gap built in                              | `fix:`      | Verdict      |
| ------------------- | ----------------------------------------- | ----------- | ------------ |
| `% Complete`        | Cube counts 2 duplicate "not tested" rows | `cube`      | `fix_cube`   |
| `% Completion`      | The dashboard's 2 counts read scored rows | `dashboard` | `pass`       |
| `Students Tested`   | Cube leaves out 2 untagged students       | `undecided` | `undecided`  |
| `Students Assessed` | Cube has a student the extract lacks      | none        | `fail`       |
| `Avg Score`         | Planted bad mapping (`sum` for `avg`)     | none        | `incomplete` |

- [ ] **Step 1: Write the test**

Append:

```python
def _replay_hyper(path):
    hapi = pytest.importorskip("tableauhyperapi")
    cols = [("student_number", hapi.SqlType.int()), ("school", hapi.SqlType.text()),
            ("is_complete", hapi.SqlType.int()), ("is_scored", hapi.SqlType.int()),
            ("is_tagged", hapi.SqlType.int()), ("score", hapi.SqlType.double())]
    table = hapi.TableDefinition(hapi.TableName("Extract", "Extract"),
                                 [hapi.TableDefinition.Column(n, t, hapi.NULLABLE) for n, t in cols])
    rows, sid = [], 0
    for school in ("Alpha", "Beta"):
        for i in range(1, 21):
            sid += 1
            done = i <= 16
            rows.append((sid, school, int(done), int(done), int(i > 2), 40.0 + i if done else None))
    with hapi.HyperProcess(hapi.Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hp:
        with hapi.Connection(hp.endpoint, str(path), hapi.CreateMode.CREATE_AND_REPLACE) as c:
            c.catalog.create_schema("Extract")
            c.catalog.create_table(table)
            with hapi.Inserter(c, table) as ins:
                ins.add_rows(rows)
                ins.execute()
    return path


DONE = "count(distinct if(is_complete = 1, student_number, null))"
REPLAY = {
    "workbook": "Replay",
    "workbook_luid": "w1",
    "student_count": "demo.count_students",
    "rows": {"1": ["demo.pct_complete"], "2": ["demo.pct_completion"], "3": ["demo.n_tested"],
             "4": ["demo.n_assessed"], "5": ["demo.avg_score"]},
    "mismatches": {
        "dup_rows": {"title": "fix(cube): duplicate not-tested rows", "what": "w", "fix": "cube"},
        "scored_only": {"title": "fix(tableau): completion reads scored rows", "what": "w", "fix": "dashboard"},
        "untagged": {"title": "fix(cube): untagged assessments", "what": "w", "fix": "undecided"},
        "avg_bug": {"title": "fix(cube): avg", "what": "w", "fix": "cube"},
    },
    "sheets": {"Sheet": {
        "datasource": DS,
        "dims": {"School": {"cube": "demo.school", "sql": "school"}},
        "measures": {
            "% Complete": {"cube": "demo.pct_complete", "num": DONE, "den": "count(distinct student_number)",
                           "variants": [{"explains": ["dup_rows"], "cube_filters": [
                               {"member": "demo.is_duplicate", "operator": "equals", "values": ["0"]}]}]},
            "% Completion": {"cube": "demo.pct_completion",
                             "num": "count(distinct if(is_scored = 1 and is_complete = 1, student_number, null))",
                             "den": "count(distinct if(is_scored = 1, student_number, null))",
                             "variants": [{"explains": ["scored_only"], "num": DONE,
                                           "den": "count(distinct student_number)"}]},
            "Students Tested": {"cube": "demo.n_tested", "sql": DONE,
                                "variants": [{"explains": ["untagged"], "where": "is_tagged = 1"}]},
            "Students Assessed": {"cube": "demo.n_assessed", "sql": DONE},
            "Avg Score": {"cube": "demo.avg_score", "sql": "sum(score)",
                          "variants": [{"explains": ["avg_bug"], "cube_filters": [
                              {"member": "demo.avg_fixed", "operator": "set"}]}]},
        },
    }},
}


def replay_cube(q):
    members = {f["member"] for f in q.get("filters", [])}

    def row(n):
        return {
            "demo.count_students": str(20 * n),
            "demo.pct_complete": str(0.8 if "demo.is_duplicate" in members else 16 / 22),
            "demo.pct_completion": "0.8",
            "demo.n_tested": str(14 * n),
            "demo.n_assessed": str(17 * n),
            "demo.avg_score": str(48.5 if "demo.avg_fixed" in members else 49.5),
        }

    if "demo.school" in q["dimensions"]:
        return [{"demo.school": s, **row(1)} for s in ("Alpha", "Beta")], []
    return [row(2)], []


def test_replay_finds_each_ddi_gap_type(tmp_path):
    hyper = _replay_hyper(tmp_path / "replay.hyper")
    checks = cv.load_checks(_write(tmp_path, REPLAY))
    export = cv.read_export(
        b"School,% Complete,% Completion,Students Tested,Students Assessed,Avg Score\r\n"
        b"Alpha,0.8,1,16,16,48.5\r\nBeta,0.8,1,16,16,48.5\r\nAll,0.8,1,32,32,48.5\r\n"
    )
    states = {"replay--default": {"state": {"id": "replay--default", "dashboard": "Replay"},
                                  "status": "ok", "sheets": {}, "click_filters": {}}}
    cells = cv.compare_export(checks["sheets"]["Sheet"], "replay--default", export, replay_cube, [], [], checks)
    with cv.ExtractSource(hyper) as src:
        cv.explain_cells(cells, checks, states, {}, lambda ds, sql: src(sql), replay_cube)
    verdicts = {m: cv.worst(c.verdict for c in cells if c.measure == m) for m in REPLAY["sheets"]["Sheet"]["measures"]}
    assert verdicts == {
        "% Complete": "fix_cube",
        "% Completion": "pass",
        "Students Tested": "undecided",
        "Students Assessed": "fail",
        "Avg Score": "incomplete",
    }
    rows = cv.row_results(cells, checks)
    assert rows["5"]["verdict"] == "incomplete"  # the planted bad mapping never blames Cube
```

- [ ] **Step 2: Run the test**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate.py -q -k replay 2>&1 | tail -n 30`
Expected: PASS. Every other part is already built, so a failure here is a real
defect in Tasks 13-15. Debug it with superpowers:systematic-debugging; do not
edit the expected verdicts to make it pass.

- [ ] **Step 3: Run both test files**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate.py tests/scripts/test_cube_validate_snapshot.py -q 2>&1 | tail -n 30`
Expected: 130 passed.

- [ ] **Step 4: Commit**

```bash
git add -u tests/scripts/test_cube_validate.py
git commit -m "test(cube): replay the DDI gap types against a synthetic extract

Refs #5856

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

## Part C: the runbook and the live check

### Task 20: the `cube-dashboard` skill and the script catalog

**Files:**

- Create: `.claude/skills/cube-dashboard/SKILL.md`
- Modify: `scripts/CLAUDE.md` (Script Catalog table)

Open both with the Read tool before editing (root CLAUDE.md, _Tooling_): the
rules for `.claude/skills/` and `CLAUDE.md` files load only through Read, Edit
or Write.

- [ ] **Step 1: Write the skill**

`.claude/skills/cube-dashboard/SKILL.md`:

````markdown
---
name: cube-dashboard
description:
  Use when validating Cube against a Tableau dashboard, re-checking one after a
  Cube or workbook fix, mapping a dashboard's sheets to Cube members, filing or
  following up on the GitHub issues a validation drafted. Triggers: "validate <dashboard> against Cube",
  "does Cube match Tableau", "follow up on <dashboard>", cube_validate,
  ZZ-REVIEW copies in TEMP-CB, or any file under
  .claude/skills/cube-dashboard/checks/.
---

# cube-dashboard

Truth is what Tableau shows. A review copy of the workbook is published to
TEMP-CB, each state a person can reach is exported, Cube is compared with each
export, and SQL over the dashboard's own extract explains each gap. Design:
`docs/superpowers/specs/2026-10-09-cube-validate-tableau-truth-design.md`.

## Running a step that needs credentials

`open`, `export`, `close`, `compare` and `explain` need the Tableau PAT or
`CUBE_API_SECRET`. Only the pytest secrets fixture provides them. Write this
throwaway file, change `ARGS`, run it, and delete it after the session:

```python
# tests/test_zz_cube_validate.py: throwaway, never committed
import importlib.util
import sys
from pathlib import Path

CHECKS = ".claude/skills/cube-dashboard/checks/<dashboard>.yml"
ARGS = ("cube_validate_snapshot", ["open", CHECKS])


def _load(name):
    path = Path(__file__).parents[1] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_step():
    script, argv = ARGS
    mod = _load(script)
    try:
        assert mod.main(argv) == 0
    except BaseException:
        # A failed open or export must not leave the review copy behind.
        if script == "cube_validate_snapshot" and argv[0] in ("open", "export"):
            mod.main(["close", CHECKS])
        raise
```

Run:
`uv run --with tableauhyperapi pytest tests/test_zz_cube_validate.py -s --tb=short`.
`--tb=short` keeps credentials out of a traceback.

## Validating a dashboard

1. **Header.** Create `checks/<dashboard>.yml` with `workbook`, `workbook_luid`,
   `review_project_luid` (TEMP-CB, `ddc817c2-6bc7-4bca-8be9-e385f95b9ebc`),
   `dashboards`, `student_count` (the Cube student-count member) and
   `scope: {filter: <region caption>}`.
2. **Plan.** Run `cube_validate_snapshot.py plan <checks>` (credentialed; it
   downloads the workbook). Show the analyst the trees, the borderline pairs and
   the must, optional and skipped states as one table per dashboard. Save their
   edits as `trees`, `cross_cuts`, `accept_nesting` and `states`.
3. **Open.** `open <checks>`: sweeps stale copies, publishes the review copy,
   exports the planned states, downloads the extracts.
4. **Map.** From the exported CSV headers, draft `sheets:`: each column's Cube
   member (from Cube `meta`) and extract SQL. The analyst approves the mapping.
5. **Compare.** `cube_validate.py compare <checks>`. It writes `cells.jsonl` and
   `next_states.yml` in the snapshot.
6. **Descend.** While `next_states.yml` is not empty:
   `export <checks> --states <snapshot>/next_states.yml`, then compare again.
7. **Close.** `close <checks>`, always, including after a failure. Confirm the
   output says the copy is gone.
8. **Explain.** `cube_validate.py explain <checks>`.
9. **Report.** `cube_validate.py drafts <checks>` (no secret). Read the digest
   and the coverage report.

## Reading the results

- **`filter_ignored` state:** the `vf` caption is wrong (Tableau ignores an
  unknown field silently). Fix the caption, then export that state again.
- **`incomplete`, "extract SQL does not reproduce Tableau":** the mapping's SQL
  is wrong, not Cube. Fix the mapping. Never file this as a Cube issue.
- **`fail`:** a gap nothing explains yet. Find the cause with SQL over the
  extract, then add a `mismatches:` entry and a variant on the measure.
- **Variants:** `sql`, or `num` and `den`, or `where` (limits every aggregate of
  the measure's own formula) on the dashboard side; `cube_filters` for "Cube
  without these rows". A cell is explained only when one variant accounts for
  its whole gap.
- **`fix:`** says who fixes a mismatch: `cube`, `dashboard` (add `where: rpt`
  for the model), `source`, or `undecided` (the domain owner decides).

## Filing

1. For each draft and each "Investigate" row, search the repo's issues, open and
   closed, with the GitHub MCP. List the matches beside it.
2. A match that is the same problem becomes the entry's `issue:`; a related one
   goes in `related:`.
3. Show the analyst the full list of drafts before filing anything. File only
   the ones they pick, with the title, labels and body from the draft.
4. Write each new `issue:` into the checks file and commit it. The analyst runs
   `~/asana-sync/sync.py`.

## Following up ("follow up on <dashboard>")

Read each filed issue's state, labels and comments. A closed issue gets
`closed_on`. On an undecided issue, the label `fix-cube` or `fix-dashboard`, or
a comment starting with the word, sets `fix`. Then open a new session for the
states those cells came from, compare, explain, and report again.

## Timing

The extract is a snapshot; Cube reads current data. When Cube differs from
Tableau but equals the same SQL run on the live `rpt_` table, the gap is only
the extract's age: `explain` marks it `pass` with a timing note. When Cube's
data is older than the live table, the cell is `incomplete`: re-run `explain`
after Cube refreshes. `explain` reads BigQuery through ADC as well as Cube.

## Rules

- Snapshots hold student-level rows. They stay in `~/.cache/cube-validate/`.
  Never commit them, and never paste row values outside the terminal or
  `#data_team`.
- The checks file is committed, so `states:` never holds a person's name.
- Review copies go to TEMP-CB only, named `ZZ-REVIEW <date> <time> <workbook>`.
````

- [ ] **Step 2: Add both scripts to the catalog**

In `scripts/CLAUDE.md`, add these rows to the Script Catalog table, in
alphabetical position after `cube-rest-mcp-launch.sh`:

```text
| `cube_validate.py`            | Compare Cube with a Tableau dashboard's own exports: `compare` diffs each exported sheet with Cube and proposes the next descent level, `explain` judges gaps with SQL over the extract (trusted only once it reproduces Tableau) and checks timing against the live `rpt_` table, `drafts` writes the digest, issue drafts and `latest.json`. Runbook: the `cube-dashboard` skill. |
| `cube_validate_snapshot.py`   | The Tableau side of the same check: `plan` proposes states from the workbook and extract, `open` publishes a `ZZ-REVIEW` copy to TEMP-CB and exports states, `export` adds states, `close` deletes the copy. Credentialed steps run inside a throwaway pytest. Runbook: the `cube-dashboard` skill. |
```

- [ ] **Step 3: Lint**

Run from `/workspaces/teamster`:

```bash
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix .claude/skills/cube-dashboard/SKILL.md scripts/CLAUDE.md </dev/null 2>&1 | tail -n 20
```

Expected: no issues other than formatting (the commit hook formats). Fix any
markdownlint finding.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/cube-dashboard/SKILL.md
git add -u scripts/CLAUDE.md
git commit -m "docs(cube): cube-dashboard runbook for validating against Tableau

Refs #5856

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

### Task 21: live acceptance on the DDI Suite

**Files:**

- Create: `.claude/skills/cube-dashboard/checks/ddi_suite.yml`
- Throwaway: `tests/test_zz_cube_validate.py` (deleted at the end)

This task runs against real Tableau and Cube with the analyst. Stop and ask
whenever the skill says the analyst approves something.

- [ ] **Step 1: Write the checks header**

Find the DDI Suite workbook LUID with the Tableau MCP (`search-content` for "DDI
Suite"). Write `checks/ddi_suite.yml` with the header from the skill's step 1
and `dashboards: [Module Dashboard]` (the dashboard the spike proved).

- [ ] **Step 2: Plan and agree the states**

Run `plan` through the throwaway test. Show the analyst the table. Record their
edits in the checks file. Confirm that `states:` holds no person's name.

- [ ] **Step 3: Open, map, compare, descend, close**

Follow skill steps 3-7. Record from the terminal output: states exported,
`filter_ignored` and `export_failed` counts, descent rounds, and the `close`
confirmation.

- [ ] **Step 4: Settle the open items from the spec**

From this session's output, answer each and note the answer for the PR body:

- Which `vf` caption each tree level uses on the Module Dashboard (homeroom:
  `team` or `course_section`).
- Whether `vf` with comma-joined values filters to those values (the `(All)`
  states: compare their rows with the default view).
- Whether `vf(<caption>, "Null")` selects blank rows (the `(Blank)` states:
  `filter_ignored` means it does not). If it does not, open an issue for a
  working blank filter and link it from the PR.
- Whether the live workbook's `updated_at` moved during the session.

- [ ] **Step 5: Explain and check the known DDI gaps are found**

Run `explain`, then `drafts`. With the analyst, add `mismatches:` entries and
variants for the known DDI gaps (handoff list): duplicate rows in the assessment
fact (`fix: cube`), "% Completion: From 75%" reading scored rows only
(`fix: dashboard`), untagged Illuminate assessments (`fix: undecided`). Rerun
`explain` and `drafts`.

Acceptance: the digest shows the first 3 under their sections, the extract's
missing not-tested students under "Investigate" (DDI weekly extract only; skip
if the Module Dashboard reads only the assessment extract), and no `fix_cube`
verdict caused by a trust-gate failure.

- [ ] **Step 6: Run-twice check**

Open a second session on the same extract (before the next extract refresh) with
the same `states:`, then close it. Compare the 2 snapshots' CSVs:

```bash
cd ~/.cache/cube-validate/ddi-suite && ls && diff -rq "$(ls | sort | tail -n 2 | head -n 1)/csv" "$(ls | sort | tail -n 1)/csv" | head -n 20
```

Expected: no differences in files present in both. Any difference is a
non-deterministic export; list the sheets in the PR body.

- [ ] **Step 7: Confirm nothing is left on the server**

List TEMP-CB's workbooks with the Tableau MCP (`list-workbooks` filtered to the
project). Expected: no `ZZ-REVIEW` workbook from today.

- [ ] **Step 8: Clean up and commit the checks file**

```bash
rm tests/test_zz_cube_validate.py
grep -nE "student_name|lastfirst" .claude/skills/cube-dashboard/checks/ddi_suite.yml || echo "no person fields in states"
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix .claude/skills/cube-dashboard/checks/ddi_suite.yml </dev/null 2>&1 | tail -n 10
git add .claude/skills/cube-dashboard/checks/ddi_suite.yml
git commit -m "feat(cube): DDI Suite checks file for Tableau-truth validation

Refs #5856

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 9: Hand the findings to the analyst, file nothing**

Write the PR-body evidence (counts only, small cells hidden, no names): states
visited, verdict counts, the open-item answers, the run-twice result, and the
server check. List every draft that would be filed, with its related-issue
matches. Filing waits for the analyst, per the skill's _Filing_ section.
