# Tableau constructs in cube-dashboard validation: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** `scripts/cube_validate.py` finds every Tableau construct that can
change what a checked sheet shows, reproduces the ones it can (groups, bins,
copies, parameter branches, drill levels, subtotals), and marks a row
`incomplete` when a construct on its sheets is neither handled nor listed as not
checked.

**Architecture:** The `.twb` parser gains a construct inventory per sheet
(`Construct(kind, name, sheets, detail)`), built from a one-pass workbook index
(`_Workbook`). Grain proposal expands parameter branches, drill levels and
subtotals. The checks file accounts for each construct (`handled:` at the top,
`not_checked:` per row); `audit_rows` compares the two on every run, and the
digest, report and comments list what is unaccounted and what is not checked.

**Tech Stack:** Python 3.13 standalone script, `defusedxml`, `pyyaml`, pytest.
No new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-08-cube-validate-skill-design.md`,
section _Revision 2026-10-08: Tableau constructs that change what a sheet
shows_. Approved 2026-10-08 with both calls confirmed: `not_checked:` items do
not fail a row; an unaccounted construct marks the row `incomplete`.

## Global Constraints

- Run Python only through `uv run`; never bare `python` or `pytest`.
- Test command for every task:
  `uv run pytest tests/scripts/test_cube_validate.py -q`. Never bare
  `uv run pytest` (`tests/` holds live integration tests).
- No new dependencies. XML parsing stays on `defusedxml` (`SafeET`).
- Aggregates only: no student names or ids in fixtures, outputs, comments or
  chat.
- Branch `cristinabaldor/feat/claude-cube-validate-skill`, main checkout, PR
  #5805. Stage files by name (`git add <paths>`); never `-A` or `-u`, because
  `.devcontainer/tpl/.env.tpl` carries the user's own uncommitted edit.
- If a hook blocks `git commit -m`, write the message to the session scratchpad
  and use `git commit -F <file>`.
- Before the final push, lint every touched file:
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`.
  Suppress only with `trunk-ignore(linter/rule): reason`.
- Construct keys are `"<kind>: <name>"`, with kind one of `group`, `bin`, `set`,
  `viewer_function`, `lod`, `table_calc`, `filter`, `total`, `alias`,
  `fiscal_year`, `parameter`, `blend`, `top_n`, `source_filter`.

## Review Focus

1. A quick table calculation token with no trailing `:N`
   (`pcto:usr:Calculation_abs:qk`) still classifies as its measure (Task 2 test
   `test_table_calc_token_without_a_suffix_still_classifies`).
2. A group over a numeric field with text labels compiles to valid SQL: the
   `else` keeps the value as text (Task 6 test
   `test_group_over_a_number_casts_the_kept_value`).
3. A row whose measure appears only under a Measure Names alias is still
   audited, on the sheets that show the alias (Task 7 test
   `test_audit_finds_sheets_through_a_measure_names_alias`).
4. A failing row with unaccounted constructs stays `fail`: fail outranks
   incomplete (Task 7 test
   `test_unaccounted_construct_makes_a_passing_row_incomplete_but_a_fail_stays_fail`).
5. A checks file with no `dashboards:` makes every row `incomplete` with a named
   reason, never a pass (Task 7 test
   `test_audit_without_dashboards_names_the_reason`).

---

### Task 1: Confirm how Tableau shows values outside every bin

The spec's open fact: the `.twb` marks every group `new-bin='true'` and no
workbook defines an Other bin, so values in no bin most likely keep their own
label. Confirm with 1 render before Task 6 relies on it.

**Files:** none (a ruling in the ledger).

**Interfaces:**

- Produces: a ruling
  `Task 1: Ruling: values outside every bin <keep their own label | show as Other>`.
  Task 6 builds `group_case_sql` to keep the value (the default); if this task
  finds Other, Task 9's snippet adds `"other": "Other"` and Task 10's skill text
  says so.

- [ ] **Step 1: Find an aggregate sheet that puts the attendance code group on a
      shelf**

Run:

```bash
cd /workspaces/teamster && uv run python -I -c "
import re
import defusedxml.ElementTree as ET
r = ET.parse('.claude/scratch/cube-dashboard/attendance_dashboard.twb').getroot()
for w in r.iter('worksheet'):
    shelves = (w.findtext('table/rows') or '') + (w.findtext('table/cols') or '')
    if re.search(r'att_code \(group\)|\[none:att_code \(group\)', shelves):
        print(w.get('name'))
"
```

Expected: 1 or more sheet names. If the file is missing, download it per the
skill's _Author a check entry_ step 1.

- [ ] **Step 2: Render it**

Find the published view that holds that sheet with `mcp__tableau__list-views`
for the Attendance workbook, then call `mcp__tableau__get-view-image` with one
region in `viewFilters`. Render only a view that shows aggregates, never a
roster.

Expected: the image shows the group's bins (Absent, Excused, ISS, OSS) plus
either each ungrouped code under its own label or one "Other" bar.

- [ ] **Step 3: Ledger the ruling**

Write the ruling line. If no aggregate view shows the group, rule "keep their
own label" (Tableau's behavior when "Include Other" is unchecked) and add
`unconfirmed by render` to the ruling.

### Task 2: Fixture, copies and table-calculation tokens

**Files:**

- Create: `tests/scripts/fixtures/cube_validate/constructs.twb`
- Modify: `scripts/cube_validate.py` (`_INSTANCE`, `Sheet`, `_columns`,
  `_classify`, new `_resolve`, `parse_twb`)
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Produces: `Sheet.rows_dims`, `Sheet.cols_dims`, `Sheet.measure_aliases`,
  `Sheet.param_dims`, `Sheet.drill_paths`, `Sheet.subtotal_dims`,
  `Sheet.constructs` (filled by Tasks 3 to 5);
  `_resolve(columns, ds, fld) -> tuple[str, str]`; `_NESTED` regex.

- [ ] **Step 1: Write the fixture**

Create `tests/scripts/fixtures/cube_validate/constructs.twb`:

```xml
<?xml version='1.0' encoding='utf-8' ?>
<workbook xmlns:user='http://www.tableausoftware.com/xml/user'>
  <datasources>
    <datasource name='Parameters'>
      <column caption='Level' datatype='string' name='[Parameter 1]' role='measure' type='nominal' value='&quot;Region&quot;'>
        <calculation class='tableau' formula='&quot;Region&quot;' />
      </column>
    </datasource>
    <datasource caption='rpt_demo (kipptaf_tableau)' name='federated.abc'>
      <column caption='School' datatype='string' name='[school_abbreviation]' role='dimension' type='nominal'>
        <aliases><alias key='&quot;TEAM&quot;' value='TEAM Academy' /></aliases>
      </column>
      <column caption='School (copy)' datatype='string' name='[School (copy)_1]' role='dimension' type='nominal'>
        <calculation class='tableau' formula='[school_abbreviation]' />
      </column>
      <column caption='Code Group' datatype='string' name='[att_code (group)]' role='dimension' type='nominal'>
        <calculation class='categorical-bin' column='[att_code]' new-bin='true'>
          <bin default-name='false' value='&quot;Absent&quot;'>
            <value>&quot;A&quot;</value>
            <value>&quot;AD&quot;</value>
          </bin>
          <bin default-name='false' value='&quot;Present&quot;'>
            <value>%null%</value>
            <value>&quot;P&quot;</value>
          </bin>
        </calculation>
      </column>
      <column caption='Score (bin)' datatype='integer' name='[score (bin)]' role='dimension' type='ordinal'>
        <calculation class='bin' decimals='0' formula='[score]' peg='0' size='10' />
      </column>
      <column caption='# Absent' datatype='integer' name='[Calculation_abs]' role='measure' type='quantitative'>
        <calculation class='tableau' formula='SUM([is_absent])' />
      </column>
      <column caption='Days FIXED' datatype='integer' name='[Calculation_lod]' role='measure' type='quantitative'>
        <calculation class='tableau' formula='{FIXED [student_number]: SUM([is_absent])}' />
      </column>
      <column caption='Permissions' datatype='boolean' name='[Calculation_perm]' role='dimension' type='nominal'>
        <calculation class='tableau' formula='ISMEMBEROF(&apos;Group A&apos;)' />
      </column>
      <column caption='Share' datatype='real' name='[Calculation_pct]' role='measure' type='quantitative'>
        <calculation class='tableau' formula='SUM([is_absent]) / TOTAL(SUM([is_absent]))'>
          <table-calc ordering-type='Rows' />
        </calculation>
      </column>
      <column caption='Level Column' datatype='string' name='[Calculation_level]' role='dimension' type='nominal'>
        <calculation class='tableau' formula='CASE [Parameters].[Parameter 1]&#10;WHEN &apos;Region&apos; THEN [region]&#10;WHEN &apos;School&apos; THEN [school_abbreviation]&#10;WHEN &apos;Network&apos; THEN &apos;N/A&apos;&#10;END' />
      </column>
      <column caption='Odd Column' datatype='string' name='[Calculation_odd]' role='dimension' type='nominal'>
        <calculation class='tableau' formula='CASE [Parameters].[Parameter 1] WHEN &apos;Region&apos; THEN [region] + &apos;!&apos; END' />
      </column>
      <column caption='Calendardate' datatype='date' fiscal-year-start='7' name='[calendardate]' role='dimension' type='ordinal' />
      <column datatype='string' name='[:Measure Names]' role='dimension' type='nominal'>
        <aliases><alias key='&quot;[federated.abc].[usr:Calculation_abs:qk]&quot;' value='Absences Shown' /></aliases>
      </column>
      <group caption='Exclude OD' name='[Exclude OD]' name-style='unqualified' user:ui-builder='filter-group'>
        <groupfilter function='except' user:ui-enumeration='exclusive'>
          <groupfilter function='level-members' level='[school_level]' />
          <groupfilter function='member' level='[school_level]' member='&quot;OD&quot;' />
        </groupfilter>
      </group>
      <group name='[User Filter 1]' name-style='unqualified' user:ui-builder='identity-set'>
        <groupfilter function='union'>
          <groupfilter expression='ISMEMBEROF(&apos;Group A&apos;)' function='filter'>
            <groupfilter function='level-members' level='[region]' />
          </groupfilter>
        </groupfilter>
      </group>
      <group name='[Action (School)]' name-style='unqualified' user:ui-builder='filter-group'>
        <groupfilter function='level-members' level='[school_abbreviation]' />
      </group>
      <drill-paths>
        <drill-path name='Geo'>
          <field>[region]</field>
          <field>[School (copy)_1]</field>
        </drill-path>
      </drill-paths>
      <filter class='categorical' column='[federated.abc].[none:region_type:nk]'>
        <groupfilter function='member' level='[none:region_type:nk]' member='&quot;KTAF&quot;' />
      </filter>
    </datasource>
    <datasource caption='other' name='federated.other' />
  </datasources>
  <worksheets>
    <worksheet name='Codes'>
      <table>
        <view>
          <datasource-dependencies datasource='federated.abc' />
          <filter class='categorical' column='[federated.abc].[none:Calculation_perm:nk]' context='true'>
            <groupfilter function='member' level='[none:Calculation_perm:nk]' member='true' />
          </filter>
          <filter class='categorical' column='[federated.abc].[Exclude OD]' />
          <filter class='categorical' column='[federated.abc].[none:att_code:nk]'>
            <groupfilter function='except' user:ui-enumeration='exclusive'>
              <groupfilter function='level-members' level='[none:att_code:nk]' />
              <groupfilter function='member' level='[none:att_code:nk]' member='&quot;X&quot;' />
              <groupfilter function='member' level='[none:att_code:nk]' member='%null%' />
            </groupfilter>
          </filter>
          <filter class='categorical' column='[federated.abc].[User Filter 1]' context='true' />
          <filter class='categorical' column='[federated.abc].[none:gender:nk]'>
            <groupfilter function='level-members' level='[none:gender:nk]' />
          </filter>
        </view>
        <panes><pane><encodings><text column='[federated.abc].[usr:Calculation_abs:qk]' /></encodings></pane></panes>
        <rows>[federated.abc].[none:att_code (group):nk]</rows>
        <cols />
      </table>
    </worksheet>
    <worksheet name='Geo'>
      <table>
        <view><datasource-dependencies datasource='federated.abc' /></view>
        <panes><pane><encodings><text column='[federated.abc].[usr:Calculation_abs:qk]' /></encodings></pane></panes>
        <rows>([federated.abc].[none:region:nk] / [federated.abc].[none:school_abbreviation:nk])</rows>
        <cols>[federated.abc].[yr:calendardate:ok]</cols>
        <subtotals><column>[federated.abc].[none:region:nk]</column></subtotals>
      </table>
    </worksheet>
    <worksheet name='Levels'>
      <table>
        <view><datasource-dependencies datasource='federated.abc' /></view>
        <panes><pane><encodings><text column='[federated.abc].[usr:Calculation_abs:qk]' /></encodings></pane></panes>
        <rows>([federated.abc].[none:Calculation_level:nk] / [federated.abc].[none:Calculation_odd:nk])</rows>
        <cols>[federated.abc].[none:School (copy)_1:nk]</cols>
      </table>
    </worksheet>
    <worksheet name='Shares'>
      <table>
        <view>
          <datasource-dependencies datasource='federated.abc'>
            <column-instance column='[Calculation_abs]' derivation='User' name='[pcto:usr:Calculation_abs:qk:3]' pivot='key' type='quantitative'>
              <table-calc ordering-type='Rows' type='PctTotal' />
            </column-instance>
          </datasource-dependencies>
        </view>
        <panes>
          <pane>
            <encodings>
              <text column='[federated.abc].[pcto:usr:Calculation_abs:qk:3]' />
              <tooltip column='[federated.abc].[usr:Calculation_pct:qk]' />
              <tooltip column='[federated.abc].[usr:Calculation_lod:qk]' />
            </encodings>
          </pane>
        </panes>
        <rows>[federated.abc].[none:region:nk]</rows>
        <cols />
      </table>
    </worksheet>
    <worksheet name='Bins'>
      <table>
        <view>
          <datasource-dependencies datasource='federated.abc' />
          <datasource-dependencies datasource='federated.other' />
          <filter class='categorical' column='[federated.abc].[none:region:nk]'>
            <groupfilter count='5' end='top' function='end' units='records'>
              <groupfilter function='level-members' level='[none:region:nk]' />
            </groupfilter>
          </filter>
          <filter class='quantitative' column='[federated.abc].[sum:score:qk]' included-values='in-range'>
            <min>10</min>
          </filter>
        </view>
        <panes><pane><encodings><text column='[federated.abc].[usr:Calculation_abs:qk]' /></encodings></pane></panes>
        <rows>[federated.abc].[none:score (bin):qk]</rows>
        <cols />
      </table>
    </worksheet>
    <worksheet name='Shown'>
      <table>
        <view>
          <datasource-dependencies datasource='federated.abc' />
          <filter class='categorical' column='[federated.abc].[:Measure Names]'>
            <groupfilter function='union' user:op='manual'>
              <groupfilter function='member' level='[:Measure Names]' member='&quot;[federated.abc].[usr:Calculation_abs:qk]&quot;' />
            </groupfilter>
          </filter>
        </view>
        <rows>[federated.abc].[none:region:nk]</rows>
        <cols>[federated.abc].[:Measure Names]</cols>
      </table>
    </worksheet>
  </worksheets>
  <dashboards>
    <dashboard name='Main'>
      <zones>
        <zone name='Codes' /><zone name='Geo' /><zone name='Levels' />
        <zone name='Shares' /><zone name='Bins' /><zone name='Shown' />
      </zones>
    </dashboard>
  </dashboards>
</workbook>
```

- [ ] **Step 2: Write the failing tests**

Append to `tests/scripts/test_cube_validate.py`:

```python
# ---------------------------------------------------------------- Tableau constructs
def _sheet(name):
    sheets = cv.parse_twb(FIX / "constructs.twb", ["Main"])
    return next(s for s in sheets if s.name == name)


def test_parse_twb_splits_rows_and_cols():
    geo = _sheet("Geo")
    assert geo.rows_dims == ["region", "School"]
    assert geo.cols_dims == ["Calendardate@year"]
    assert geo.shelf_dims == ["region", "School", "Calendardate@year"]


def test_parse_twb_resolves_copies_to_the_source_field():
    assert _sheet("Levels").cols_dims == ["School"]


def test_bin_field_is_not_read_as_a_copy():
    assert _sheet("Bins").shelf_dims == ["Score (bin)"]


def test_parse_twb_reads_a_quick_table_calc_as_its_measure():
    assert "# Absent" in _sheet("Shares").measures


def test_table_calc_token_without_a_suffix_still_classifies():
    columns = {("federated.abc", "[Calculation_abs]"): ("# Absent", "SUM([is_absent])")}
    kind, label, _ = cv._classify("federated.abc", "pcto:usr:Calculation_abs:qk", columns)
    assert (kind, label) == ("measure", "# Absent")
```

- [ ] **Step 3: Run them to verify they fail**

Run:
`uv run pytest tests/scripts/test_cube_validate.py -q -k "rows_and_cols or copies or not_read_as_a_copy or quick_table_calc or without_a_suffix"`
Expected: FAIL (`Sheet` has no `rows_dims`; the table-calc token classifies as
`other`).

- [ ] **Step 4: Implement**

In `scripts/cube_validate.py`, replace `_INSTANCE` and add `_NESTED` below it:

```python
# [<derivation>:<field>:<type>], with a trailing :N on quick table calculations
_INSTANCE = re.compile(r"^([a-z]+):(.+):([a-z]+)(?::\d+)?$")
# A quick table calculation wraps a measure: pcto:sum:<field>
_NESTED = re.compile(r"^([a-z]+):(.+)$")
```

Replace the `Sheet` dataclass:

```python
@dataclass
class Sheet:
    name: str
    dashboards: list[str]
    datasource: str = ""
    measures: dict[str, str] = field(default_factory=dict)  # caption -> formula
    shelf_dims: list[str] = field(default_factory=list)
    filter_dims: list[str] = field(default_factory=list)
    other_filters: list[str] = field(default_factory=list)
    rows_dims: list[str] = field(default_factory=list)
    cols_dims: list[str] = field(default_factory=list)
    # A measure shown through Measure Names under another name: alias -> caption.
    measure_aliases: dict[str, str] = field(default_factory=dict)
    # Dimension label -> {parameter, branches: {parameter value: label or None}}.
    param_dims: dict[str, dict] = field(default_factory=dict)
    drill_paths: list[list[str]] = field(default_factory=list)
    subtotal_dims: list[str] = field(default_factory=list)
    constructs: list[Construct] = field(default_factory=list)
```

In `_columns`, read a formula only from ordinary calculations (a bin's
`formula='[score]'` is its source, not a copy):

```python
            out[(_attr(ds, "name"), _attr(col, "name"))] = (
                _attr(col, "caption") or _attr(col, "name").strip("[]"),
                _attr(calc, "formula")
                if calc is not None and calc.get("class", "tableau") == "tableau"
                else "",
            )
```

Add `_resolve` above `_classify`, and replace `_classify`:

```python
def _resolve(columns, ds: str, fld: str) -> tuple[str, str]:
    """Caption and formula of a field, following plain copies ([x]) to their source."""
    caption, formula = columns.get((ds, f"[{fld}]"), (fld, ""))
    for _ in range(5):
        src = re.fullmatch(r"\s*\[([^\[\]]+)\]\s*", formula or "")
        if not src:
            break
        caption, formula = columns.get(
            (ds, f"[{src.group(1)}]"), (src.group(1), "")
        )
    return caption, formula


def _classify(ds: str, inner: str, columns) -> tuple[str, str, str]:
    """Return (kind, label, formula); kind is 'dim', 'measure' or 'other'."""
    m = _INSTANCE.match(inner)
    if not m:
        return "other", inner, ""
    deriv, fld, _ = m.groups()
    wrapped = _NESTED.match(fld)
    if wrapped and wrapped.group(1) in _MEASURE_DERIVATIONS:
        deriv, fld = wrapped.groups()
    caption, formula = _resolve(columns, ds, fld)
    if deriv == "none":
        return "dim", caption, formula
    if deriv in _DATE_PARTS:
        return "dim", f"{caption}@{_DATE_PARTS[deriv]}", formula
    if deriv in _MEASURE_DERIVATIONS:
        return "measure", caption, formula
    return "other", caption, formula
```

In `parse_twb`, replace the block from `s = Sheet(...)` through the encodings
loop (the filter loop stays as it is):

```python
        s = Sheet(_attr(w, "name"), placed[_attr(w, "name")])

        def take(text: str, dims: list[str], s=s) -> None:
            for ds, inner in _TOKEN.findall(text):
                s.datasource = s.datasource or str(ds_caption.get(ds) or ds)
                kind, label, formula = _classify(ds, inner, columns)
                if kind == "dim" and label not in dims:
                    dims.append(label)
                elif kind == "measure":
                    s.measures.setdefault(label, formula)

        take(w.findtext("table/rows") or "", s.rows_dims)
        take(w.findtext("table/cols") or "", s.cols_dims)
        s.shelf_dims = list(dict.fromkeys(s.rows_dims + s.cols_dims))
        take(
            " ".join(_attr(e, "column") for e in w.findall(".//encodings/*")),
            s.shelf_dims,
        )
```

Add a placeholder `Construct` so the `Sheet` annotation resolves until Task 3
replaces it (above `Sheet`):

```python
@dataclass
class Construct:
    """A Tableau feature on a sheet that can change what the sheet shows."""

    kind: str
    name: str
    sheets: list[str] = field(default_factory=list)
    detail: dict = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.kind}: {self.name}"
```

- [ ] **Step 5: Run the suite**

Run: `uv run pytest tests/scripts/test_cube_validate.py -q` Expected: PASS, all
tests (the 5 new and the existing ones).

- [ ] **Step 6: Commit**

```bash
git add scripts/cube_validate.py tests/scripts/test_cube_validate.py tests/scripts/fixtures/cube_validate/constructs.twb
git commit -m "feat(cube): read field copies and quick table calculations in workbooks"
```

### Task 3: Field-level constructs

**Files:**

- Modify: `scripts/cube_validate.py` (new `_Workbook`, `_tableau_value`,
  `_bins`, `_param_branches`, `_fiscal_start`, `_field_constructs`,
  `_sheet_tokens`, `_sheet_constructs`; `parse_twb` calls it)
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Consumes: `Construct`, `_resolve`, `_NESTED` (Task 2).
- Produces: `CONSTRUCT_KINDS: set[str]`; `_Workbook(root)` with `.columns`,
  `.cols`, `.groups`, `.drill_paths`, `.source_filters`, `.ds_caption`,
  `.mn_aliases`, `.caption(ds, name)`, `.formula(ds, name)`, `.deps(ds, name)`,
  `.closure(ds, names)`;
  `_tableau_value(raw) -> str | int | float | bool | None`;
  `_param_branches(columns, ds, formula) -> dict | None`;
  `_sheet_constructs(book, w, columns) -> list[Construct]` (Task 4 replaces its
  body).

- [ ] **Step 1: Write the failing tests**

```python
def _keys(sheet):
    return {c.key for c in sheet.constructs}


def test_groups_are_constructs_with_their_bins():
    (g,) = [c for c in _sheet("Codes").constructs if c.kind == "group"]
    assert g.name == "Code Group"
    assert g.detail == {
        "of": "att_code",
        "of_formula": None,
        "bins": {"Absent": ["A", "AD"], "Present": [None, "P"]},
    }


def test_numeric_bins_are_constructs():
    (b,) = [c for c in _sheet("Bins").constructs if c.kind == "bin"]
    assert b.detail == {"of": "score", "size": 10}


def test_lod_and_table_calc_formulas_are_constructs():
    assert {"lod: Days FIXED", "table_calc: Share"} <= _keys(_sheet("Shares"))


def test_viewer_functions_are_found_through_a_filter_calc():
    assert "viewer_function: Permissions" in _keys(_sheet("Codes"))


def test_fiscal_year_on_a_year_date_part():
    (f,) = [c for c in _sheet("Geo").constructs if c.kind == "fiscal_year"]
    assert f.name == "Calendardate@year"
    assert f.detail == {"start_month": 7}


def test_unexpandable_parameter_field_is_a_construct():
    keys = _keys(_sheet("Levels"))
    assert "parameter: Odd Column" in keys
    assert "parameter: Level Column" not in keys
```

- [ ] **Step 2: Run them to verify they fail**

Run:
`uv run pytest tests/scripts/test_cube_validate.py -q -k "constructs or viewer or fiscal or unexpandable"`
Expected: FAIL (`constructs` is empty).

- [ ] **Step 3: Implement**

Below `Construct`, add:

```python
CONSTRUCT_KINDS = {
    "group",
    "bin",
    "set",
    "viewer_function",
    "lod",
    "table_calc",
    "filter",
    "total",
    "alias",
    "fiscal_year",
    "parameter",
    "blend",
    "top_n",
    "source_filter",
}
_USER = "{http://www.tableausoftware.com/xml/user}"
_REF = re.compile(r"\[([^\[\]]+)\]")
_PARAM_REF = re.compile(r"\[Parameters\]\.\[[^\[\]]+\]")
_VIEWER = re.compile(r"\b(ISMEMBEROF|USERNAME|USERDOMAIN|FULLNAME)\s*\(", re.I)
_TABLE_CALC_FN = re.compile(
    r"\b(WINDOW_\w+|RUNNING_\w+|LOOKUP|INDEX|RANK\w*|TOTAL|SIZE|FIRST|LAST"
    r"|PREVIOUS_VALUE)\s*\(",
    re.I,
)
_DATE_FN = re.compile(r"\b(YEAR|QUARTER|DATEPART|DATETRUNC|DATENAME)\s*\(", re.I)
_LOD = re.compile(r"\{\s*(FIXED|INCLUDE|EXCLUDE)\b", re.I)
_PARAM_CASE = re.compile(
    r"^\s*CASE\s+\[Parameters\]\.\[([^\[\]]+)\]\s+(.*?)\s*END\s*$", re.S | re.I
)
_WHEN = re.compile(
    r"WHEN\s+'([^']*)'\s+THEN\s+(.*?)(?=\s+WHEN\s+'|\s+ELSE\b|\s*$)", re.S | re.I
)
# Groups Tableau builds from a viewer's clicks: actions, tooltips, highlights.
_IGNORED_GROUPS = ("Action (", "Tooltip (", "Highlight (")


def _tableau_value(raw: str):
    """A member as the .twb writes it: "text", a number, true/false, or %null%."""
    if raw == "%null%":
        return None
    if len(raw) >= 2 and raw[0] == raw[-1] == '"':
        return raw[1:-1]
    if raw in ("true", "false"):
        return raw == "true"
    for cast in (int, float):
        try:
            return cast(raw)
        except ValueError:
            pass
    return raw


class _Workbook:
    """The lookups construct detection needs, built once per workbook."""

    def __init__(self, root: ET.Element):
        self.columns = _columns(root)
        self.cols: dict[tuple[str, str], ET.Element] = {}
        self.groups: dict[tuple[str, str], ET.Element] = {}
        self.drill_paths: dict[str, list[list[str]]] = {}
        self.source_filters: dict[str, list[ET.Element]] = {}
        self.ds_caption: dict[str, str] = {}
        # (datasource, Measure Names member token) -> the alias shown for it
        self.mn_aliases: dict[tuple[str, str], str] = {}
        for ds in root.findall("datasources/datasource"):
            name = _attr(ds, "name")
            self.ds_caption[name] = _attr(ds, "caption") or name
            for col in ds.findall("column"):
                self.cols.setdefault((name, _attr(col, "name")), col)
                if _attr(col, "name") == "[:Measure Names]":
                    for a in col.findall("aliases/alias"):
                        self.mn_aliases[(name, _attr(a, "key").strip('"'))] = (
                            _attr(a, "value").strip()
                        )
            for g in ds.findall("group"):
                self.groups.setdefault((name, _attr(g, "name")), g)
            self.drill_paths[name] = [
                [f.text or "" for f in p.findall("field")]
                for p in ds.findall("drill-paths/drill-path")
            ]
            self.source_filters[name] = ds.findall("filter") + ds.findall(
                "extract//filter"
            )

    def calc(self, ds: str, name: str):
        col = self.cols.get((ds, name))
        return col.find("calculation") if col is not None else None

    def caption(self, ds: str, name: str) -> str:
        col = self.cols.get((ds, name))
        return (_attr(col, "caption") if col is not None else "") or name.strip("[]")

    def formula(self, ds: str, name: str) -> str:
        calc = self.calc(ds, name)
        return _attr(calc, "formula") if calc is not None else ""

    def deps(self, ds: str, name: str) -> list[str]:
        """The fields a field's formula or group reads, as '[name]'."""
        calc = self.calc(ds, name)
        if calc is None:
            return []
        refs = _REF.findall(_PARAM_REF.sub("", _attr(calc, "formula")))
        out = [f"[{r}]" for r in refs]
        if calc.get("column"):
            out.append(_attr(calc, "column"))
        return out

    def closure(self, ds: str, names: list[str]) -> list[str]:
        """The fields named, and every field they read, transitively."""
        seen: list[str] = []
        todo = list(names)
        while todo:
            n = todo.pop(0)
            if n not in seen:
                seen.append(n)
                todo += self.deps(ds, n)
        return seen


def _bins(calc: ET.Element) -> dict:
    return {
        _tableau_value(_attr(b, "value")): [
            _tableau_value(v.text or "") for v in b.findall("value")
        ]
        for b in calc.findall("bin")
    }


def _param_branches(columns, ds: str, formula: str) -> dict | None:
    """A CASE on a parameter whose branches are fields or text, else None."""
    m = _PARAM_CASE.match(formula or "")
    if not m:
        return None
    branches: dict[str, str | None] = {}
    for value, expr in _WHEN.findall(m.group(2)):
        expr = expr.strip()
        ref = re.fullmatch(r"\[([^\[\]]+)\]", expr)
        if ref:
            branches[value] = _resolve(columns, ds, ref.group(1))[0]
        elif re.fullmatch(r"'[^']*'|\"[^\"]*\"", expr):
            branches[value] = None
        else:
            return None
    return {"parameter": m.group(1), "branches": branches} if branches else None


def _fiscal_start(book: _Workbook, ds: str, name: str) -> int | None:
    col = book.cols.get((ds, name))
    start = _attr(col, "fiscal-year-start") if col is not None else ""
    return int(start) if start and start != "1" else None


def _field_constructs(book: _Workbook, ds: str, name: str) -> list[Construct]:
    """Constructs one field carries: a group, a bin, an LOD, a viewer function..."""
    calc = book.calc(ds, name)
    if calc is None:
        return []
    caption, f = book.caption(ds, name), _attr(calc, "formula")
    out = []
    if calc.get("class") == "categorical-bin":
        src = _attr(calc, "column")
        src_formula = book.formula(ds, src)
        out.append(
            Construct(
                "group",
                caption,
                detail={
                    "of": None if src_formula else src.strip("[]"),
                    "of_formula": src_formula or None,
                    "bins": _bins(calc),
                },
            )
        )
        return out
    if calc.get("class") == "bin":
        src = (_REF.findall(f) or [""])[0]
        size = _tableau_value(_attr(calc, "size"))
        return [Construct("bin", caption, detail={"of": src, "size": size})]
    if lod := _LOD.search(f):
        out.append(
            Construct("lod", caption, detail={"type": lod.group(1).lower(), "formula": f})
        )
    if _VIEWER.search(f):
        out.append(Construct("viewer_function", caption, detail={"formula": f}))
    if _TABLE_CALC_FN.search(f) or calc.find("table-calc") is not None:
        out.append(Construct("table_calc", caption, detail={"formula": f}))
    if "[Parameters]." in f and _param_branches(book.columns, ds, f) is None:
        out.append(Construct("parameter", caption, detail={"formula": f}))
    if _DATE_FN.search(f) and any(
        _fiscal_start(book, ds, d) for d in book.deps(ds, name)
    ):
        out.append(Construct("fiscal_year", caption, detail={"formula": f}))
    return out


def _sheet_tokens(w: ET.Element) -> list[tuple[str, str]]:
    """Every field token a sheet uses: shelves, marks, filters, Measure Values."""
    parts = [w.findtext("table/rows") or "", w.findtext("table/cols") or ""]
    parts += [_attr(e, "column") for e in w.findall(".//encodings/*")]
    for f in w.iter("filter"):
        parts.append(_attr(f, "column"))
        if _attr(f, "column").endswith("[:Measure Names]"):
            parts += [_attr(g, "member") for g in f.iter("groupfilter")]
    return _TOKEN.findall(" ".join(parts))


def _sheet_constructs(book: _Workbook, w: ET.Element, columns) -> list[Construct]:
    found: dict[str, Construct] = {}
    by_ds: dict[str, list[str]] = {}
    for ds, inner in _sheet_tokens(w):
        m = _INSTANCE.match(inner)
        if not m:
            continue
        deriv, fld, _ = m.groups()
        wrapped = _NESTED.match(fld)
        if wrapped and wrapped.group(1) in _MEASURE_DERIVATIONS:
            fld = wrapped.group(2)
        by_ds.setdefault(ds, []).append(f"[{fld}]")
        start = _fiscal_start(book, ds, f"[{fld}]")
        if deriv in ("yr", "tyr", "qr", "tqr") and start:
            label = _classify(ds, inner, columns)[1]
            c = Construct("fiscal_year", label, detail={"start_month": start})
            found.setdefault(c.key, c)
    for ds, names in by_ds.items():
        for n in book.closure(ds, names):
            for c in _field_constructs(book, ds, n):
                found.setdefault(c.key, c)
    return list(found.values())
```

In `parse_twb`, replace `columns = _columns(root)` with:

```python
    book = _Workbook(root)
    columns = book.columns
```

and, just before `sheets.append(s)`:

```python
        s.constructs = _sheet_constructs(book, w, columns)
```

- [ ] **Step 4: Run the suite**

Run: `uv run pytest tests/scripts/test_cube_validate.py -q` Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): inventory groups, bins, LODs and viewer functions per sheet"
```

### Task 4: Sheet-level constructs

**Files:**

- Modify: `scripts/cube_validate.py` (new `_filter_detail`, `_set_construct`,
  `_measure_aliases`; replace `_sheet_constructs`; `parse_twb` sets
  `measure_aliases`)
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Consumes: `_Workbook`, `_sheet_tokens`, `_field_constructs`, `_tableau_value`
  (Task 3).
- Produces: `_measure_aliases(book, w, columns) -> dict[str, str]`;
  `Sheet.measure_aliases` filled.

- [ ] **Step 1: Write the failing tests**

```python
def test_filters_carry_their_mode():
    cs = {c.key: c for c in _sheet("Codes").constructs}
    assert cs["filter: att_code"].detail["mode"] == "exclude"
    assert cs["filter: att_code"].detail["nulls"] is True
    assert cs["filter: Permissions"].detail["context"] is True
    # An all-values quick filter is the viewer's control, not a construct.
    assert "filter: gender" not in cs


def test_sets_and_user_filters():
    cs = {c.key: c for c in _sheet("Codes").constructs}
    assert cs["set: Exclude OD"].detail == {
        "mode": "exclude",
        "members": ["OD"],
        "of": "school_level",
    }
    assert "viewer_function: User Filter 1" in cs


def test_quick_table_calc_top_n_range_filter_and_blend():
    shares = {c.key: c for c in _sheet("Shares").constructs}
    assert shares["table_calc: # Absent"].detail == {"quick": "PctTotal"}
    bins = {c.key: c for c in _sheet("Bins").constructs}
    assert {"top_n: region", "filter: score", "blend: other"} <= set(bins)
    assert bins["filter: score"].detail["range"] == {"min": "10"}


def test_source_filters_reach_every_sheet_on_the_datasource():
    key = "source_filter: rpt_demo (kipptaf_tableau): region_type"
    for name in ("Codes", "Geo", "Levels", "Shares", "Bins", "Shown"):
        assert key in _keys(_sheet(name))


def test_measure_names_alias_is_a_construct():
    shown = _sheet("Shown")
    assert shown.measure_aliases == {"Absences Shown": "# Absent"}
    assert "alias: Absences Shown" in _keys(shown)


def test_plain_subtotals_are_grains_not_constructs():
    assert not any(c.kind == "total" for c in _sheet("Geo").constructs)
```

- [ ] **Step 2: Run them to verify they fail**

Run:
`uv run pytest tests/scripts/test_cube_validate.py -q -k "mode or sets_and or top_n or source_filters or names_alias or subtotals_are"`
Expected: FAIL on the first 5 (no filter, set, blend, source-filter or alias
constructs yet); the subtotal test passes already.

- [ ] **Step 3: Implement**

Add above `_sheet_constructs`:

```python
def _filter_detail(f: ET.Element) -> dict | None:
    """What a filter keeps, or None for an all-values quick filter."""
    gfs = list(f.iter("groupfilter"))
    members = [
        _tableau_value(_attr(g, "member"))
        for g in gfs
        if _attr(g, "function") == "member"
    ]
    exclude = any(
        _attr(g, "function") == "except"
        or g.get(f"{_USER}ui-enumeration") == "exclusive"
        for g in gfs
    )
    rng = {k: f.findtext(k) for k in ("min", "max") if f.find(k) is not None}
    context = _attr(f, "context") == "true"
    if not (members or rng or context or _attr(f, "class") == "relative-date"):
        return None
    return {
        "mode": "exclude" if exclude else "include",
        "members": members,
        "nulls": None in members,
        "range": rng,
        "context": context,
        "class": _attr(f, "class"),
    }


def _set_construct(book: _Workbook, ds: str, name: str) -> Construct | None:
    """A set or user filter used on the sheet; action and tooltip groups are not."""
    g = book.groups.get((ds, f"[{name}]"))
    if g is None or name.startswith(_IGNORED_GROUPS):
        return None
    caption = _attr(g, "caption") or name
    gfs = list(g.iter("groupfilter"))
    exprs = [_attr(x, "expression") for x in gfs if x.get("expression")]
    if g.get(f"{_USER}ui-builder") == "identity-set" or any(
        _VIEWER.search(e) for e in exprs
    ):
        return Construct(
            "viewer_function", caption, detail={"set": name, "expressions": exprs}
        )
    return Construct(
        "set",
        caption,
        detail={
            "mode": "exclude"
            if any(_attr(x, "function") == "except" for x in gfs)
            else "include",
            "members": [
                _tableau_value(_attr(x, "member"))
                for x in gfs
                if _attr(x, "function") == "member"
            ],
            "of": next(
                (_attr(x, "level").strip("[]") for x in gfs if x.get("level")), None
            ),
        },
    )


def _measure_aliases(book: _Workbook, w: ET.Element, columns) -> dict[str, str]:
    """Measures this sheet shows through Measure Names under another name."""
    out = {}
    for f in w.iter("filter"):
        if not _attr(f, "column").endswith("[:Measure Names]"):
            continue
        for g in f.iter("groupfilter"):
            member = _attr(g, "member").strip('"')
            for ds, inner in _TOKEN.findall(member):
                alias = book.mn_aliases.get((ds, member))
                caption = _classify(ds, inner, columns)[1]
                if alias and alias != caption:
                    out[alias] = caption
    return out
```

Replace `_sheet_constructs`:

```python
def _sheet_constructs(book: _Workbook, w: ET.Element, columns) -> list[Construct]:
    """Every construct that can change what this sheet shows."""
    found: dict[str, Construct] = {}

    def add(c: Construct | None) -> None:
        if c is not None:
            found.setdefault(c.key, c)

    tokens = _sheet_tokens(w)
    instances = {_attr(ci, "name"): ci for ci in w.iter("column-instance")}
    by_ds: dict[str, list[str]] = {}
    for ds, inner in tokens:
        add(_set_construct(book, ds, inner))
        m = _INSTANCE.match(inner)
        if not m:
            continue
        deriv, fld, _ = m.groups()
        add(_set_construct(book, ds, fld))
        wrapped = _NESTED.match(fld)
        if wrapped and wrapped.group(1) in _MEASURE_DERIVATIONS:
            fld = wrapped.group(2)
            ci = instances.get(f"[{inner}]")
            tc = ci.find("table-calc") if ci is not None else None
            quick = _attr(tc, "type") if tc is not None else deriv
            add(
                Construct(
                    "table_calc",
                    _classify(ds, inner, columns)[1],
                    detail={"quick": quick or deriv},
                )
            )
        by_ds.setdefault(ds, []).append(f"[{fld}]")
        start = _fiscal_start(book, ds, f"[{fld}]")
        if deriv in ("yr", "tyr", "qr", "tqr") and start:
            add(
                Construct(
                    "fiscal_year",
                    _classify(ds, inner, columns)[1],
                    detail={"start_month": start},
                )
            )
    for f in w.iter("filter"):
        if _attr(f, "column").endswith("[:Measure Names]"):
            continue
        for ds, inner in _TOKEN.findall(_attr(f, "column")):
            if (ds, f"[{inner}]") in book.groups:
                continue  # a set: added from the tokens above
            label = _classify(ds, inner, columns)[1]
            if any(_attr(g, "function") == "end" for g in f.iter("groupfilter")):
                add(Construct("top_n", label))
            elif detail := _filter_detail(f):
                add(Construct("filter", label, detail=detail))
    sub = w.find("table/subtotals")
    # Plain subtotals become grains; any other setting needs a person to read it.
    if sub is not None and (sub.attrib or any(c.tag != "column" for c in sub)):
        add(
            Construct(
                "total",
                "subtotals",
                detail={"attributes": dict(sub.attrib), "children": [c.tag for c in sub]},
            )
        )
    used = list(dict.fromkeys([ds for ds, _ in tokens] + [
        _attr(d, "datasource") for d in w.iter("datasource-dependencies")
    ]))
    used = [ds for ds in used if ds and ds != "Parameters"]
    for ds in used:
        if used and ds != used[0]:
            add(Construct("blend", book.ds_caption.get(ds, ds)))
        for f in book.source_filters.get(ds, []):
            for fds, inner in _TOKEN.findall(_attr(f, "column")):
                label = _classify(fds, inner, columns)[1]
                add(
                    Construct(
                        "source_filter",
                        f"{book.ds_caption.get(ds, ds)}: {label}",
                        detail=_filter_detail(f) or {},
                    )
                )
    for alias, caption in _measure_aliases(book, w, columns).items():
        add(Construct("alias", alias, detail={"field": caption}))
    for ds, names in by_ds.items():
        for n in book.closure(ds, names):
            for c in _field_constructs(book, ds, n):
                add(c)
    return list(found.values())
```

In `parse_twb`, before `s.constructs = ...`, add:

```python
        s.measure_aliases = _measure_aliases(book, w, columns)
```

- [ ] **Step 4: Run the suite**

Run: `uv run pytest tests/scripts/test_cube_validate.py -q` Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): inventory filters, sets, blends and aliases per sheet"
```

### Task 5: Grain expansion

**Files:**

- Modify: `scripts/cube_validate.py` (`parse_twb` fills `param_dims`,
  `drill_paths`, `subtotal_dims`; new `_dedupe`, `_shelves`, `_subtotal_grains`;
  replace `propose_grains`)
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Consumes: `_param_branches`, `_Workbook.drill_paths` (Task 3);
  `Sheet.measure_aliases` (Task 4).
- Produces: `_shelves(s: Sheet) -> list[list[str]]`;
  `_subtotal_grains(s: Sheet, shelf: list[str]) -> list[list[str]]`;
  `propose_grains` also matches a measure by its Measure Names alias.

- [ ] **Step 1: Write the failing tests**

```python
def test_parameter_branches_parse():
    assert _sheet("Levels").param_dims["Level Column"] == {
        "parameter": "Parameter 1",
        "branches": {"Region": "region", "School": "School", "Network": None},
    }


def test_grains_expand_parameter_branches_and_drill_levels():
    grains = cv.propose_grains(cv.parse_twb(FIX / "constructs.twb", ["Main"]), "# Absent")
    assert ["region", "Odd Column"] in grains
    assert ["region", "School", "Odd Column"] in grains
    assert not any("Level Column" in g for g in grains)


def test_grains_add_drill_levels_and_subtotals():
    geo = _sheet("Geo")
    assert cv._shelves(geo) == [
        ["region", "Calendardate@year"],
        ["region", "School", "Calendardate@year"],
    ]
    assert cv._subtotal_grains(geo, ["region", "School", "Calendardate@year"]) == [
        ["region", "Calendardate@year"]
    ]


def test_grains_include_sheets_showing_the_measure_under_an_alias():
    # region heads the Geo drill path, so the sheet also drills down to School.
    assert cv.propose_grains([_sheet("Shown")], "Absences Shown") == [
        [],
        ["region"],
        ["region", "School"],
    ]
```

- [ ] **Step 2: Run them to verify they fail**

Run:
`uv run pytest tests/scripts/test_cube_validate.py -q -k "branches_parse or expand_parameter or drill_levels_and or under_an_alias"`
Expected: FAIL (`param_dims` empty; no `_shelves`).

- [ ] **Step 3: Implement**

In `parse_twb`, extend `take` to record parameter dimensions and
parameter-swapped measures, and collect the raw datasource names:

```python
        raw: list[str] = []

        def take(text: str, dims: list[str], s=s, raw=raw) -> None:
            for ds, inner in _TOKEN.findall(text):
                s.datasource = s.datasource or str(ds_caption.get(ds) or ds)
                if ds not in raw:
                    raw.append(ds)
                kind, label, formula = _classify(ds, inner, columns)
                branches = _param_branches(columns, ds, formula)
                if kind == "dim" and label not in dims:
                    dims.append(label)
                    if branches:
                        s.param_dims[label] = branches
                elif kind == "measure":
                    s.measures.setdefault(label, formula)
                    # A parameter that swaps measures: the sheet shows each branch.
                    for b in (branches or {}).get("branches", {}).values():
                        if b:
                            s.measures.setdefault(b, "")
```

After the encodings `take(...)` call, add:

```python
        for ds in raw:
            for path in book.drill_paths.get(ds, []):
                labels = [_resolve(columns, ds, n.strip("[]"))[0] for n in path]
                if any(d in s.shelf_dims for d in labels):
                    s.drill_paths.append(labels)
        for ds, inner in _TOKEN.findall(
            " ".join(c.text or "" for c in w.findall("table/subtotals/column"))
        ):
            s.subtotal_dims.append(_classify(ds, inner, columns)[1])
```

Replace `propose_grains`, adding its helpers above it:

```python
def _dedupe(dims) -> list[str]:
    return list(dict.fromkeys(d for d in dims if d is not None))


def _shelves(s: Sheet) -> list[list[str]]:
    """The sheet's shelf grain once per parameter value and per drill level."""
    shelves = [list(s.shelf_dims)]
    by_param: dict[str, list[str]] = {}
    for label, p in s.param_dims.items():
        by_param.setdefault(p["parameter"], []).append(label)
    for labels in by_param.values():
        # Every field switching on one parameter switches together.
        values = list(
            dict.fromkeys(v for lb in labels for v in s.param_dims[lb]["branches"])
        )
        shelves = [
            _dedupe(
                s.param_dims[d]["branches"].get(v) if d in labels else d
                for d in shelf
            )
            for shelf in shelves
            for v in values
        ]
    for path in s.drill_paths:
        nxt = []
        for shelf in shelves:
            at = [i for i, d in enumerate(shelf) if d in path]
            if not at:
                nxt.append(shelf)
                continue
            rest = [d for d in shelf if d not in path]
            pos = sum(1 for d in shelf[: at[0]] if d not in path)
            nxt += [rest[:pos] + path[:k] + rest[pos:] for k in range(1, len(path) + 1)]
        shelves = nxt
    return [list(t) for t in dict.fromkeys(tuple(sh) for sh in shelves)]


def _subtotal_grains(s: Sheet, shelf: list[str]) -> list[list[str]]:
    """A subtotal on d totals the fields nested inside d on its axis."""
    out = []
    for d in s.subtotal_dims:
        axis = s.rows_dims if d in s.rows_dims else s.cols_dims
        if d in shelf and d in axis:
            inner = axis[axis.index(d) + 1 :]
            out.append([x for x in shelf if x not in inner])
    return out


def propose_grains(sheets: list[Sheet], measure: str) -> list[list[str]]:
    """The total; each sheet's shelf grains, subtotals, and each filter added."""
    grains: list[list[str]] = [[]]
    for s in sheets:
        if measure not in s.measures and measure not in s.measure_aliases:
            continue
        for shelf in _shelves(s):
            extra = [shelf + [f] for f in s.filter_dims if f not in shelf]
            for g in [shelf] + _subtotal_grains(s, shelf) + extra:
                if g not in grains:
                    grains.append(list(g))
    return grains
```

- [ ] **Step 4: Run the suite**

Run: `uv run pytest tests/scripts/test_cube_validate.py -q` Expected: PASS,
including the existing
`test_propose_grains_adds_total_shelf_and_one_filter_at_a_time`.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): expand grains across parameters, drill levels and subtotals"
```

### Task 6: Checks file: groups, bins, Tableau captions, accounting

**Files:**

- Modify: `scripts/cube_validate.py` (`Dim`, new `group_case_sql`, `_dim_sql`,
  `_construct_key_ok`; `load_checks`)
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Consumes: `CONSTRUCT_KINDS` (Task 3); `_sql_literal` (existing).
- Produces: `Dim.group_kind: str | None` (`relabel`, `rule` or None);
  `group_case_sql(of, bins, other=None) -> str`; checks keys `dashboards` (list,
  default `[]`), `handled` (dict, default `{}`), per metric `tableau` (list,
  default `[]`), per row `not_checked` (list of `{construct, why}`, default
  `[]`).

- [ ] **Step 1: Write the failing tests**

```python
def test_group_dimension_compiles_to_a_case(tmp_path):
    def m(d):
        d["dimensions"]["code_group"] = {
            "cube": None,
            "kind": "relabel",
            "group": {"of": "att_code", "bins": {"Absent": ["A", "AD"], "Present": [None, "P"]}},
        }

    dim = cv.load_checks(_write_variant(tmp_path, m))["dimensions"]["code_group"]
    assert dim.sql == (
        "case when att_code in ('A', 'AD') then 'Absent' "
        "when att_code in ('P') or att_code is null then 'Present' "
        "else cast(att_code as string) end"
    )
    assert dim.group_kind == "relabel"


def test_group_over_a_number_casts_the_kept_value():
    sql = cv.group_case_sql("lvl", {"Not Proficient": [1, 2], "Proficient": [4, 5]})
    assert sql == (
        "case when lvl in (1, 2) then 'Not Proficient' "
        "when lvl in (4, 5) then 'Proficient' else cast(lvl as string) end"
    )
    assert cv.group_case_sql("lvl", {"Low": [1]}, other="Other").endswith(
        "else 'Other' end"
    )


def test_bin_dimension_compiles_to_floor(tmp_path):
    def m(d):
        d["dimensions"]["score_bin"] = {"cube": None, "bin": {"of": "score", "size": 10}}

    dim = cv.load_checks(_write_variant(tmp_path, m))["dimensions"]["score_bin"]
    assert dim.sql == "floor((score) / 10) * 10"


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda d: d["dimensions"].update(g={"cube": None, "sql": "x", "kind": "rule", "group": {"of": "x", "bins": {}}}), "not both"),
        (lambda d: d["dimensions"].update(g={"cube": None, "group": {"of": "x", "bins": {}}}), "relabel or rule"),
        (lambda d: d["rows"][0].update(not_checked=[{"construct": "widget: x", "why": "y"}]), "unknown construct"),
        (lambda d: d["rows"][0].update(not_checked=[{"construct": "group: x"}]), "why"),
        (lambda d: d.update(handled={"nonsense": "x"}), "unknown construct"),
    ],
)
def test_load_checks_rejects_bad_construct_entries(tmp_path, mutate, message):
    with pytest.raises(cv.CheckError, match=message):
        cv.load_checks(_write_variant(tmp_path, mutate))


def test_load_checks_normalizes_tableau_captions(tmp_path):
    def m(d):
        d["rows"][0]["metrics"][0]["tableau"] = "# Tardy"

    c = cv.load_checks(_write_variant(tmp_path, m))
    assert c["rows"][0]["metrics"][0]["tableau"] == ["# Tardy"]
    assert c["rows"][1]["metrics"][0]["tableau"] == []
    assert c["dashboards"] == [] and c["handled"] == {}
    assert c["rows"][0]["not_checked"] == []
```

- [ ] **Step 2: Run them to verify they fail**

Run:
`uv run pytest tests/scripts/test_cube_validate.py -q -k "case or floor or bad_construct or tableau_captions"`
Expected: FAIL (`KeyError: 'sql'`; no `group_case_sql`).

- [ ] **Step 3: Implement**

Replace `Dim`:

```python
@dataclass(frozen=True)
class Dim:
    name: str
    cube: str | None  # None: no Cube member, so grains using it are not comparable
    sql: str
    granularity: str | None = None
    tableau_only: bool = False  # a dashboard control, not data: never a missing member
    group_kind: str | None = None  # a Tableau group: relabel (buckets) or rule (a definition)
```

Add below `Dim` (it needs `_sql_literal`, defined later in the module; Python
resolves it at call time):

```python
def group_case_sql(of: str, bins: dict, other: str | None = None) -> str:
    """A Tableau group as SQL; a value in no bin keeps its own value unless `other`."""
    whens = []
    for label, values in bins.items():
        conds = []
        kept = [v for v in values if v is not None]
        if kept:
            conds.append(f"{of} in ({', '.join(_sql_literal(v) for v in kept)})")
        if any(v is None for v in values):
            conds.append(f"{of} is null")
        whens.append(f"when {' or '.join(conds)} then {_sql_literal(label)}")
    # The kept value is cast so a numeric field still matches text bin labels.
    rest = _sql_literal(other) if other is not None else f"cast({of} as string)"
    return f"case {' '.join(whens)} else {rest} end"


def _dim_sql(path, name: str, d: dict) -> str:
    if "group" in d:
        if "sql" in d:
            raise CheckError(f"{path}: dimension '{name}': give group or sql, not both")
        if d.get("kind") not in ("relabel", "rule"):
            raise CheckError(
                f"{path}: dimension '{name}': a group needs kind relabel or rule"
            )
        g = d["group"]
        return group_case_sql(g["of"], g["bins"], g.get("other"))
    if "bin" in d:
        b = d["bin"]
        return f"floor(({b['of']}) / {b['size']}) * {b['size']}"
    if "sql" not in d:
        raise CheckError(f"{path}: dimension '{name}' needs sql, group or bin")
    return d["sql"]


def _construct_key_ok(key) -> bool:
    kind, _, name = str(key).partition(": ")
    return kind in CONSTRUCT_KINDS and bool(name)
```

In `load_checks`, replace the `dims = {...}` comprehension:

```python
    dims = {
        n: Dim(
            n,
            d.get("cube"),
            _dim_sql(path, n, d),
            d.get("granularity"),
            bool(d.get("tableau_only")),
            d.get("kind") if ("group" in d or "bin" in d) else None,
        )
        for n, d in data["dimensions"].items()
    }
```

Inside the `for row in data["rows"]:` validation loop, after the metrics loop
(before `for g in row["grains"]:`), add:

```python
        for m in row["metrics"]:
            t = m.get("tableau")
            m["tableau"] = [t] if isinstance(t, str) else list(t or [])
        row.setdefault("not_checked", [])
        for n in row["not_checked"]:
            if not _construct_key_ok(n.get("construct")):
                raise CheckError(
                    f"{where}: not_checked names unknown construct "
                    f"'{n.get('construct')}' (use '<kind>: <name>' from `grains`)"
                )
            if not n.get("why"):
                raise CheckError(f"{where}: not_checked '{n['construct']}' needs a why")
```

After the rows loop, before `seen: dict[str, dict] = {}`, add:

```python
    data["dashboards"] = list(data.get("dashboards") or [])
    data["handled"] = dict(data.get("handled") or {})
    for key in data["handled"]:
        if not _construct_key_ok(key):
            raise CheckError(f"{path}: handled names unknown construct '{key}'")
```

- [ ] **Step 4: Run the suite**

Run: `uv run pytest tests/scripts/test_cube_validate.py -q` Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): group and bin dimensions, and construct accounting in checks"
```

### Task 7: Audit rows on every run

**Files:**

- Modify: `scripts/cube_validate.py` (new `merge_constructs`, `audit_rows`;
  `run_dashboard` takes `audit`; `_run_command` builds it)
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Consumes: `parse_twb`, `Construct` (Tasks 2 to 5); checks keys from Task 6.
- Produces: `merge_constructs(sheets) -> list[Construct]`;
  `audit_rows(checks, twb) -> dict[str, dict]` keyed by row gid, each
  `{"not_checked": [...], "unaccounted": [...]}` or `{"error": str}`; items are
  `asdict(Construct)` plus `key` (and `why` for not-checked);
  `run_dashboard(..., audit=None)`; row results gain `unaccounted`,
  `not_checked`, `audit_error` when present.

- [ ] **Step 1: Write the failing tests**

```python
ALL_KEYS = {
    "group: Code Group",
    "filter: Permissions",
    "viewer_function: Permissions",
    "set: Exclude OD",
    "filter: att_code",
    "viewer_function: User Filter 1",
    "source_filter: rpt_demo (kipptaf_tableau): region_type",
    "fiscal_year: Calendardate@year",
    "parameter: Odd Column",
    "table_calc: # Absent",
    "table_calc: Share",
    "lod: Days FIXED",
    "bin: Score (bin)",
    "top_n: region",
    "filter: score",
    "blend: other",
    "alias: Absences Shown",
}


def _audited(tmp_path, mutate=None):
    def m(d):
        d["dashboards"] = ["Main"]
        for row in d["rows"]:
            for metric in row["metrics"]:
                metric["tableau"] = "# Absent"
        if mutate:
            mutate(d)

    checks = cv.load_checks(_write_variant(tmp_path, m))
    return checks, cv.audit_rows(checks, FIX / "constructs.twb")


def test_audit_lists_every_construct_on_the_rows_sheets(tmp_path):
    _, audit = _audited(tmp_path)
    assert {c["key"] for c in audit["1"]["unaccounted"]} == ALL_KEYS


def test_audit_splits_handled_and_not_checked(tmp_path):
    def m(d):
        d["handled"] = {"group: Code Group": "dimension code_group"}
        d["rows"][0]["not_checked"] = [
            {"construct": "table_calc: Share", "why": "percent of total"}
        ]

    _, audit = _audited(tmp_path, m)
    keys = {c["key"] for c in audit["1"]["unaccounted"]}
    assert "group: Code Group" not in keys
    assert "table_calc: Share" not in keys
    (nc,) = audit["1"]["not_checked"]
    assert (nc["key"], nc["sheets"], nc["why"]) == (
        "table_calc: Share",
        ["Shares"],
        "percent of total",
    )


def test_audit_finds_sheets_through_a_measure_names_alias(tmp_path):
    def m(d):
        d["rows"][0]["metrics"][0]["tableau"] = "Absences Shown"

    _, audit = _audited(tmp_path, m)
    assert {c["key"] for c in audit["1"]["unaccounted"]} == {
        "alias: Absences Shown",
        "source_filter: rpt_demo (kipptaf_tableau): region_type",
    }


def test_audit_needs_a_tableau_caption(tmp_path):
    def m(d):
        d["rows"][1]["metrics"][0]["tableau"] = []

    _, audit = _audited(tmp_path, m)
    assert "tableau:" in audit["2"]["error"]


def test_audit_without_dashboards_names_the_reason(tmp_path):
    def m(d):
        d["dashboards"] = []

    checks, audit = _audited(tmp_path, m)
    assert "names no dashboards" in audit["1"]["error"]
    result = cv.run_dashboard(checks, FakeCube(), FakeBQ(), TODAY, audit=audit)
    assert result["rows"]["2"]["verdict"] == "incomplete"
    assert "names no dashboards" in result["rows"]["2"]["audit_error"]


def test_unaccounted_construct_makes_a_passing_row_incomplete_but_a_fail_stays_fail(
    tmp_path,
):
    _, audit = _audited(tmp_path)
    result = cv.run_dashboard(_checks(), FakeCube(), FakeBQ(), TODAY, audit=audit)
    assert result["rows"]["1"]["verdict"] == "fail"
    assert result["rows"]["2"]["verdict"] == "incomplete"
    assert len(result["rows"]["2"]["unaccounted"]) == len(ALL_KEYS)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/scripts/test_cube_validate.py -q -k audit` Expected:
FAIL (`audit_rows` not defined).

- [ ] **Step 3: Implement**

Add after `propose_grains`:

```python
def merge_constructs(sheets: list[Sheet]) -> list[Construct]:
    """Each construct once, with every sheet it appears on."""
    out: dict[str, Construct] = {}
    for s in sheets:
        for c in s.constructs:
            m = out.setdefault(c.key, Construct(c.kind, c.name, [], c.detail))
            if s.name not in m.sheets:
                m.sheets.append(s.name)
    return list(out.values())


def audit_rows(checks: dict, twb) -> dict[str, dict]:
    """Per row: constructs on its sheets, split into not checked and unaccounted."""
    rows = [str(r["row_gid"]) for r in checks["rows"]]
    if not checks["dashboards"]:
        msg = "the checks file names no dashboards, so its sheets cannot be audited"
        return {gid: {"error": msg} for gid in rows}
    sheets = parse_twb(twb, checks["dashboards"])
    out = {}
    for row in checks["rows"]:
        gid = str(row["row_gid"])
        captions = [c for m in row["metrics"] for c in m["tableau"]]
        if not captions:
            out[gid] = {
                "error": "no metric names its Tableau measure (tableau:), so its "
                "sheets cannot be audited"
            }
            continue
        using = [
            s
            for s in sheets
            if any(c in s.measures or c in s.measure_aliases for c in captions)
        ]
        if not using:
            out[gid] = {
                "error": f"no sheet on {', '.join(checks['dashboards'])} shows "
                f"{', '.join(captions)}"
            }
            continue
        why = {n["construct"]: n["why"] for n in row["not_checked"]}
        found = merge_constructs(using)
        out[gid] = {
            "not_checked": [
                dict(asdict(c), key=c.key, why=why[c.key])
                for c in found
                if c.key in why
            ],
            "unaccounted": [
                dict(asdict(c), key=c.key)
                for c in found
                if c.key not in why and c.key not in checks["handled"]
            ],
        }
    return out
```

Change the `run_dashboard` signature to:

```python
def run_dashboard(
    checks,
    cube_load,
    bq,
    today,
    rows=None,
    scope_only=False,
    snapshots=None,
    audit=None,
) -> dict:
```

and replace the `result["rows"][str(row["row_gid"])] = {...}` block with:

```python
        a = (audit or {}).get(str(row["row_gid"]), {})
        verdict = row_verdict(grains)
        if (a.get("unaccounted") or a.get("error")) and verdict in (
            "pass",
            "missing_member",
        ):
            # A construct nobody accounted for may change what the sheet shows.
            verdict = "incomplete"
        result["rows"][str(row["row_gid"])] = {
            "name": row["name"],
            "verdict": verdict,
            "grains": grains,
            **({"diagnosis": diagnosis} if diagnosis else {}),
            "missing_members": {
                k: v
                for k, v in missing.items()
                if v["explains_cells"] or v["blocks_grains"] or v["changes_total"]
            },
            **({"unaccounted": a["unaccounted"]} if a.get("unaccounted") else {}),
            **({"not_checked": a["not_checked"]} if a.get("not_checked") else {}),
            **({"audit_error": a["error"]} if a.get("error") else {}),
        }
```

In `_run_command`, after `cube_at = cube_built_at(...)`, add:

```python
    audit = audit_rows(checks, SCRATCH / checks["dashboard"] / "workbook.twb")
```

and pass `audit=audit` to `run_dashboard`.

- [ ] **Step 4: Run the suite**

Run: `uv run pytest tests/scripts/test_cube_validate.py -q` Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): mark a row incomplete when a Tableau construct is unaccounted"
```

### Task 8: Outputs list unaccounted and not-checked constructs

**Files:**

- Modify: `scripts/cube_validate.py` (new `_construct_hint`, `_construct_lines`;
  `comment_text`, `digest_markdown`, `report_markdown`)
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Consumes: row keys `unaccounted`, `not_checked`, `audit_error` (Task 7);
  `Dim.group_kind` (Task 6).
- Produces: digest sections `## Unaccounted Tableau constructs`,
  `## Not checked`, and `### Definitions to decide`.

- [ ] **Step 1: Write the failing tests**

```python
def test_comment_and_digest_list_unaccounted_and_not_checked(tmp_path):
    def m(d):
        d["rows"][1]["not_checked"] = [
            {"construct": "table_calc: Share", "why": "percent of total"}
        ]

    checks, audit = _audited(tmp_path, m)
    result = cv.run_dashboard(checks, FakeCube(), FakeBQ(), TODAY, audit=audit)
    row = result["rows"]["2"]
    text = cv.comment_text(row, result)
    assert f"Unaccounted Tableau constructs: {len(ALL_KEYS) - 1}; see the fix digest." in text
    assert "Not checked: 1 Tableau construct; see the fix digest." in text
    digest = cv.digest_markdown(result, checks, {})
    assert "## Unaccounted Tableau constructs" in digest
    assert "- group: Code Group on Codes (2 bins over att_code)" in digest
    assert "## Not checked" in digest
    assert ": percent of total" in digest
    report = cv.report_markdown(result)
    assert "Unaccounted: " in report and "Not checked: table_calc: Share." in report


def test_rule_groups_are_listed_as_decisions(tmp_path):
    def m(d):
        d["dimensions"]["code_group"] = {
            "cube": None,
            "kind": "rule",
            "group": {"of": "att_code", "bins": {"Absent": ["A"]}},
        }
        d["rows"][0]["grains"].append(["code_group"])

    checks = cv.load_checks(_write_variant(tmp_path, m))
    result = cv.run_dashboard(checks, FakeCube(), FakeBQ(), TODAY)
    digest = cv.digest_markdown(result, checks, {})
    assert "### Definitions to decide" in digest
    assert "- code_group: blocks 1 grain in 1 row" in digest
```

- [ ] **Step 2: Run them to verify they fail**

Run:
`uv run pytest tests/scripts/test_cube_validate.py -q -k "unaccounted_and_not_checked or decisions"`
Expected: FAIL.

- [ ] **Step 3: Implement**

Add above `comment_text`:

```python
def _construct_hint(c: dict) -> str:
    """One short phrase on what a construct does, for the digest."""
    d, k = c.get("detail") or {}, c["kind"]
    if k == "group":
        return f"{len(d.get('bins', {}))} bins over {d.get('of') or d.get('of_formula')}"
    if k == "bin":
        return f"size {d.get('size')} over {d.get('of')}"
    if k in ("filter", "set", "source_filter"):
        bits = [d.get("mode", "include")]
        if d.get("members"):
            bits.append(", ".join("null" if v is None else str(v) for v in d["members"]))
        if d.get("range"):
            bits.append(", ".join(f"{a} {v}" for a, v in d["range"].items()))
        if d.get("context"):
            bits.append("context")
        return "; ".join(bits)
    if k == "alias":
        return f"shows {d.get('field')}"
    for key in ("quick", "formula", "expressions", "start_month"):
        if d.get(key):
            return str(d[key])
    return ""


def _construct_lines(items: list[dict], with_why: bool) -> list[str]:
    out = []
    for c in items:
        hint = _construct_hint(c)
        line = f"- {c['key']} on {', '.join(c['sheets'])}"
        line += f" ({hint})" if hint else ""
        line += f": {c['why']}" if with_why else ""
        out.append(line)
    return out
```

In `comment_text`, before `return "\n".join(lines)`, add:

```python
    if row.get("audit_error"):
        lines.append(f"Not audited: {row['audit_error']}.")
    if row.get("unaccounted"):
        lines.append(
            f"Unaccounted Tableau constructs: {len(row['unaccounted'])}; "
            "see the fix digest."
        )
    if row.get("not_checked"):
        lines.append(
            f"Not checked: {_plural(len(row['not_checked']), 'Tableau construct')}; "
            "see the fix digest."
        )
```

In `digest_markdown`, replace the `if blocked:` block with:

```python
    if blocked:
        dims_ = checks["dimensions"]
        rules = {
            n: b
            for n, b in blocked.items()
            if getattr(dims_.get(n), "group_kind", None) == "rule"
        }
        plain = {n: b for n, b in blocked.items() if n not in rules}
        for title, group in (
            ("Dimensions the dashboard slices by that Cube lacks", plain),
            # A group that encodes a definition: someone decides it, then Cube names it.
            ("Definitions to decide", rules),
        ):
            if not group:
                continue
            out += [f"### {title}", ""]
            for name, b in sorted(group.items(), key=lambda kv: -kv[1]["grains"]):
                dim = dims_.get(name)
                col = f"; dashboard field `{dim.sql}`" if dim else ""
                out.append(
                    f"- {name}: blocks {_plural(b['grains'], 'grain')} in "
                    f"{_plural(b['rows'], 'row')}{col}"
                )
            out.append("")
```

and replace the closing `if not any_gap: ... return "\n".join(out)` with:

```python
    if not any_gap:
        out += ["Nothing unexplained.", ""]
    gaps = [(g, r) for g, r in rows.items() if r.get("unaccounted") or r.get("audit_error")]
    if gaps:
        out += [
            "## Unaccounted Tableau constructs",
            "",
            "Add each to the checks file: under `handled:` with what reproduces it, "
            "or under the row's `not_checked:` with why.",
            "",
        ]
        for gid, r in gaps:
            out.append(f"### {r['name']} ({gid})")
            if r.get("audit_error"):
                out.append(f"- Not audited: {r['audit_error']}")
            out += _construct_lines(r.get("unaccounted", []), with_why=False)
            out.append("")
    skipped = [(g, r) for g, r in rows.items() if r.get("not_checked")]
    if skipped:
        out += ["## Not checked", ""]
        for gid, r in skipped:
            out.append(f"### {r['name']} ({gid})")
            out += _construct_lines(r["not_checked"], with_why=True)
            out.append("")
    return "\n".join(out)
```

In `report_markdown`, after the `if row.get("missing_members"):` block, add:

```python
        for label, key in (("Unaccounted", "unaccounted"), ("Not checked", "not_checked")):
            if row.get(key):
                out += [f"{label}: {', '.join(c['key'] for c in row[key])}.", ""]
        if row.get("audit_error"):
            out += [f"Not audited: {row['audit_error']}.", ""]
```

- [ ] **Step 4: Run the suite**

Run: `uv run pytest tests/scripts/test_cube_validate.py -q` Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): list unaccounted and unchecked Tableau constructs in outputs"
```

### Task 9: `grains` prints the constructs and dimension snippets

**Files:**

- Modify: `scripts/cube_validate.py` (new `_snippet`; `_grains_command`)
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Consumes: `merge_constructs` (Task 7); `Sheet.measure_aliases` (Task 4); Task
  1's ruling.
- Produces: `grains --measure` output keys `resolves_to` and `constructs` (each
  `asdict(Construct)` plus `key`, and `dimension` for groups and bins).

- [ ] **Step 1: Write the failing test**

```python
def test_grains_cli_lists_constructs_with_dimension_snippets(capsys):
    twb = str(FIX / "constructs.twb")
    assert cv.main(["grains", twb, "--dashboard", "Main", "--measure", "Absences Shown"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["resolves_to"] == ["# Absent"]
    assert cv.main(["grains", twb, "--dashboard", "Main", "--measure", "# Absent"]) == 0
    out = json.loads(capsys.readouterr().out)
    group = next(c for c in out["constructs"] if c["key"] == "group: Code Group")
    assert group["sheets"] == ["Codes"]
    assert group["dimension"] == {
        "group": {"of": "att_code", "bins": {"Absent": ["A", "AD"], "Present": [None, "P"]}},
        "kind": "relabel or rule: decide",
        "cube": None,
    }
```

- [ ] **Step 2: Run it to verify it fails**

Run:
`uv run pytest tests/scripts/test_cube_validate.py -q -k dimension_snippets`
Expected: FAIL (`KeyError: 'resolves_to'`).

- [ ] **Step 3: Implement**

Add above `_grains_command` (if Task 1 ruled "show as Other", add
`"other": "Other"` to the `group` dict):

```python
def _snippet(c: Construct) -> dict:
    """A checks-file dimension to paste for a group or bin on a plain column."""
    d = c.detail
    if c.kind == "group" and d.get("of"):
        return {
            "dimension": {
                "group": {"of": d["of"], "bins": d["bins"]},
                "kind": "relabel or rule: decide",
                "cube": None,
            }
        }
    if c.kind == "bin" and d.get("of"):
        return {"dimension": {"bin": {"of": d["of"], "size": d["size"]}, "cube": None}}
    return {}
```

Replace the `if a.measure:` branch of `_grains_command`:

```python
    if a.measure:
        using = [
            s for s in sheets if a.measure in s.measures or a.measure in s.measure_aliases
        ]
        out = {
            "measure": a.measure,
            "resolves_to": sorted(
                {s.measure_aliases.get(a.measure, a.measure) for s in using}
            ),
            "sheets": [asdict(s) for s in using],
            "grains": propose_grains(sheets, a.measure),
            "constructs": [
                dict(asdict(c), key=c.key, **_snippet(c))
                for c in merge_constructs(using)
            ],
        }
```

- [ ] **Step 4: Run the suite**

Run: `uv run pytest tests/scripts/test_cube_validate.py -q` Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): grains prints each Tableau construct with a dimension snippet"
```

### Task 10: Skill and catalog docs, lint

**Files:**

- Modify: `.claude/skills/cube-dashboard/SKILL.md`, `scripts/CLAUDE.md`

**Interfaces:**

- Consumes: everything above; Task 1's ruling.

- [ ] **Step 1: Update the skill**

In `.claude/skills/cube-dashboard/SKILL.md`:

1. In the verdict paragraph, replace `` `incomplete` (a grain errored) `` with
   `` `incomplete` (a grain errored, or a Tableau construct on the row's sheets is unaccounted) ``.
2. In _Validate a dashboard_ step 4, append:
   `A render shows aliased labels (a school id shown as its name); map a label back to its value from the column's `<aliases>`in the`.twb` before comparing.`
   In step 5, append:
   `"Unaccounted Tableau constructs" lists what the checks file must account for before the row can pass; "Not checked" lists what the check deliberately skips, with why.`
3. Replace _Author a check entry_ step 3's sentence
   `Resolve groups (`categorical-bin`columns in the`.twb`) and parameters.` with
   `` `grains` resolves field copies and expands parameter branches, drill levels and subtotals into grains. ``
4. Insert after step 4 (renumber the rest):

   ```markdown
   5. Constructs. `grains --measure` lists every construct on the measure's
      sheets under `constructs`, each with a `key`. Account for each one:
      - A group or bin: paste its `dimension` snippet, set `kind: relabel`
        (codes rolled into buckets) or `kind: rule` (a definition), and set
        `cube:` to a member whose values equal the bin labels, or leave it null.
      - A filter, set or source filter: reproduce it in `hard_filters`,
        `cube_filters` or `truth_filters`, reading its mode (exclude, nulls,
        context), not just the field name.
      - An LOD: FIXED ignores every filter except context filters; translate it
        with only those inside.
      - Then list the key under the file's `handled:` with what reproduces it.
        Anything the check cannot reproduce (table calculations, viewer
        functions, a total that sums rows) goes under the row's `not_checked:`
        with `why`. Set the file's `dashboards:` to the published dashboard
        names and each metric's `tableau:` to its caption; without them the run
        cannot audit the row and marks it `incomplete`.
   ```

5. In _Rules_, add:
   `- Never mark a construct handled that the check does not reproduce. A wrong `handled:` entry hides the gap the audit exists to show.`

- [ ] **Step 2: Update the catalog row**

In `scripts/CLAUDE.md`, in the `cube_validate.py` row, replace
``(`grains` proposes them from a `.twb`; `run` compares and writes `~/asana-sync/validation/`)``
with
``(`grains` proposes them from a `.twb` and lists the Tableau constructs on those sheets; `run` compares, marks a row incomplete when a construct is unaccounted, and writes `~/asana-sync/validation/`)``.

- [ ] **Step 3: Format, then lint every touched file**

Run:

```bash
cd /workspaces/teamster && /workspaces/teamster/.trunk/tools/trunk fmt scripts/cube_validate.py tests/scripts/test_cube_validate.py .claude/skills/cube-dashboard/SKILL.md scripts/CLAUDE.md </dev/null >/dev/null 2>&1
cd /workspaces/teamster && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix scripts/cube_validate.py tests/scripts/test_cube_validate.py .claude/skills/cube-dashboard/SKILL.md scripts/CLAUDE.md docs/superpowers/plans/2026-10-08-cube-dashboard-tableau-constructs.md </dev/null 2>&1 | tail -n 20
```

Expected: `No issues`. Fix any finding; suppress only with
`trunk-ignore(linter/rule): reason`.

- [ ] **Step 4: Run the suite**

Run: `uv run pytest tests/scripts/test_cube_validate.py -q` Expected: PASS.

- [ ] **Step 5: Commit and push**

```bash
git add .claude/skills/cube-dashboard/SKILL.md scripts/CLAUDE.md scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "docs(cube): author check entries that account for Tableau constructs"
git push
```
