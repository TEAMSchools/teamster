# Validator: DDI Run Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the 9 bugs the fresh DDI run found, show only published worksheets
and safe filter values, share explanations across a dashboard model, and add the
formula check: a differing cell that still differs once every unmatched row is
left out is a formula difference, whatever row causes it also holds.

**Architecture:** Small fixes first, grouped by module. Then published sheets
(read from the workbook XML), safe filter values and shared explanations. The
formula check lives in a new `formula.py`: it builds, for each comparison, a
dashboard-side and a Cube-side query over matched rows only (a rebuilt reconcile
minus the saved unmatched keys), plus a self-check of each with nothing removed.
`sort` prices them in the explanations' batch, runs them after the stored
explanations, stores each comparison's result in its latest result, and
recomposes `run.json`, so a checked cell is filed in `<id>:formula` by the same
code that files cells with no group. Every failure leaves the cell closing by
coverage, labelled "formulas not compared: <why>", and `ask-owner` lists it.

**Tech Stack:** Python 3.13 via `uv run`, sqlglot, `google-cloud-bigquery`,
pytest with DuckDB (`--with duckdb`).

**Spec:**
`docs/superpowers/specs/2026-11-14-validator-coverage-and-gaps-design.md`,
section "Revision 2026-11-18: after the fresh DDI run" (the authority; read the
rest for context). Background with file:line evidence:
`/tmp/claude-1000/-workspaces-teamster/b7c4309a-7aab-4478-98dc-5c70545c92ff/scratchpad/ddi-run-findings-triage.md`
(the spec wins where they differ). Issues #6410, #6415. PR #6402.

Worktree `W` =
`/workspaces/teamster/.claude/worktrees/cristinabaldor/fix/claude-validator-second-fact-time-dims`.
Package `P` = `W/scripts/cube_validation/`. Tests `T` =
`W/tests/scripts/cube_validation/`. Run every test from `W`:

```bash
uv run --with duckdb pytest tests/scripts/cube_validation/<file>::<test> -q
```

(`/home/vscode/.local/bin/uv` if `uv` is not on PATH.) Baseline before Task 1:
`uv run --with duckdb pytest tests/scripts/cube_validation/ -q` → **1358
passed**. Every task ends with the whole suite green. IDE Pyright errors on
worktree files are false positives.

## Global Constraints

- One PR, #6402. No live warehouse, Cube or Tableau command in any task; every
  test is offline (DuckDB fakes, `FakeBigQuery`, `FakeCube`, `FakeTableau`).
- No student or staff value in any output that can reach GitHub: the formula
  item's `evidence_posted`, the "formulas not compared" lines, the unpublished
  note, filter values. Counts under 10 are masked with `report.mask` wherever
  text is posted. A cell's dims and values appear only in local `evidence` and
  the terminal.
- A cell closes, or is called a formula difference, only on a computed result;
  never on a guess. Every formula-check failure falls back to coverage with a
  "formulas not compared: <why>" label; none refuses `sort`, makes a comparison
  stale, or blocks `ask-owner`.
- The formula check never spends unpriced: its queries are dry-run with the
  stored explanations before anything runs, and one cap refusal covers both.
- A validation file with none of this plan's new keys (`unpublished`,
  `rebuild_check.published`) keeps every entry and checkpoint fingerprint it has
  today, or every saved result and saved-rows table goes stale at merge and the
  #6415 re-run cannot happen (Task 7).
- Tests that touch the cache use the suite's fixtures: `test_cli.py`'s autouse
  `_cache_in_tmp`, or a copy of it in a new test module. Never star-import
  `test_cli` (it skips the autouse fixture and writes the real
  `~/.cache/cube-validation/spend.json`). Import named helpers only.
- Docstrings follow `W/src/teamster/CLAUDE.md`; comments follow
  `.claude/rules/comments.md` (the why, no measurements, no history).
- Commits: stage each file by name (never `-A`, `-u` or `.`), conventional
  commit subject, body `Refs #6410` and `Refs #6415` on separate lines, last
  line `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. If a hook
  blocks `-m`, write the message to `<session scratchpad>/commit-msg-<slug>.txt`
  and `git commit -F` it.
- Markdown (Task 17) is linted with
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  from `W`.

## Review Focus

1. A date grain: the dashboard view stores a DATE, the fact a TIMESTAMP. Keys
   must match or every cell reads "no rows both sides hold". Pinned in Task 12
   (`test_key_sql_reads_a_timestamp_and_its_date_alike`) and Task 13
   (`test_cube_side_keys_a_timestamp_grain_as_a_date`).
2. A daily dashboard with `rows.reduce`: non-latest rows were never reconciled,
   so they must not enter the dashboard's matched rows. Pinned in Task 12
   (`test_dashboard_side_keeps_only_the_latest_row_under_reduce`).
3. Rows a `dashboard_filters` entry drops while Cube keeps them: not matched, so
   they leave both sides, never read as a formula difference. Pinned in Task 12
   (`test_matched_keys_leave_out_rows_a_dashboard_filter_drops`).
4. A comparison with several cuts: each differing cell is recomputed under its
   own cut, never another's. Pinned in Task 12
   (`test_dashboard_side_tags_each_cut`) and Task 14
   (`test_verdicts_match_cells_by_cut_and_dims`).
5. An existing validation file after merge: entry and checkpoint fingerprints
   unchanged, so results and saved rows stay current. Pinned in Task 7
   (`test_new_keys_left_unset_keep_every_fingerprint`).

## Decisions the spec left to the builder

- **Published** (spec §3) is read from the workbook XML everywhere: a worksheet
  named by a `<zone>` of any `<dashboard>`, or whose
  `<window class='worksheet'>` is not `hidden='true'`. The second is exactly the
  set Tableau Server lists as views (`tableau.expose_sheet`'s docstring: a
  hidden window publishes no view), so no command reads the Server views list,
  and `read-sheet` stays offline. `rebuild-sheet` records the result as
  `rebuild_check.published`; `compare` downloads the workbook only when that is
  not `true` or the workbook was republished since.
- **Grain column detection** (Cube side): parse Cube's compiled row SQL with
  sqlglot; each grain member's projection (`` `<view>__<member>` ``) must be a
  bare column qualified by the alias of a `FROM`/`JOIN` table, all on one table.
  Which tables carry those columns comes from `Warehouse.columns` (table schema,
  a free metadata call, no query).
- **Fact reference rewrite**: on the as-of-expanded Cube SQL, each
  `` `teamster-332318.<ds>.<t>` [AS `a`] FOR SYSTEM_TIME AS OF TIMESTAMP '…' ``
  of a table to filter becomes
  `` (SELECT * FROM `teamster-332318.<ds>.<t>` FOR SYSTEM_TIME AS OF TIMESTAMP '…' WHERE <key> IN (SELECT __key FROM __matched)) AS `a` ``.
  No alias, or no reference found, is "formulas not compared".
- **Matched keys**: the reconcile's own `joined` CTE rebuilt in the query
  (`reconcile._joined`), keys of rows it files `match` with both sides present,
  minus the key of every other `joined` row, minus every saved unmatched key. A
  key is `TO_JSON_STRING(STRUCT(...))` of `reconcile._grain_keys`; a NULL
  student is never matched; a time-dimension grain column is cast to DATE before
  keying on raw tables.
- **Self-check**: the same rewritten query with the key predicate replaced by
  `TRUE` and, on the dashboard side, the original `{rows}` (no scope, reduce or
  cut restriction). It checks the wrapping reproduces the run's cell; it does
  not reference `__matched`. So 4 queries per comparison: each side matched and
  self-check, each one `UNION ALL` over the cuts holding checked cells, tagged
  `__cut`.
- **Where results live**: a comparison's completed check goes in its latest
  result (`data["formula_check"]`, with that result's fingerprint) and is
  honored by every later compose; `sort` recomposes `run.json` through
  `compose_run`, only when the run is still composed from the latest results. A
  stored check is reused while its fingerprint holds (no spend). A failure that
  stops the whole comparison is not stored, so the next `sort` retries it.
- **Formula item text**: `CellDiff.matched_only` counts the cells the check
  filed. Local evidence names each such cell (cut, dims, both recomputed
  values); posted evidence carries masked counts only. Its row groups stay their
  own items ("still listed").
- **Labels**: constants in `formula.py` (Task 12) and the refusals named in each
  task are the wording.
- **Stale or skipped comparisons** get no formula check and no label: they are
  already listed as waiting.
- **Shared explanations** key on `dashboard_view`, `rows.grain` and
  `rows.values` only; `rows.dashboard_scope` and `rows.reduce` may differ too,
  since `{unmatched}`'s columns do not depend on them.
- **Text measures** are detected as a value field on a `string` column whose
  derivation is not a count; `tableau._number` says "text" only for a value with
  no digit, so `12K` still reads as a number format.
- **`*` total rows** skip only for dims on the rows or columns shelf; `All`
  keeps today's rule for every dim.

---

### Task 1: `read-sheet` and `find-field`: COUNTD captions and non-null filters

**Files:**

- Modify: `P/read_sheet.py` (`_AGG_PREFIX`, `SheetFilter`, `_filter_lines`,
  `_sheet_lines`)
- Modify: `P/find_field.py` (`restricts`, new `null_mode`, `sheet_shape`)
- Test: `T/test_read_sheet.py`, `T/test_find_field_shape.py`

**Interfaces:**

- Produces: `find_field.null_mode(filter_el: ET.Element) -> str | None`
  (`"non-null"`, `"null"` or None); `SheetFilter.null_mode: str | None = None`.

- [ ] **Step 1: Write the failing tests**

```python
# test_read_sheet.py
def test_export_name_reads_a_countd_caption():
    assert read_sheet._export_name("Distinct count of Student Number") == "student number"

def test_measure_line_finds_a_countd_sheet_field():
    facts = read_sheet.Sheet([], [], [], [], {"COUNTD(Student Number)": {"student number"}})
    out = read_sheet._Checklist([], [])
    read_sheet._measure_line(out, _comparison(sheet_field="Distinct count of Student Number"), facts)
    assert out.before == []

def test_read_sheet_points_a_non_null_filter_at_dashboard_filters_set():
    # TWB with `<filter class='quantitative' column='[federated.0pf].[none:score:qk]'
    # included-values='non-null'/>` inserted before _ANCHOR, as _with_relative does
    _, before = read_sheet.check("v", twb, SHEET, _comparison(), MEMBERS)
    assert any("non-null values only" in b and "operator: set" in b for b in before)

# test_find_field_shape.py
NON_NULL = "<filter class='quantitative' column='[ds].[none:score:qk]' included-values='non-null'/>"

def test_a_non_null_quantitative_filter_restricts():
    assert finder.restricts(ET.fromstring(NON_NULL))
    assert finder.null_mode(ET.fromstring(NON_NULL)) == "non-null"
    assert not finder.restricts(ET.fromstring(
        "<filter class='quantitative' column='[ds].[none:score:qk]' included-values='all'/>"))

def test_sheet_shape_says_non_null_values_only():
    shape = finder.sheet_shape(_one_filter_twb(NON_NULL), "S")
    assert shape.filters == ["score: non-null values only (narrows the sheet)"]
```

`_one_filter_twb(filter_xml)` is a test helper returning
`<workbook><worksheets><worksheet name='S'><table><view>{filter_xml}</view><rows/><cols/></table></worksheet></worksheets></workbook>`.

- [ ] **Step 2: Run them to verify they fail**

Run:
`uv run --with duckdb pytest tests/scripts/cube_validation/test_read_sheet.py tests/scripts/cube_validation/test_find_field_shape.py -q -k "countd or non_null"`
Expected: FAIL (no `distinct count` alternative, `null_mode` undefined, the
filter reads "keeps all").

- [ ] **Step 3: Implement**

- `read_sheet._AGG_PREFIX`: add `distinct\s+count` to the alternation, before
  `count`.
- `find_field.null_mode`: the `included-values` attribute of a quantitative
  filter when it is `non-null` or `null`, else None. `restricts` returns True
  for a quantitative filter with a `min`/`max` child or a `null_mode`.
- `sheet_shape`: a quantitative filter with a `null_mode` reads
  `"<name>: non-null values only (narrows the sheet)"` (or `null values only`);
  one with bounds keeps "a range" until Task 10.
- `read_sheet`: set `SheetFilter.null_mode`; `_sheet_lines` shows
  `non-null values only` in place of `restricting` for it; `_filter_lines`'s
  final branch, for a filter with a `null_mode`, blocks with
  `"<caption>: keeps non-null values only; add dashboard_filters with operator: set on its column"`.

- [ ] **Step 4: Run the tests, then the whole suite**

Run the Step 2 command, then
`uv run --with duckdb pytest tests/scripts/cube_validation/ -q`. Expected: PASS;
no failures.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validation/read_sheet.py scripts/cube_validation/find_field.py tests/scripts/cube_validation/test_read_sheet.py tests/scripts/cube_validation/test_find_field_shape.py
git commit -m "fix(cube-validation): read COUNTD captions and non-null filters" -m "Refs #6410
Refs #6415" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Text measures refused up front

**Files:**

- Modify: `P/tableau.py` (`TEXT_MEASURE`, `_number`)
- Modify: `P/find_field.py` (new `text_values`)
- Modify: `P/read_sheet.py` (`Sheet.text_values`, new `text_measure`,
  `_measure_line`)
- Modify: `P/rebuild.py` (`_capture`)
- Test: `T/test_tableau.py`, `T/test_find_field_shape.py`,
  `T/test_read_sheet.py`, `T/test_cli.py`

**Interfaces:**

- Produces:
  `tableau.TEXT_MEASURE = "text measures are not compared; compare the numeric measure it is built from"`;
  `find_field.text_values(twb_xml: str, sheet: str) -> set[str]` (export names,
  lowercase, of value fields that are text);
  `read_sheet.text_measure(facts: Sheet, sheet_field: str | None) -> str | None`
  (the blocking line or None).

- [ ] **Step 1: Write the failing tests**

```python
# test_tableau.py
def test_export_number_calls_a_word_a_text_measure():
    with pytest.raises(ValueError, match="text measures are not compared"):
        tableau._number("met")

def test_export_number_still_calls_a_digit_format_a_number_format():
    with pytest.raises(ValueError, match="still carries a number format"):
        tableau._number("12K")

# test_find_field_shape.py
def test_text_values_names_a_string_attr_but_not_its_countd():
    # rows hold [attr:status:nk] and [ctd:status:qk]; <column name='[status]' datatype='string'/>
    assert finder.text_values(twb, "S") == {"status"}

# test_read_sheet.py
def test_read_sheet_refuses_a_text_sheet_field():
    facts = replace(_facts(), text_values=frozenset({"status"}))
    assert read_sheet.text_measure(facts, "Status") == f"sheet_field 'Status': {tableau.TEXT_MEASURE}"

# test_cli.py
def test_rebuild_sheet_refuses_a_text_measure_before_any_export(fakes, tmp_path, capsys):
    # comparison whose sheet_field names a string ATTR on the fake workbook
    assert main([...rebuild-sheet...]) == 1
    assert "text measures are not compared" in capsys.readouterr().err
    # FakeTableau recorded no capture (read its attributes in test_cli.py)
```

- [ ] **Step 2: Run them to verify they fail**

Run:
`uv run --with duckdb pytest tests/scripts/cube_validation/ -q -k "text_measure or text_values or calls_a_word or digit_format"`
Expected: FAIL.

- [ ] **Step 3: Implement**

- `tableau._number`: before the number-format error, raise
  `ValueError(f"export value {text!r} is text; {TEXT_MEASURE}")` when the body
  holds no digit.
- `find_field.text_values`: value refs on rows, columns and encodings
  (`is_value`) whose derivation is not `cnt`, `ctd` or `cntd` and whose workbook
  `<column>` (by bare name) has `datatype='string'`; the name is the caption
  lowercased, as `read_sheet._value_names` gives it.
- `read_sheet.read_sheet` fills
  `Sheet.text_values: frozenset[str] = frozenset()`. `text_measure` returns
  `f"sheet_field {sheet_field!r}: {TEXT_MEASURE}"` when
  `_export_name(sheet_field)` is in `text_values`, or, with no `sheet_field`,
  `f"the sheet's measure: {TEXT_MEASURE}"` when every value field is text.
  `_measure_line` adds it as a blocking item.
- `rebuild._capture`: after `set_shelves`, before `tbl.capture`, raise
  `Refusal(f"comparison {comparison.id!r}: {why}")` when
  `read_sheet.text_measure(read_sheet.read_sheet(shaped, sheet), comparison.sheet_field)`
  returns a line.

- [ ] **Step 4: Run the tests, then the whole suite** (as Task 1). Expected:
      PASS.

- [ ] **Step 5: Commit** the eight files by name:
      `fix(cube-validation): refuse text measures before the export`.

---

### Task 3: Find a comparison item by any `id:` line

**Files:**

- Modify: `P/config.py` (`write_rebuild_check`, `write_decision`, new
  `_list_item`, `comparison_item`, `find_comparison`)
- Modify: `P/rebuild.py` (`rebuild_sheet`)
- Test: `T/test_config.py`, `T/test_cli.py`

**Interfaces:**

- Produces:
  `config._list_item(lines: list[str], head: int, end: int, item_id: str) -> tuple[int, int, int] | None`
  (start, end exclusive, key indent) over one block's list items;
  `config.comparison_item(lines: list[str], comparison_id: str) -> tuple[int, int, int] | None`
  (scoped to the top-level `comparisons:` block);
  `config.find_comparison(path: Path, comparison_id: str) -> None` (raises
  `ConfigError` with today's "no comparison with id" message).

- [ ] **Step 1: Write the failing tests**

```python
# test_config.py
MERGED = """\
shared:
  roster: &roster
    workbook: wb
comparisons:
  - <<: *roster
    id: goal  # the goal sheet
    measure: m
decisions:
  - id: goal
    comparison: goal
    call: deliberate
    reason: r
    formula: true
"""

def test_write_rebuild_check_finds_a_comparison_that_opens_with_a_merge_key(tmp_path):
    path = _write(tmp_path, MERGED)
    config.write_rebuild_check(path, "goal", {"fingerprint": "f", "cells": 1, "matched_at": "t"})
    c = load_view_config(path).comparisons[0]
    assert c.rebuild_check.fingerprint == "f" and c.workbook == "wb"

def test_comparison_item_ignores_a_decision_with_the_same_id(tmp_path): ...
def test_write_decision_replaces_a_decision_whose_id_is_not_its_first_key(tmp_path): ...

# test_cli.py
def test_rebuild_sheet_refuses_an_unwritable_comparison_before_any_export(fakes, tmp_path, capsys):
    # `comparisons:` as a flow list: it loads, but no line edit can find the item
    assert main([...rebuild-sheet...]) == 1
    # FakeTableau recorded no capture
```

- [ ] **Step 2: Run them to verify they fail.** Expected: FAIL ("no comparison
      with id 'goal'").

- [ ] **Step 3: Implement**

`_list_item` walks the block's items (a line at the block's item indent starting
`- `); an item matches when its first line is `- id: <id>` or a line at its key
indent (item indent + 2) is `id: <id>`, each allowing quotes and a trailing
`# comment`. Both writers use it in place of their `- id:` scans; the decision
writer keeps its "edit it by hand" refusal only for a decision the loader reads
but no item matches (a flow list). `rebuild_sheet` calls
`find_comparison(path, comparison.id)` right after `_require`, before
`_capture`, re-raising `ConfigError` as `Refusal`.

- [ ] **Step 4: Run the tests, then the whole suite.** Expected: PASS.

- [ ] **Step 5: Commit** the four files:
      `fix(cube-validation): find a comparison item by any id line`.

---

### Task 4: Export matching: blanks, `*` totals, dual-axis repeats

**Files:**

- Modify: `P/tableau.py` (`match_export`, `RebuildResult.blanks_skipped`)
- Modify: `P/rebuild.py` (`TOTAL_LABELS`, `_export_cells`, new `_shelf_dims`,
  `_ignored_headers`, `rebuild_sheet`)
- Test: `T/test_tableau.py` (import `rebuild` there)

**Interfaces:**

- Produces: `RebuildResult.blanks_skipped: int = 0`;
  `rebuild._export_cells(comparison, rows, mapping, value, columns, probe_rows, *, shelf_dims: set[str], ignored: set[str]) -> tuple[list[dict], int, int]`;
  `rebuild._shelf_dims(comparison: Comparison, shaped: str, sheet: str, columns: list[ET.Element]) -> set[str]`;
  `rebuild._ignored_headers(headers: list[str], mapping: dict[str, str], value: str, columns: list[ET.Element], calcs: list[tableau.TableCalc]) -> set[str]`.

- [ ] **Step 1: Write the failing tests**

```python
def test_match_export_skips_export_only_blanks_and_query_only_nulls():
    exports = [{"school": "A", "value": "0.5"}, {"school": "B", "value": ""}]
    query = [{"school": "A", "value": 0.5}, {"school": "C", "value": None}]
    proof = tableau.match_export(_comparison(), exports, query, twb_xml=TWB, now=NOW)
    assert proof.matched and proof.cells == 1 and proof.blanks_skipped == 2

def test_match_export_still_fails_a_blank_against_a_value():
    # export "" vs query 0.5 on the same key -> one failure (cube_only verdict)

def test_export_cells_skips_a_star_total_row_on_a_shelf_dim():
    cells, totals, _ = rebuild._export_cells(c, [{"School": "*", "v": "9"}, {"School": "A", "v": "1"}],
        {"School": "school"}, "v", [], [{"school": "A"}], shelf_dims={"school"}, ignored=set())
    assert totals == 1 and [x["school"] for x in cells] == ["A"]

def test_export_cells_keeps_a_star_row_on_a_detail_dim(): ...          # shelf_dims=set() -> kept
def test_export_cells_keeps_a_star_row_when_the_sheet_query_has_a_real_star(): ...

def test_export_cells_drops_a_dual_axis_repeat_that_differs_only_in_a_table_calc():
    rows = [{"School": "A", "v": "1", "Rank": "1"}, {"School": "A", "v": "1", "Rank": "2"}]
    cells, _, _ = rebuild._export_cells(c, rows, {"School": "school"}, "v", [], [],
                                        shelf_dims={"school"}, ignored={"Rank"})
    assert len(cells) == 1

def test_export_cells_keeps_two_marks_that_differ_in_another_column():
    # rows differ in "Teacher" (not ignored) -> both kept, so match_export later
    # fails "more than 1 export row"
```

- [ ] **Step 2: Run them to verify they fail.** Expected: FAIL (no
      `blanks_skipped`, unexpected keyword `shelf_dims`).

- [ ] **Step 3: Implement**

- `match_export`: an export-only key whose `_number` value is None, and a
  sheet-query-only key whose value is None, are skipped and counted in
  `blanks_skipped`, not in `cells`. Docstring says so.
- `rebuild.TOTAL_LABELS = ("All", "*")`. `_export_cells` skips a row whose dim
  reads `All` (any dim) or `*` (a dim in `shelf_dims` only), unless the probe
  has a real member with that label for that dim; both count in `totals`. The
  dedupe key is every column but `ignored`, so a repeat that differs only in an
  ignored column is dropped (not with `split_rows: sum`, as today). Update the
  docstring.
- `_shelf_dims`: the dims whose dashboard name, column caption or `filters`
  caption appears in `finder.sheet_shape(shaped, sheet).rows + .cols`.
- `_ignored_headers`: headers other than the mapped dims and `value` whose
  `read_sheet._export_name` equals a `role='measure'` column's caption or bare
  name, or a table calc's caption, lowercased.
- `rebuild_sheet`: compute both per cut (calcs via `tableau.table_calcs` on the
  shaped worksheet) and print
  `"Skipped {n} blank cells (blank in the export, NULL in the sheet query)"`
  when `proof.blanks_skipped`.

- [ ] **Step 4: Run the tests, then the whole suite.** Expected: PASS.

- [ ] **Step 5: Commit** the three files:
      `fix(cube-validation): skip blank cells, star totals and dual-axis repeats`.

---

### Task 5: `{unmatched}` carries the dashboard's cell

**Files:**

- Modify: `P/explain.py` (`unmatched_sql`, module docstring, `unmatched_sql`
  docstring)
- Test: `T/test_explain.py`

**Interfaces:**

- Produces: `unmatched_sql`'s SELECT adds `__moved` and `__d_<column>` per
  group-by column when the comparison has group-by dims.

- [ ] **Step 1: Write the failing test**

```python
def test_unmatched_carries_moved_and_the_dashboard_cell(duck, tmp_path, offline):
    _tables(duck)
    run = _run([_group(3, bucket="dims_differ")])
    wh = _saved_wh(duck, run)
    table = explain.require_saved(wh, CFG, run, COMPARISON)
    ctes, select = explain.unmatched_sql(COMPARISON, "dims_differ", [], table)
    assert "__moved" in select and "__d_abbreviation" in select
    rows = duck.rows(f"{ctes}\nSELECT COALESCE(u.__d_abbreviation, u.abbreviation) AS d FROM ({select}) AS u")
    assert isinstance(rows, list)
```

- [ ] **Step 2: Run it to verify it fails.** Expected: FAIL (`__moved` not in
      the SELECT).

- [ ] **Step 3: Implement.** Add the columns after the group-by columns. Both
      docstrings say `__d_<column>` is NULL unless that column differs between
      the sides, so an explanation reads `COALESCE(u.__d_x, u.x)` for the
      dashboard's value. Check `explanation_query` and `_with_students` select
      no column of the same name.

- [ ] **Step 4: Run it, then the whole suite.** Expected: PASS.

- [ ] **Step 5: Commit** both files:
      `fix(cube-validation): give an explanation the dashboard's cell`.

---

### Task 6: Pre-aggregation refusal names the remedy

**Files:**

- Modify: `P/cube_client.py` (`refuse_unless_safe`)
- Modify: `P/compare.py` (`_say_skips`)
- Test: `T/test_cube_client.py`, `T/test_cli.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_pre_aggregation_refusal_names_the_scope_remedy():
    with pytest.raises(CubeRefusal) as exc:
        refuse_unless_safe(_compiled(pre_aggregations=[{"id": "r"}]), view_fact="m.fct", network_schools=set())
    text = str(exc.value)
    assert "scope" in text and "operator: set" in text and "primary key" in text
    assert not text.endswith(".")

def test_skip_lines_never_end_in_a_doubled_period(capsys):
    compare._say_skips([Skip("a", "why.")])
    assert capsys.readouterr().out == "Skipping a: why.\n"
```

- [ ] **Step 2: Run them to verify they fail.**

- [ ] **Step 3: Implement.** Refusal text:
      `"Cube served this from a pre-aggregation, stored data rather than the fact the view reads; add a Cube-only `scope`on a never-null member the rollup does not carry, such as the fact's primary key, with`operator:
      set`"`. `_say_skips` prints `s.why.rstrip(".")` + `"."`.

- [ ] **Step 4: Run them, then the whole suite.** Expected: PASS.

- [ ] **Step 5: Commit** the four files:
      `fix(cube-validation): name the pre-aggregation remedy`.

---

### Task 7: Published worksheets: read, mark, refuse, record

**Files:**

- Modify: `P/tableau.py` (new `published_sheets`, `NOT_PUBLISHED`)
- Modify: `P/config.py` (`Comparison.unpublished`, `RebuildCheck.published`, new
  `fingerprint_data`)
- Modify: `P/latest.py` (`entry_fingerprint`), `P/pipeline.py`
  (`checkpoint_fingerprint`, `_print_sheets`)
- Modify: `P/read_sheet.py` (`Sheet.published`, `_sheet_lines`, `check`)
- Modify: `P/rebuild.py` (`_capture`, `rebuild_sheet`)
- Test: `T/test_tableau.py`, `T/test_config.py`, `T/test_read_sheet.py`,
  `T/test_cli.py`

**Interfaces:**

- Produces: `tableau.published_sheets(twb_xml: str) -> set[str]`;
  `tableau.NOT_PUBLISHED = "not on a published dashboard"`;
  `Comparison.unpublished: bool = False`;
  `RebuildCheck.published: bool | None = None` (None: the check predates it);
  `config.fingerprint_data(comparison: Comparison) -> dict` (what both
  fingerprints hash).

- [ ] **Step 1: Capture today's fingerprints.** Before any edit, run the current
      code on a fixture comparison with a rebuild check and every field set as
      an existing DDI file sets it, and paste the two hex digests
      (`latest.entry_fingerprint(c)`,
      `pipeline.checkpoint_fingerprint(c, {"cube": "x", "dashboard": "y"})`)
      into the test below as golden values.

- [ ] **Step 2: Write the failing tests**

```python
# test_config.py
def test_new_keys_left_unset_keep_every_fingerprint():
    assert latest.entry_fingerprint(FIXTURE) == "<golden 1>"
    assert pipeline.checkpoint_fingerprint(FIXTURE, {"cube": "x", "dashboard": "y"}) == "<golden 2>"

def test_unpublished_and_published_load(tmp_path):
    # `unpublished: true` and `rebuild_check.published: false` read back; a
    # non-boolean is refused

# test_tableau.py
def test_published_sheets_reads_dashboard_zones_and_visible_windows():
    # zone name='A' in a dashboard; window class='worksheet' name='B' (no hidden);
    # window name='C' hidden='true' and in no zone
    assert tableau.published_sheets(xml) == {"A", "B"}

# test_read_sheet.py
def test_read_sheet_marks_and_blocks_an_unpublished_sheet(): ...
def test_read_sheet_lets_an_opted_in_unpublished_sheet_through(): ...

# test_cli.py
def test_rebuild_sheet_refuses_an_unpublished_sheet_before_any_export(fakes, tmp_path, capsys): ...
def test_rebuild_sheet_records_published(fakes, tmp_path): ...  # rebuild_check.published is True
def test_find_field_marks_an_unpublished_sheet(fakes, tmp_path, capsys): ...
```

- [ ] **Step 3: Run them to verify they fail** (except the golden test, which
      passes now and must keep passing).

- [ ] **Step 4: Implement**

- `published_sheets`: names in any `<dashboard>`'s `<zone name=…>` (zones nest;
  take every one) plus every `<window class='worksheet' name=…>` without
  `hidden='true'`. Docstring gives the reason (a hidden window publishes no
  view).
- `config.fingerprint_data`: `asdict` of the comparison with `definitions`
  emptied, then `unpublished` dropped when False and `rebuild_check.published`
  dropped when None. `latest.entry_fingerprint` and
  `pipeline.checkpoint_fingerprint` hash it in place of their own `asdict`.
- Read `unpublished` with `reader.get("unpublished", bool, default=False)` and
  `published` with `check_reader.get("published", bool)`; add `unpublished`
  wherever the loader lists comparison keys.
- `read_sheet.read_sheet` sets `Sheet.published: bool = True` from
  `published_sheets`. `_sheet_lines`'s header adds
  `; not on a published dashboard`. `check` adds the blocking item
  `"sheet: not on a published dashboard; set unpublished: true to compare it anyway"`
  for a comparison without `unpublished`.
- `pipeline._print_sheets` prints `"    not on a published dashboard"` for such
  a sheet.
- `rebuild._capture`, after downloading: refuse
  `f"comparison {id!r}: sheet {sheet!r} is {NOT_PUBLISHED}; set unpublished: true to compare it anyway"`
  unless `comparison.unpublished`. `rebuild_sheet` writes
  `"published": sheet in published_sheets(twb)`.

- [ ] **Step 5: Run the tests, then the whole suite.** Expected: PASS, golden
      digests unchanged.

- [ ] **Step 6: Commit** the ten files:
      `feat(cube-validation): validate only published worksheets`.

---

### Task 8: `compare` skips unpublished sheets; the owner sees the opt-in

**Files:**

- Modify: `P/rebuild.py` (new `unpublished_sheets`)
- Modify: `P/compare.py` (`_early_skips`)
- Modify: `P/report.py` (`render_review_issue`), `P/review.py` (`ask_owner`)
- Test: `T/test_cli.py`, `T/test_report.py`

**Interfaces:**

- Consumes: Task 7's `published_sheets`, `RebuildCheck.published`,
  `Comparison.unpublished`.
- Produces:
  `rebuild.unpublished_sheets(comparisons: list[Comparison], *, tbl: tableau.Tableau) -> dict[str, str]`
  (comparison id to skip reason);
  `render_review_issue(..., unpublished: dict[str, set[str]] | None = None)`.

- [ ] **Step 1: Write the failing tests**

```python
def test_compare_skips_a_sheet_on_no_published_dashboard(fakes, tmp_path, capsys):
    # rebuild_check without `published`; the fake workbook hides the sheet
    assert "Skipping c1: not on a published dashboard; set unpublished: true" in capsys.readouterr().out

def test_compare_downloads_no_workbook_for_a_check_that_recorded_published(fakes, tmp_path): ...
def test_compare_checks_again_after_a_republish(fakes, tmp_path): ...
def test_compare_runs_an_opted_in_unpublished_sheet(fakes, tmp_path): ...

# test_report.py
def test_review_question_says_its_sheet_is_on_no_published_dashboard():
    body = report.render_review_issue("Registrar", runs, ..., unpublished={"v": {"c1"}})
    assert "`c1`'s sheet is on no published dashboard" in body
```

- [ ] **Step 2: Run them to verify they fail.**

- [ ] **Step 3: Implement**

`unpublished_sheets` skips opted-in comparisons; downloads each workbook once
(per luid) when one of its comparisons has `published` not True or
`tbl.workbook_updated(luid)` is after its check's `workbook_updated_at`; returns
`"not on a published dashboard; set unpublished: true to compare it anyway"` for
a sheet outside `published_sheets`, and
`f"the workbook could not be checked: {TABLEAU_ANSWERED} {code} {summary}"` on
`TSC.ServerResponseError`. `_early_skips` runs it on what is left after
`workbook_check`. `render_review_issue` ends each question line naming an
`unpublished` comparison (per `defined_comparisons([q], view)`) with
``Note: `<id>`'s sheet is on no published dashboard.``; `ask_owner` passes
`{cfg.view: {c.id for c in cfg.comparisons if c.unpublished}}`.

- [ ] **Step 4: Run the tests, then the whole suite.** Expected: PASS.

- [ ] **Step 5: Commit** the six files:
      `feat(cube-validation): skip unpublished sheets in compare`.

---

### Task 9: Safe filter values

**Files:**

- Modify: `P/find_field.py` (`SHOWN_FILTER_FIELDS`, new `columns_read`,
  `shown_values`, `sheet_shape`)
- Modify: `P/read_sheet.py` (filter `columns` via `columns_read`,
  `SheetFilter.shown`, `_sheet_lines`, module docstring)
- Test: `T/test_find_field_shape.py`, `T/test_read_sheet.py`

**Interfaces:**

- Produces:
  `find_field.columns_read(name: str, formulas: dict[str, str]) -> tuple[str, ...]`
  (the datasource columns `name` reads through calculations, parameters left
  out; `name` itself when it is no calc);
  `find_field.shown_values(filter_el: ET.Element, field_name: str, formulas: dict[str, str]) -> str | None`
  (None when hidden); `SheetFilter.shown: str = ""`.

- [ ] **Step 1: Write the failing tests**

```python
def test_shown_values_lists_chosen_members_of_an_allowlisted_field():
    # categorical union on response_type -> "Overall, Growth"; except -> "all except Overall"

def test_shown_values_gives_a_quantitative_filter_s_bounds_and_mode():
    # is_normed_scope min 1 max 1 -> "from 1 to 1"; non-null -> "non-null values only"

def test_shown_values_hides_a_field_off_the_allowlist():
    assert finder.shown_values(el_on_student_number, "student_number", {}) is None

def test_a_calc_filter_shows_only_when_every_column_it_reads_is_allowlisted():
    formulas = {"Calculation_1": "[module_type] = 'WPP' AND [region] = 'Newark'",
                "Calculation_2": "[student_number] > 0"}
    assert finder.shown_values(el_calc1, "Calculation_1", formulas) is not None
    assert finder.shown_values(el_calc2, "Calculation_2", formulas) is None

def test_read_sheet_shows_an_allowlisted_filter_s_values(): ...
```

- [ ] **Step 2: Run them to verify they fail.**

- [ ] **Step 3: Implement**

Add `response_type`, `module_type` and `is_normed_scope` to
`SHOWN_FILTER_FIELDS`. `columns_read` is `read_sheet.read_sheet`'s `reads`
closure moved out (recursion through calcs, bracketed names that are no calc and
not `Parameters`); `read_sheet` uses it for `SheetFilter.columns`.
`shown_values` returns None unless `field_name` is allowlisted, or is a calc
whose `columns_read` are all allowlisted; categorical members as today
(`all except …` for `function='except'`); quantitative `from <min> to <max>`,
`from <min>`, `up to <max>`, or the `null_mode` words. `sheet_shape` builds
`formulas` as `read_sheet` does and prints
`"<name>: <shown> (narrows the sheet)"`, keeping the hidden wording otherwise.
`read_sheet._sheet_lines` appends `; shows <shown>` for a restricting filter.
Both docstrings say values print only for allowlisted fields.

- [ ] **Step 4: Run the tests, then the whole suite.** Expected: PASS.

- [ ] **Step 5: Commit** the four files:
      `feat(cube-validation): show filter values that cannot identify a person`.

---

### Task 10: Share an explanation across a dashboard model

**Files:**

- Modify: `P/config.py` (`row_population` and `_POPULATION` become
  `explanation_key`)
- Modify: `P/explain.py` (import, `siblings` docstring, the `explain` "Also"
  line)
- Test: `T/test_explain.py`, `T/test_cli.py` (rewrite
  `test_dashboard_columns_change_the_row_population`)

**Interfaces:**

- Produces: `config.explanation_key(comparison: Comparison) -> str | None` (None
  without `rows`): JSON of `dashboard_view`, `rows.grain`, `rows.values`.

- [ ] **Step 1: Write the failing tests**

```python
def test_comparisons_on_one_model_and_grain_share_an_explanation():
    other = replace(COMPARISON, id="b", filters={...}, defaults={...}, scope=[...],
                    cuts=[{}], dashboard_columns={"x": "1"})
    assert explain.siblings(ViewConfig("v", "m.fct", [COMPARISON, other]), COMPARISON) == [other]

def test_another_grain_or_model_does_not_share():
    # rows.values differ -> no; dashboard_view differs -> no; rows None -> key None

def test_a_shared_explanation_runs_on_each_comparison_s_own_rows(duck, tmp_path, offline):
    # sibling with different `filters`: the outcome counts its own saved rows;
    # a row it lacks the explanation covers falls to UNEXPLAINED
```

In `test_cli.py`, replace the dashboard-columns test with
`test_dashboard_columns_do_not_change_the_explanation_key` and update any
`"(same rows)"` assertion to the new `explain` line.

- [ ] **Step 2: Run them to verify they fail.**

- [ ] **Step 3: Implement.** `explain` prints
      `f"Also {sibling}: {n} of {len(r.found)} items explained."` and
      `f"Also {sibling}: not run; see above."`.

- [ ] **Step 4: Run the tests, then the whole suite.** Expected: PASS.

- [ ] **Step 5: Commit** the four files:
      `feat(cube-validation): share explanations across a dashboard model`.

---

### Task 11: Formula check, part 1: matched keys

**Files:**

- Create: `P/formula.py`
- Test: Create `T/test_formula.py` (with its own autouse `_cache_in_tmp`, copied
  from `test_cli.py`; import named helpers from `test_explain.py` only)

**Interfaces:**

- Consumes: `pipeline.reconcile_args`, `reconcile._joined`,
  `reconcile._grain_keys`, `pipeline.RowSides`.
- Produces in `formula.py`:
  - `NOT_COMPARED = "formulas not compared"`; `class NotCompared(Exception)`
    (its text is a fixed reason); reasons
    `REWRITE_DIFFERS = "the rewrite does not reproduce the run's cells"`,
    `NO_ROWS = "no rows both sides hold"`,
    `SAVED_GONE = "its saved rows are gone or of another run; compare it again"`,
    `SQL_MOVED = "its SQL changed since the run; compare it again"`,
    `CUBE_REFUSED = "Cube refused its SQL; sort again"`,
    `NOT_COMPOSED = "the run is not composed from the latest results; compare it again"`,
    `OUTSIDE = "not run: outside --comparison; sort it"`.
  - `key_sql(columns: list[str], dates: list[bool]) -> str`: the key of one row;
    NULL when the first column's key is NULL.
  - `matched_ctes(cfg: ViewConfig, comparison: Comparison, sides: pipeline.RowSides, saved_table: str) -> str`:
    a `WITH` prefix ending in `__matched AS (SELECT __key …)`, no final SELECT.

- [ ] **Step 1: Write the failing tests** (DuckDB; toy tables and a `RowSides`
      like `test_explain.SIDES`, saved rows via `compare.save_script`)

```python
def test_matched_keys_leave_out_every_unmatched_and_one_sided_key(duck): ...
    # 4 students: 1 match, 1 cube_only, 1 value_differs, 1 duplicate on one side
    # -> __matched holds only the match
def test_matched_keys_leave_out_a_key_with_any_unmatched_duplicate(duck): ...
def test_matched_keys_never_hold_a_null_student(duck): ...
def test_matched_keys_leave_out_rows_a_dashboard_filter_drops(duck): ...
def test_matched_keys_leave_out_a_saved_unmatched_key_the_rebuild_misses(duck): ...
    # saved table holds a key the rebuilt join files `match` -> left out
def test_key_sql_reads_a_timestamp_and_its_date_alike(duck):
    assert duck.rows(f"SELECT {formula.key_sql(['t'], [True])} = {formula.key_sql(['d'], [False])} AS same "
                     "FROM (SELECT TIMESTAMP '2026-01-05 00:00:00' AS t, DATE '2026-01-05' AS d)")[0]["same"]
```

- [ ] **Step 2: Run them to verify they fail.** Expected: FAIL (no module
      `formula`).

- [ ] **Step 3: Implement**

`key_sql` wraps each date column in `DATE()`, applies `reconcile._grain_keys`,
and returns `IF(<k0> IS NULL, NULL, TO_JSON_STRING(STRUCT(<k0> AS k0, …)))`.
`matched_ctes` builds
`reconcile._joined(*args, keys=True, moved=True, **kwargs)` from
`pipeline.reconcile_args`, then:

```sql
__match AS (SELECT <key over __k*> AS __key FROM joined
            WHERE bucket = 'match' AND __cin IS NOT NULL AND __din IS NOT NULL),
__other AS (SELECT <key over __k*> FROM joined
            WHERE NOT (bucket = 'match' AND __cin IS NOT NULL AND __din IS NOT NULL)),
__saved AS (SELECT <key over __gd*> FROM <saved> WHERE bucket != 'cube_only'
            UNION DISTINCT
            SELECT <key over __gc*> FROM <saved> WHERE bucket != 'dashboard_only'),
__matched AS (SELECT __key FROM __match WHERE __key IS NOT NULL
              EXCEPT DISTINCT SELECT * FROM __other
              EXCEPT DISTINCT SELECT * FROM __saved)
```

The `__k*` columns are already keys: key them with `TO_JSON_STRING(STRUCT(…))`
directly, not `key_sql` again. The module docstring states the rule (matched =
rows the reconcile matched, minus every saved unmatched key).

- [ ] **Step 4: Run them, then the whole suite.** Expected: PASS.

- [ ] **Step 5: Commit** both files:
      `feat(cube-validation): build the formula check's matched keys`.

---

### Task 12: Formula check, part 2: the dashboard side and its self-check

**Files:**

- Modify: `P/pipeline.py` (`sheet_query` gains `rows`; new
  `dashboard_scoped_rows_sql`; `dashboard_rows_sql` shares its WHERE and
  ranking)
- Modify: `P/formula.py`
- Test: `T/test_formula.py`, `T/test_pipeline_slices.py`

**Interfaces:**

- Produces:
  - `pipeline.sheet_query(cfg, comparison, cut, with_filters=True, rows: str | None = None) -> str`
    (`rows` replaces `SELECT * FROM <dashboard_ref>`; unchanged when None, so
    `sheet_query_fingerprint` does not move).
  - `pipeline.dashboard_scoped_rows_sql(cfg: ViewConfig, comparison: Comparison) -> str`:
    every column of the dashboard rows the reconcile reads (any cut without
    `dashboard_filters`, `rows.dashboard_scope`, `rows.reduce`).
  - `formula.dashboard_side_sql(cfg, comparison, cuts: list[dict], build: Build, wh, *, keep: bool) -> str`:
    `UNION ALL` over `cuts` of
    `SELECT <lit(cut_label)> AS __cut, * FROM (<sheet query as of build.start>)`.
    `keep=True` reads `{rows}` as
    `SELECT * FROM (<dashboard_scoped_rows_sql>) WHERE <key_sql(dash grain, dates)> IN (SELECT __key FROM __matched)`;
    `keep=False` as `SELECT * FROM (SELECT * FROM <dashboard_ref>) WHERE TRUE`.

- [ ] **Step 1: Write the failing tests**

```python
def test_sheet_query_takes_other_rows_and_keeps_its_fingerprint(): ...
def test_dashboard_side_recomputes_a_cell_on_matched_rows_only(duck):
    # school X: 2 matched students (0.5, 1.0) + 1 cube_only; AVG on matched = 0.75
def test_dashboard_side_keeps_only_the_latest_row_under_reduce(duck): ...
def test_dashboard_side_leaves_out_rows_outside_dashboard_scope(duck): ...
def test_dashboard_side_tags_each_cut(duck):
    # cuts [{}, {"Region": "Miami"}] -> rows carry both __cut labels, each with its own value
def test_dashboard_self_check_reproduces_the_sheet_query(duck):
    # keep=False equals running sheet_query per cut
```

- [ ] **Step 2: Run them to verify they fail.**

- [ ] **Step 3: Implement.** `dashboard_scoped_rows_sql` is
      `SELECT * FROM <dashboard_ref> WHERE <any cut, no filters> AND <dashboard_scope>`,
      with `rows.reduce` as `dashboard_rows_sql` ranks it; its kept-first order
      reads the filters inline (`COALESCE(<filter sql>, FALSE) AND …`) since the
      `__df` flags are not columns here. The keep variant is wrapped by the
      caller (Task 15) as `f"{matched_ctes}\nSELECT * FROM (\n{body}\n)"`; the
      self-check runs bare.

- [ ] **Step 4: Run them, then the whole suite.** Expected: PASS.

- [ ] **Step 5: Commit** the four files:
      `feat(cube-validation): recompute the dashboard's cells on matched rows`.

---

### Task 13: Formula check, part 3: the Cube side, its tables and self-check

**Files:**

- Modify: `P/bq.py` (`Warehouse.columns`)
- Modify: `P/formula.py`
- Test: `T/test_bq.py`, `T/test_formula.py`

**Interfaces:**

- Produces:
  - `Warehouse.columns(dataset: str, name: str) -> set[str]`: the table's schema
    field names (`_get_table(...).schema`; no query).
  - `formula.fact_grain(compiled_rows_sql: str, view: str, grain: list[str]) -> tuple[str, list[str]]`:
    the `dataset.table` the grain sits on and its column per grain member;
    raises
    `NotCompared(f"grain column {m} is an expression, not a fact column")` or
    `NotCompared("the grain columns sit on more than one table")`.
  - `formula.filtered_tables(read: list[str], columns: list[str], columns_of: Callable[[str], set[str]]) -> list[str]`:
    the tables of `read` carrying every grain column; raises
    `NotCompared("no table Cube reads carries the grain columns")` when none.
  - `formula.rewrite_cube_sql(sql: str, tables: list[str], columns: list[str], dates: list[bool], *, keep: bool) -> str`;
    raises `NotCompared(f"Cube's SQL reads {t} with no alias")` or
    `NotCompared(f"Cube's SQL does not read {t}")`.
  - `formula.cube_side_sql(cfg, comparison, cuts, build, *, ex: pipeline.Expand, sides: pipeline.RowSides, tables: list[str], columns: list[str], keep: bool) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
def test_columns_reads_the_schema_without_a_query(): ...  # fake client with schema; no query() call
def test_fact_grain_maps_each_member_to_its_fact_column():
    sql = "SELECT `f`.student_number `v__student`, `f`.item_id `v__item` FROM kipptaf_marts.fct_x AS `f`"
    assert formula.fact_grain(sql, "v", ["student", "item"]) == ("kipptaf_marts.fct_x", ["student_number", "item_id"])
def test_fact_grain_refuses_an_expression(): ...       # CAST(`f`.a AS STRING) `v__student`
def test_fact_grain_refuses_a_subquery_alias(): ...
def test_filtered_tables_skips_a_goals_lookup():
    cols = {"m.fct": {"student_number", "item_id"}, "m.fct_goals": {"school", "grade"}}
    assert formula.filtered_tables(["m.fct", "m.fct_goals"], ["student_number", "item_id"], cols.__getitem__) == ["m.fct"]
def test_rewrite_wraps_every_reference_of_each_table(): ...
def test_rewrite_refuses_a_reference_with_no_alias(): ...
def test_cube_side_recomputes_on_matched_rows_and_self_checks(duck): ...
def test_cube_side_keys_a_timestamp_grain_as_a_date(duck): ...
```

- [ ] **Step 2: Run them to verify they fail.**

- [ ] **Step 3: Implement.** `fact_grain` parses with
      `sqlglot.parse_one(sql, read="bigquery")`, reads the outermost SELECT's
      projections and its `FROM`/`JOIN` aliases. `rewrite_cube_sql` matches, per
      table,
      ``re.escape(f"`{PROJECT}.{t}`") + r"(?P<alias>\s+AS\s+`?\w+`?)?\s+FOR SYSTEM_TIME AS OF TIMESTAMP '(?P<at>[^']+)'"``
      and writes the filtered subquery with the alias after it (predicate `TRUE`
      when `keep` is False). `cube_side_sql`, per cut:
      `ex.at(ex.cube_sql(cell_query(view, comparison, cut)), build.end)`,
      `timetravel.repin` of its tables shared with `sides.dashboard.tables` to
      `build.start` (one query reads each table at one moment), the rewrite,
      `pipeline.wrap_cube(..., comparison.measure)`, then the `__cut` tag and
      `UNION ALL`. Tables `read` are `cfg.fact` and each `cfg.also_facts` entry
      that `cube_client._FACT_REF` finds in Cube's compiled cell SQL.

- [ ] **Step 4: Run them, then the whole suite.** Expected: PASS.

- [ ] **Step 5: Commit** the four files:
      `feat(cube-validation): recompute Cube's cells on matched rows`.

---

### Task 14: Formula check, part 4: verdicts and filing

**Files:**

- Modify: `P/formula.py` (`Check`, `verdicts`)
- Modify: `P/reconcile.py` (`CellDiff.matched_only`)
- Modify: `P/results.py` (`_cell_diffs`, `compose_run`, new `recompose`)
- Modify: `P/latest.py` (new `add_formula_check`)
- Modify: `P/sort.py` (`suggest`'s formula evidence, new `MATCHED_LABEL`)
- Test: `T/test_formula.py`, `T/test_sort.py`

**Interfaces:**

- Produces:
  - `formula.Check` (dataclass): `comparison: str`, `fingerprint: str`,
    `formula: list[tuple[str, str]]`, `coverage: list[tuple[str, str]]` (cells
    as `(cut, key)` from `run.diff_cells`),
    `not_compared: dict[str, list[tuple[str, str]]]` (reason to cells),
    `lines: list[str]` (local only); `to_json() -> dict`,
    `from_json(data: dict) -> Check`.
  - `formula.verdicts(comparison: Comparison, fingerprint: str, cells: list[dict], dash: list[dict], cube: list[dict], dash_self: list[dict], cube_self: list[dict]) -> Check`
    (pure).
  - `CellDiff.matched_only: int = 0`.
  - `latest.add_formula_check(results: Path, comparison_id: str, check: dict) -> None`
    (sets `data["formula_check"]`, writes the whole file).
  - `results.recompose(cfg: ViewConfig, cache_root: Path, run: RunResult, run_json: Path, *, cube: Cube) -> RunResult`;
    `compose_run(..., echo: bool = True)`.
  - `sort.MATCHED_LABEL = "differing cells differ on matched rows"`.

- [ ] **Step 1: Write the failing tests**

```python
def test_verdicts_file_a_cell_that_still_differs_as_formula(): ...
def test_verdicts_leave_an_agreeing_cell_to_coverage(): ...
def test_verdicts_match_cells_by_cut_and_dims(): ...       # same dims, 2 cuts, opposite outcomes
def test_verdicts_say_the_rewrite_differs_when_a_self_check_misses():
    # dash_self 0.5 vs cell dashboard 0.6 at decimals 2 -> not_compared[REWRITE_DIFFERS]
def test_verdicts_say_no_rows_when_both_sides_are_empty(): ...
def test_compose_files_checked_cells_as_formula(tmp_path):
    # a latest result with a cell holding a group and data["formula_check"]
    # naming it -> run.json: kind "formula", CellDiff(kind="formula", matched_only=1)
def test_compose_ignores_a_check_of_another_result(tmp_path): ...  # fingerprint differs
def test_recompose_refuses_when_the_latest_results_moved_on(tmp_path): ...
def test_formula_evidence_counts_matched_row_cells_masked():   # test_sort.py
    # matched_only=3 -> evidence "3 differing cells differ on matched rows: …",
    # evidence_posted "<10 …"; a cell's dims only in local evidence
```

- [ ] **Step 2: Run them to verify they fail.**

- [ ] **Step 3: Implement**

- `verdicts` keys rows by `(__cut, tuple(value_key(row[d]) …))` (dashboard names
  on the dashboard rows, Cube names on Cube's), as `compare._cells` does, and
  decides each cell in this order: either self-check value fails
  `cell_verdict(self, cell[side], decimals) == "pass"` → `REWRITE_DIFFERS`; both
  matched values None → `NO_ROWS`; `cell_verdict(dash, cube, decimals)` `pass` →
  coverage; else formula, with a local line naming the cut, dims and both
  values.
- `_cell_diffs` takes `checks: dict[str, set[tuple[str, str]]]` (default empty):
  a differing cell with groups whose `(cut, key)` is in its comparison's set
  joins the formula diff. The formula diff's first causes are
  `f"{n} differing cells hold no unmatched row"` (as today, when any) and
  `f"{m} {MATCHED_LABEL} only"` (when any); `matched_only=m`. `compose_run`
  builds `checks` from each result's `data["formula_check"]` whose `fingerprint`
  equals that result's `fingerprint`, and prints the report only when `echo`.
- `recompose`: `Refusal("the run is not composed from the latest results")` (its
  own words: `results` must not import `formula`, which imports `explain`, which
  imports `results`) unless
  `composed_from(json.loads(run_json.read_text()), confirmed, latest.read_all(...))`;
  else `compose_run` with the saved run's `cube_host`, `totals`, `moment`,
  folder `run_json.parent`, `cost_usd`, `skipped` (as `Skip`s), `compared=()`,
  `echo=False`.
- `suggest` (formula item): one evidence line per origin, local exact, posted
  masked; for `matched_only`, a local line per formula cell (cut and dims from
  `run.diff_cells`); the cause label is `MATCHED_LABEL` when `matched_only` > 0,
  else `FORMULA_LABEL` (unchanged output for today's runs).

- [ ] **Step 4: Run them, then the whole suite.** Expected: PASS.

- [ ] **Step 5: Commit** the seven files:
      `feat(cube-validation): file cells that differ on matched rows as formula`.

---

### Task 15: Formula check, part 5: run it in `sort`

**Files:**

- Modify: `P/formula.py` (`Job`, `checkable_cells`, `plan`, `run_job`, `label`)
- Modify: `P/explain.py` (`run_stored` gains `also_usd`)
- Modify: `P/sort.py` (`sort_run`)
- Test: `T/test_formula.py`, `T/test_cli.py`

**Interfaces:**

- Consumes: Tasks 11-14; `explain.require_saved`, `explain._CANNOT_RUN`,
  `trace._dry_runs`, `trace.Prepared`, `bq.job_failure`.
- Produces:
  - `formula.Job` (dataclass): `comparison: str`, `fingerprint: str`,
    `cells: list[dict]`, `sql: dict[str, str]` (keys `dashboard`, `cube`,
    `dashboard_self`, `cube_self`).
  - `formula.checkable_cells(run: RunResult, comparison: Comparison) -> list[dict]`:
    the comparison's `kind: cells` entries of `run.diff_cells` that
    `coverage.placed` places (not None) with at least one group, over
    `run.applied.open` plus the groups in `run.applied.quiet`.
  - `formula.plan(cfg, run, comparison, *, fingerprint: str, wh, cube, prepared: trace.Prepared) -> Job | Check | None`
    (None: no checkable cell; a `Check` with every cell not compared on any
    failure, mapped to the fixed reasons of Task 11, a BigQuery error as
    `f"BigQuery refused it ({job_failure(exc)}); sort again"`).
  - `formula.run_job(job: Job, comparison: Comparison, wh) -> Check` (any
    `GoogleAPIError` or `CostCapError` → every cell not compared, the second as
    `"a cap stopped it; sort again with a higher --max-usd"`).
  - `formula.label(items: list[dict], checks: dict[str, Check]) -> dict[str, dict[str, int]]`:
    prepends to each `<id>:cells` item
    `f"{NOT_COMPARED}: {why} ({n} cells closed by coverage only)"` (posted with
    `mask(n)`); returns `{comparison: {why: n}}` for `triage.json`.
  - `explain.run_stored(..., also_usd: float = 0.0)`: refuses past the caps on
    its explanations plus `also_usd`.

- [ ] **Step 1: Write the failing tests**

```python
def test_plan_builds_four_priced_queries(duck, offline): ...
def test_plan_says_compare_again_when_the_saved_rows_are_gone(duck, offline):
    # labels missing -> Check.not_compared == {SAVED_GONE: [all cells]}
def test_plan_falls_back_when_the_grain_is_an_expression(duck, offline): ...
def test_run_job_falls_back_on_a_bigquery_error_with_its_job_only(): ...  # no message text
def test_label_discloses_unchecked_cells_masked(): ...
# test_cli.py
def test_sort_prices_the_formula_check_with_the_explanations(fakes, tmp_path, capsys):
    # "Formula check: 4 queries, $… (dry run)." printed; a cap below the
    # explanations + formula total refuses before any query runs
def test_sort_files_a_decided_cell_whose_formulas_differ_as_formula(fakes, tmp_path):
    # the DDI goal shape: a cell holding a decided row group, recomputed values
    # still differ -> triage item `<id>:formula`, cells item no longer holds it
def test_sort_reuses_a_stored_check_without_spending(fakes, tmp_path): ...
def test_sort_comparison_checks_only_the_comparisons_named(fakes, tmp_path): ...
def test_a_failed_check_neither_refuses_sort_nor_makes_the_comparison_stale(fakes, tmp_path): ...
```

`FakeBigQuery.get_table` needs a `schema` for `Warehouse.columns`, and canned
answers for the 4 formula queries (match on `__cut` and `__matched`); extend the
fake, not the code.

- [ ] **Step 2: Run them to verify they fail.**

- [ ] **Step 3: Implement**

In `sort_run`, import `formula` inside the function as `explain` is. After
`stale` and `trace.check_ready`, before `explain.run_stored`:

1. When `results.composed_from` fails for the run, every checkable confirmed
   comparison gets a `Check` with `NOT_COMPOSED`; no queries.
2. Otherwise, for each confirmed comparison with `rows`, not in `stale`: a
   stored check whose fingerprint equals its latest result's is reused; outside
   `--comparison` without one, `OUTSIDE`; else `formula.plan`.
3. Dry-run every job's 4 SQL with `trace._dry_runs`; a failed dry run turns that
   job into a not-compared `Check`. Print
   `f"Formula check: {n} queries, ${usd:.2f} (dry run)."` and pass
   `also_usd=usd` to `run_stored` (with explanations off,
   `wh.refuse_past_caps(usd)`).

After `run_stored`, run each job (`formula.run_job`, then
`ticker.say("sort formula", comparison_id, wh.spent)`), store each check that
ran its queries with `latest.add_formula_check`, and, when any stored check
names a formula cell, `run = results.recompose(...)` before `suggest`; a
`Refusal` there keeps the old run and turns every just-run check into
`NOT_COMPOSED` labels (stored checks stay for the next compose). After
`explain.apply_runs` and before `mark_decided`, `formula.label(items, checks)`;
write its result to `triage.json` as `"formulas_not_compared"`. The `sort_run`
docstring adds the check, its pricing and its fallback.

- [ ] **Step 4: Run them, then the whole suite.** Expected: PASS.

- [ ] **Step 5: Commit** the five files:
      `feat(cube-validation): run the formula check in sort`.

---

### Task 16: `ask-owner` lists "formulas not compared"

**Files:**

- Modify: `P/sort.py` (new `formulas_not_compared`)
- Modify: `P/report.py` (`still_with_analyst`), `P/review.py` (`ask_owner`)
- Test: `T/test_report.py`, `T/test_cli.py`

**Interfaces:**

- Consumes: `triage.json`'s `"formulas_not_compared"` (Task 15).
- Produces:
  `sort.formulas_not_compared(loaded: dict) -> dict[str, dict[str, int]]`;
  `report.still_with_analyst(items, waiting, unchecked: dict[str, dict[str, dict[str, int]]] | None = None) -> list[str]`
  (per view, comparison, reason to cells).

- [ ] **Step 1: Write the failing tests**

```python
def test_still_with_the_analyst_lists_formulas_not_compared_masked():
    lines = report.still_with_analyst([], {}, {"v": {"c1": {"no rows both sides hold": 3}}})
    assert lines == ["`c1` in `v`: formulas not compared: no rows both sides hold; <10 cells closed by coverage only"]
def test_ask_owner_lists_formulas_not_compared_and_record_answers_ignores_them(fakes, tmp_path): ...
```

- [ ] **Step 2: Run them to verify they fail.**

- [ ] **Step 3: Implement.** Each line runs the reason through `_safe_reason`;
      `ask_owner` passes
      `{run.view: sort.formulas_not_compared(proven[run.view])}`.

- [ ] **Step 4: Run them, then the whole suite.** Expected: PASS.

- [ ] **Step 5: Commit** the five files:
      `feat(cube-validation): show the owner which formulas were not compared`.

---

### Task 17: Runbook

**Files:**

- Modify: `W/.claude/skills/cube-validation/SKILL.md` (open with Read)
- Check: `W/.claude/skills/cube-builder/SKILL.md`,
  `W/.claude/skills/cube-validation-answers/` (`rg` each changed term; update
  restatements)

- [ ] **Step 1: Edit, as plain behavior (no history, no counts):**

- Comparison keys (step 3): `unpublished: true`; a merge-key item may open with
  `<<:` (the writers find its `id:`).
- `read-sheet` / `rebuild-sheet` (steps 2 and 4): text measures are refused
  (compare the numeric measure it is built from); a sheet on no published
  dashboard is marked and refused unless opted in; allowlisted filter values
  show; a non-null filter needs `dashboard_filters` with `operator: set`, and a
  rebuild check written before this needs `rebuild-sheet` again; blank cells,
  `*` total rows and dual-axis repeats are skipped and counted.
- `compare` (step 5): the unpublished skip; the pre-aggregation refusal and its
  remedy.
- `sort` (step 6): a formula difference can sit under row causes; the check
  recomputes each differing cell on matched rows, is priced with the
  explanations ("Formula check: N queries"), and "formulas not compared: <why>"
  means it could not run (the cell closes by coverage, the owner sees it under
  "Still with the analyst"; fix the cause and sort again).
- `explain` (step 6.6): `{unmatched}` also holds `__moved` and `__d_<col>`, NULL
  unless that column differs; read the dashboard's value as
  `COALESCE(u.__d_x, u.x)`.
- Shared explanations (the paragraph after step 6.9): shared on one
  `dashboard_view` with the same `rows` grain and values; each comparison runs
  it on its own rows; "Also <comparison>". Cause-first: find a cause once on the
  comparison that shows it most clearly, let it run on every comparison of that
  model, then work comparison by comparison on what is left. A shared
  explanation reads only `__row`, `side` and the grain: a group-by column one
  sibling lacks fails there.

- [ ] **Step 2: Lint**

Run:
`/workspaces/teamster/.trunk/tools/trunk check --force --no-fix .claude/skills/cube-validation/SKILL.md </dev/null`
Expected: no findings.

- [ ] **Step 3: Commit** each edited skill file by name:
      `docs(cube-validation): runbook for the DDI run fixes`.
