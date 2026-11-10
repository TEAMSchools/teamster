# OKRTS Incentive Region Toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a School/Region parameter to the OKRTS Dashboard Landing Page
incentive panel so both incentive tables can show one row per region instead of
one row per school.

**Architecture:** A `.twb` XML edit to the production OKRTS workbook, done with
the `tableau-workbook-xml` skill's loop: pull fresh, write the assertion first,
edit by anchored substitution, run the checkers, repack, publish review copies
to a non-production project, and check numbers and renders. A new list parameter
drives one calculated field that returns `region` or `school`. That field
replaces `school` on Rows in both incentive worksheets. A parameter control
joins the panel's header strip. No dbt model changes.

**Tech Stack:** Tableau `.twb` XML; Python standard library for the edit and
assertion scripts; `docs/tableau-xml/scripts/` (`check_twb.py`,
`check_geometry.py`, `mutate.py`, `repack.py`, `tsc_session.py`);
`tableauserverclient` 0.42 run under pytest for credentials; the BigQuery MCP
for reference numbers.

**Spec:** [#6332](https://github.com/TEAMSchools/teamster/issues/6332). The
issue's "For Claude" fold-out holds the zone ids, LOD formulas, and filter
inventory this plan uses.

## Global Constraints

- Invoke the `tableau-workbook-xml` skill before Task 1. Its gates override
  anything here that reads looser.
- Paths: `<worktree>` is
  `/workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-okrts-incentive-region-toggle`.
  `<server>` is `<worktree>/.claude/scratch/tableau/server`, which is the
  template's `OUT` directory. `<scripts>` is
  `<worktree>/.claude/scratch/tableau/okrts-6332-scripts`. Run the
  `docs/tableau-xml/scripts/` checkers from the main checkout; this branch does
  not change them.
- Workbook: OKRTS Dashboard, LUID `08d133d6-6e48-4218-ae6d-015f7a0abe13`,
  project Production.
- Production publish happens only when the user names production as the target
  in a typed message and then answers yes to "Are you sure? This overwrites the
  production workbook and is visible to the whole network." Nothing in this plan
  publishes to production.
- Before the first publish, ask the user which non-production project to use.
  With no preference, use `GPA-monitor-temp`,
  `c74d8e08-b856-4430-a759-ebacb061e376`.
- Every review copy is named `ZZ-REVIEW <YYYY-MM-DD> OKRTS region toggle`, plus
  a suffix for the render variants (Task 6).
- Parameter: `[Parameter 9]`, caption `View By - Incentives`, string list,
  members `"School"` and `"Region"` in that order, default `"School"`.
- Calculated field: `[Calculation_6332000000000000001]`, caption
  `Incentive Row Label`, string dimension, formula
  `IF [Parameters].[Parameter 9] = 'Region' THEN [region] ELSE [school] END`.
  Column instance: `[none:Calculation_6332000000000000001:nk]`.
- Control title: `View by`.
- The two worksheets are `LP - Incentive Quarterly` and
  `LP - Incentive Monthly`. The dashboard is `Landing Page`.
- Read and write the `.twb` with `encoding="utf-8", newline=""`. Each
  substitution asserts exactly 1 match. Parse the result with `ET.fromstring`
  before writing.
- Read every exit code through a redirect, never a pipe:
  `cmd >/tmp/o 2>&1; rc=$?`.
- Edit `<zones>` only. The Landing Page `<devicelayouts>` block (an
  auto-generated Phone layout) stays byte-identical.
- No repo file changes besides this plan. All build files live in the worktree's
  gitignored `.claude/scratch/tableau/`. Downloaded workbooks go in `server/`;
  scripts go in `okrts-6332-scripts/`. There are no commits for Tasks 1 to 7.
- The credentialed pytest file is `tests/test_zz_okrts_6332.py` in the worktree.
  Run it with
  `VIRTUAL_ENV= uv --directory <worktree> run pytest <worktree>/tests/test_zz_okrts_6332.py -s`.
  Never stage it. Delete it in Task 7.
- Outbound text (issue comments) carries school, region, and network percentages
  only, never student-level rows.

## Review Focus

1. Region filter narrowed to 1 region with View By set to Region, then to
   School: both worksheets must return the same row set in the same order.
   Tested in Task 6, Step 6.
2. Academic Year set to 2025-26, where the `Exclude Miami [TEMP]` data source
   filter does not apply: the Region setting shows 4 regions in both worksheets.
   Tested in Task 6, Step 6.
3. IEP Status set to `Has IEP` with the Region setting: the shared IEP filter
   (filter-group 45) still gives both worksheets the same row set. Tested in
   Task 6, Step 6.
4. Clicking "Show Incentives", switching the parameter, then "Hide Incentives":
   the new control appears and disappears with the panel. A render cannot click,
   so a human checks this in Task 7, Step 5.
5. A Phone-layout viewer gets no control and sees the School default. Recorded
   in the hand-over (Task 7, Step 4); a human checks it if the owner wants.

---

### Task 1: Pull a fresh base and prove the checkers pass on it

**Files:**

- Create: `<worktree>/tests/test_zz_okrts_6332.py` (copy of
  `docs/tableau-xml/scripts/tsc_session.py`)
- Create: `<worktree>/.claude/scratch/tableau/server/base.twbx`, `base.twb`
- Create: `<worktree>/.claude/scratch/tableau/okrts-6332-scripts/facts.md`

**Interfaces:**

- Produces: `base.twb` and `base.twbx`, the only reference and donor for every
  later task; `facts.md` with `updated_at`, the revision number, and
  `show_tabs`.

- [ ] **Step 1: Copy the template and fill `WORKBOOK_LUID`**

  Set `WORKBOOK_LUID = "08d133d6-6e48-4218-ae6d-015f7a0abe13"`. Leave
  `TEMP_PROJECT` as `REPLACE-ME` until Task 6. Extend `test_download` to print
  `wb.show_tabs` and, after `server.workbooks.populate_revisions(wb)`, the
  highest `revision_number`.

- [ ] **Step 2: Run the download**

  Run:
  `VIRTUAL_ENV= uv --directory <worktree> run pytest <worktree>/tests/test_zz_okrts_6332.py -s -k test_download`
  Expected: `PROJECT: Production`, an `UPDATED:` timestamp, and `TWBX` larger
  than 20,000,000 bytes. Write the timestamp, revision number, and `show_tabs`
  value to `facts.md`.

- [ ] **Step 3: Diff the base against the planning snapshot**

  The planning snapshot (pulled 2026-11-09 without its extract) had 74
  worksheets, 7 dashboards, and parameters through `[Parameter 8]`. Diff the
  worksheet and parameter lists with the regexes in the skill's
  `references/build-workflow.md` ("Pull fresh, every time"). Expected: no names
  added or removed. If anything changed, stop and report it before you build on
  it.

- [ ] **Step 4: Run both checkers against the untouched base**

  Run:
  `uv run python docs/tableau-xml/scripts/check_twb.py <server>/base.twb --ref <server>/base.twb >/tmp/c1 2>&1; echo $?`
  Run:
  `uv run python docs/tableau-xml/scripts/check_geometry.py <server>/base.twb "Landing Page" --baseline <server>/base.twb >/tmp/c2 2>&1; echo $?`
  Expected: `0` for both. A failure here is a checker bug, not a workbook bug.
  Report it before you continue.

### Task 2: Build the BigQuery reference numbers

**Files:**

- Create: `<scripts>/oracle_quarterly.sql`, `<scripts>/oracle_weekly.sql`
- Create: `<scripts>/oracle_*.csv` (query results)

**Interfaces:**

- Produces: expected shares by `region` and by `school` for term `Q1` of
  `academic_year = 2026`, and for the most recent completed week, each computed
  2 ways: student-weighted and row-weighted.

The Tableau measure is `AVG` of a FIXED LOD, so its weighting depends on how
Tableau joins the LOD back to the view. The 2 weightings give different numbers,
and comparing against both shows which one Tableau computes.

- [ ] **Step 1: Write `oracle_quarterly.sql`**

  It reads `teamster-332318.kipptaf_tableau.rpt_tableau__okrts_behavior` and
  applies the workbook's data source filters before the LOD, as Tableau does:

  ```sql
  -- in scope: workbook data source filters
  where
      academic_year = 2026
      and region != 'Miami'
      and (
          behavior_category is null
          or behavior_category not in ('Values (10 Point Bonus)', 'Values (5)')
      )
  ```

  - LOD: `max(is_earned_quarterly_incentive)` grouped by `academic_year`,
    `term`, `student_number`.
  - Student-weighted share at grain `G` (`region` or `school`): the average of
    the LOD over distinct (`G`, `academic_year`, `term`, `student_number`).
  - Row-weighted share at grain `G`: the average of the LOD over every in-scope
    row, joined back on (`academic_year`, `term`, `student_number`).
  - Output columns: `grain`, `label`, `term`, `student_weighted`,
    `row_weighted`, `student_count`.

- [ ] **Step 2: Write `oracle_weekly.sql`**

  Same shape, with `is_earned_progress_to_quarterly` grouped by `academic_year`,
  `week_start_monday`, `student_number`. Pick the latest `week_start_monday`
  with `week_end_sunday < current_date('America/New_York')`.

- [ ] **Step 3: Run both queries and save the CSVs**

  Run each through the BigQuery MCP `execute_sql_readonly`. Expected: 3 region
  rows (Camden, Newark, Paterson) and 1 row per NJ school that has enrolled
  students in that term or week. If `student_weighted` and `row_weighted` are
  equal to 3 decimal places for every row, Task 6 cannot tell them apart. If so,
  pick another term or week where they differ, and record the choice.

### Task 3: Add the parameter and the calculated field

**Files:**

- Create: `<scripts>/edit_6332.py`, `<scripts>/assert_6332.py`
- Create: `<server>/out.twb`

**Interfaces:**

- Produces in `edit_6332.py`: `add_parameter_and_calc(xml: str) -> str`;
  `main()` reads `base.twb`, applies every edit function in task order, and
  writes `out.twb`.
- Produces in `assert_6332.py`: `check_param(xml: str) -> list[str]` (one string
  per failure); CLI `--only {param,rows,zone,all} <twb> --base <twb>`, exit 1
  when any failure is listed.

- [ ] **Step 1: Write `check_param`**

  Assertions, each its own failure string:

  - The `Parameters` datasource holds exactly 1 column named `[Parameter 9]`,
    with caption `View By - Incentives`, `datatype='string'`,
    `param-domain-type='list'`, and `value='&quot;School&quot;'`.
  - Its `<members>` are exactly `&quot;School&quot;` then `&quot;Region&quot;`.
  - The `rpt_tableau__okrts_behavior` datasource
    (`federated.14j3y9x1ckp90b1gn0dte0ypafs6`) holds exactly 1 top-level column
    named `[Calculation_6332000000000000001]`, with caption
    `Incentive Row Label`, `role='dimension'`, `type='nominal'`, and the formula
    from Global Constraints. Compare the parsed (unescaped) `formula` attribute,
    since the file stores the quotes as `&apos;`.

- [ ] **Step 2: Run it against the base**

  Run:
  `uv run python <scripts>/assert_6332.py --only param <server>/base.twb --base <server>/base.twb >/tmp/a 2>&1; echo $?`
  Expected: `1`, listing the missing parameter and the missing calculation.

- [ ] **Step 3: Implement `add_parameter_and_calc`**

  Clone the `[Parameter 7]` column block (`Sheet Swap - Tree`) for the
  parameter. Insert it after the closing `</column>` of `[Parameter 8]`, using
  an anchor that matches once. Insert the calculation column after the closing
  `</column>` of `Progress to Quarterly Incentive [LOD]`
  (`[Calculation_3819967322638225408]`) in the behavior datasource. Assert first
  that neither name exists in the base.

- [ ] **Step 4: Run the assertion and the checker**

  Run: `uv run python <scripts>/edit_6332.py` then the Step 2 command against
  `out.twb`. Expected: `0`. Run:
  `check_twb.py <server>/out.twb --ref <server>/base.twb`. Expected: `0`.

- [ ] **Step 5: Prove the assertion catches a wrong edit**

  Hand-write 2 mutants of `out.twb`: one with the member spelled `Regions`, one
  with the default `value='&quot;Region&quot;'`. Expected: `check_param` exits
  `1` on each.

### Task 4: Put the new field on Rows in both worksheets

**Files:**

- Modify: `<scripts>/edit_6332.py`, `<scripts>/assert_6332.py`

**Interfaces:**

- Consumes: `add_parameter_and_calc` (Task 3).
- Produces: `swap_incentive_rows(xml: str) -> str`;
  `check_rows(xml: str, base: str) -> list[str]`.

Today each worksheet references `[none:school:nk]` 3 times: its column instance,
its `<rows>`, and 1 style rule. The rule is `<style-rule element='label'>`
display `false` on Monthly (which hides the row labels) and
`<style-rule element='header'>` width `60` on Quarterly.

- [ ] **Step 1: Write `check_rows`**

  For each of the 2 worksheets:

  - `<rows>` is exactly
    `[federated.14j3y9x1ckp90b1gn0dte0ypafs6].[none:Calculation_6332000000000000001:nk]`.
  - `[none:school:nk]` occurs 0 times and the new instance occurs 3 times.
  - The behavior `<datasource-dependencies>` holds the calculation column (with
    its formula) and its column instance. A `Parameters` dependency block holds
    `[Parameter 9]`, and `<datasources>` lists `Parameters`.
  - Monthly's `element='label'` rule and Quarterly's `element='header'` rule now
    target the new instance with their original values.
  - With the new instance swapped back to `[none:school:nk]` and the added
    dependency lines removed, the worksheet text equals the base worksheet byte
    for byte. This proves the filters, slices, formats, and encodings did not
    change.

- [ ] **Step 2: Run it against the Task 3 output**

  Expected: exit `1` on both worksheets.

- [ ] **Step 3: Implement `swap_incentive_rows`**

  Use `EA - Behaviors - Leaderboard` as the model for the `Parameters`
  dependency block and its position among the other `<datasource-dependencies>`.
  In each worksheet, replace the `[none:school:nk]` column-instance line with
  the new instance's line. Keep the `[school]` and `[region]` `<column>`
  entries, because the calculation reads both. Scope every substitution to the
  one worksheet's element and assert 1 match each.

- [ ] **Step 4: Run the assertions and the checker**

  Run: `--only all` on the regenerated `out.twb`. Expected: `0`. Run:
  `check_twb.py out.twb --ref base.twb`. Expected: `0`.

- [ ] **Step 5: Prove the assertion catches the misalignment bug**

  Hand-write 2 mutants: Quarterly left on `[none:school:nk]` (Monthly swapped),
  and Monthly's label rule left on `[none:school:nk]`. Expected: `check_rows`
  exits `1` on each.

### Task 5: Add the parameter control to the panel header strip

**Files:**

- Modify: `<scripts>/edit_6332.py`, `<scripts>/assert_6332.py`

**Interfaces:**

- Consumes: Tasks 3 and 4.
- Produces: `add_param_control(xml: str) -> str`;
  `check_zone(xml: str, base: str) -> list[str]`; the new zone id, recorded in
  `facts.md` for Task 6.

The header strip is zone 657 (`param='horz'`, `fixed-size='60'`). Its children
are text zone 602 (`w='85578'`, `x='1025'`, not fixed, so it absorbs slack) and
IEP Status filter zone 656 (`w='12299'`, `x='86603'`).

- [ ] **Step 1: Write `check_zone`**

  Inside the Landing Page `<zones>` only:

  - Exactly 1 zone has `type-v2='paramctrl'` and
    `param='[Parameters].[Parameter 9]'`. Its parent is zone 657, and it sits
    between zones 602 and 656.
  - The new zone has `custom-title='true'`, `mode='compact'`,
    `hidden-by-user='true'` (as its siblings have), `h='6667'`, `y='8000'`,
    `w='12299'`, and `x='74304'`. Its `<formatted-text>` run is `View by`, and
    its `<zone-style>` matches zone 656's.
  - Zone 602 has `w='73279'`. Every other attribute on 602, 656, and 657 equals
    the base.
  - The new zone id appears nowhere in the base Landing Page dashboard element.
  - The Landing Page `<devicelayouts>` block is byte-identical to the base.

- [ ] **Step 2: Run it against the Task 4 output**

  Expected: exit `1`.

- [ ] **Step 3: Implement `add_param_control`**

  Use the next integer above the Landing Page's highest zone id. Clone zone 450
  (the `[Parameter 7]` control) for the element shape, with the attributes from
  Step 1. Insert it before zone 656 inside zone 657 in `<zones>`, then shrink
  zone 602. Anchor on the `<zones>` copy of zone 656, not the `<devicelayouts>`
  copy.

- [ ] **Step 4: Run the assertions and both checkers**

  Run: `--only all`. Expected: `0`. Run: `check_twb.py out.twb --ref base.twb`.
  Expected: `0`. Run:
  `check_geometry.py out.twb "Landing Page" --baseline base.twb`. Expected: `0`,
  printed in baseline mode.

- [ ] **Step 5: Prove the zone assertion with `mutate.py`**

  Run `control` first and confirm a byte-identical copy. Then build 3 mutants
  from `out.twb`: `reparent <new> 603`, `delete <new>`, and
  `set-attr <new> w 13000`. Expected: `check_zone` exits `1` on each, and
  `check_geometry.py --baseline` exits non-zero on the `set-attr` mutant.

### Task 6: Publish review copies and check the numbers

**Files:**

- Modify: `<scripts>/edit_6332.py` (render variant),
  `tests/test_zz_okrts_6332.py`
- Create: `<server>/final.twbx`, `<server>/final-render.twbx`,
  `<server>/base-render.twbx`, `<server>/csv/*.csv`

**Interfaces:**

- Consumes: `out.twb` (Task 5), `base.twbx` (Task 1), oracle CSVs (Task 2).
- Produces: `make_render_variant(xml: str) -> str`. It sets `hidden='false'` on
  the 2 incentive `<window>` entries and `hidden-by-user='false'` on the panel
  zones (601, 657, 602, 656, 603, 635, 604, 605, and the new zone) inside
  `<zones>`, and changes nothing else.

The panel is hidden when the page loads, and both worksheets are hidden windows.
The render variants exist only so a render and a CSV export can reach the panel.
They are never handed over.

- [ ] **Step 1: Ask the user for the non-production project**

  Record the id in `TEMP_PROJECT` and in `NON_PRODUCTION_PROJECTS`.

- [ ] **Step 2: Build and repack 3 packages**

  - `final.twbx`: `repack.py out.twb base.twbx final.twbx`.
  - `final-render.twbx`: `make_render_variant(out.twb)`, repacked.
  - `base-render.twbx`: `make_render_variant(base.twb)`, repacked.

  Before repacking, assert that the donor's packaged `.twb` equals `base.twb`.
  Assert that each render variant differs from its source only in the changed
  `hidden` and `hidden-by-user` attributes.

- [ ] **Step 3: Publish all 3 through the gate**

  Use the names `ZZ-REVIEW <date> OKRTS region toggle`,
  `... region toggle RENDER`, and `... base RENDER`. Set `show_tabs` from
  `facts.md`. Pass `hidden_views` computed from `<windows>`, minus the 7
  production dashboard names; for the render variants, also minus the 2
  incentive worksheets. Expected: each post-publish check reports the agreed
  project.

- [ ] **Step 4: Export CSVs from the worksheet views**

  Use `tsc.CSVRequestOptions().parameter("View By - Incentives", value)` and
  `server.views.populate_csv`. The `parameter` method exists in the installed
  0.42 source; a run has not confirmed it yet.

  - `base RENDER`: both worksheets, no parameter (school grain).
  - `region toggle RENDER`: both worksheets, with `School` and with `Region`.

- [ ] **Step 5: Compare the exports**

  Expected, in this order:

  1. Output School exports equal base exports cell for cell.
  2. Base school exports match the oracle's `student_weighted` school values at
     displayed precision (`p0%` Quarterly, `p0.0%` Monthly). A mismatch on some
     rows means extract drift or an oracle bug. Resolve it before step 3.
  3. Output Region exports match the oracle's `student_weighted` region values.

  If the exports match `row_weighted` instead, the live school numbers are
  row-weighted today too. Stop and report that to the user as a defect that
  exists before this change. Do not fix it inside this change.

- [ ] **Step 6: Run the Review Focus filter cases**

  Use `vf()` for filters and `parameter()` for the toggle, on both worksheets:
  `vf("Region", "Camden")` with each parameter value;
  `vf("Academic Year (Display)", "2025-26")` with `Region`;
  `vf("Iep Status", "Has IEP")` with `Region`. Expected: in each case the 2
  worksheets return the same row labels in the same order. The 2025-26 Region
  case lists 4 regions.

### Task 7: Look at the render and hand over

**Files:**

- Create: `<server>/render-*.png`
- Delete: `<worktree>/tests/test_zz_okrts_6332.py`

- [ ] **Step 1: Render the dashboard**

  Render `Landing Page` from `base RENDER` and from `region toggle RENDER` at
  `Resolution.High`. For the output, render once per parameter value, setting
  the parameter explicitly.

- [ ] **Step 2: Crop and read the panel**

  Crop zone 601's box and read the crop for: `####`, clipped or ellipsised row
  labels, Monthly cells out of line with Quarterly labels, an overlap between
  the new control and the IEP filter, and the `View by` title. Sample pixels in
  the title crop to confirm light text on the strip's `#000000` background.

- [ ] **Step 3: Delete the throwaway test file**

  Run: `rm <worktree>/tests/test_zz_okrts_6332.py`, then
  `git -C <worktree> status --short`. Expected: no `tests/` entry.

- [ ] **Step 4: Post the hand-over on #6332**

  Include:

  - The path to `final.twbx` and the 3 review copy names.
  - What was verified: the checkers, the mutants, the CSV comparisons, and which
    weighting matched.
  - What was inferred: hiding the new zone with `hidden-by-user`, and
    `layout-cache cell-count-h='19'` on zones 604 and 605 being harmless at 3
    rows.
  - That the Phone layout and embedded credentials were not carried.
  - The extract `updated_at` and the production revision number from `facts.md`.

  Post no numbers from the IEP-filtered case; its cells can be small.

- [ ] **Step 5: Ask for the human checks**

  Ask the owner to:

  - Open `final.twbx` in Tableau Desktop.
  - Click "Show Incentives", switch View by, and click "Hide Incentives".

  A production publish waits for the user's 2 typed confirmations.

---

## Revision 2026-11-10: add a School Level option

The request in #6332 asked for "region and school-level grains". This plan read
"school-level" as one row per school, which the tables already showed. The owner
meant school level: ES, MS, and HS. The owner decided:

- `[Parameter 9]` gains a third member, `"School Level"`. The members read
  `"School"`, `"Region"`, `"School Level"`, and the default stays `"School"`.
- In School Level mode the rows are `ES`, `HS`, and `MS`, in the default
  alphabetical order that the workbook's other `school_level` displays use. The
  rows cover whatever regions the Region filter keeps.
- Out-of-district students (`school_level = 'OD'`) count under their home
  school's level, so the School Level rows cover the same students as the School
  and Region views.

Values that every revision task uses:

- New calculated field `[Calculation_6332000000000000002]`, caption
  `Home School Level`, string dimension, formula
  `{FIXED [academic_year], [school] : MIN(IF [school_level] != 'OD' THEN [school_level] END)}`.
- `[Calculation_6332000000000000001]` gets the formula
  `CASE [Parameters].[Parameter 9] WHEN 'Region' THEN [region] WHEN 'School Level' THEN [Calculation_6332000000000000002] ELSE [school] END`.
- Each incentive worksheet's behavior dependencies add the new calculation and
  the `[school_level]` column, both in name-sorted position.
- The Landing Page's dashboard-level `[Parameter 9]` dependency lists all 3
  members.

### Task R1: Extend the BigQuery reference numbers

- [ ] Add a `school_level` grain to `oracle_quarterly.sql` and
      `oracle_weekly.sql`, mapping each student's row to the school's non-OD
      level for that year.
- [ ] Assert that every school has exactly 1 non-OD level per year. Expected: no
      school with 0 or with 2 levels.

### Task R2: Edit the workbook and its assertions

- [ ] Extend `check_param`, `check_rows`, and `check_zone` to the values above,
      and run them against the current `out.twb`. Expected: exit `1`.
- [ ] Extend `edit_6332.py`, regenerate `out.twb`, and run all assertions,
      `check_twb.py`, and `geo_diff.sh`. Expected: `0` for each.
- [ ] Hand-write 2 mutants: the third member missing from the dashboard
      dependency, and the row formula reading raw `[school_level]` instead of
      the new calculation. Expected: the assertions exit `1` on each.

### Task R3: Republish and check the numbers

- [ ] Republish the hand-over and RENDER review copies to the same workbook ids.
- [ ] Export both incentive worksheets under School, Region, and School Level.
      Expected: School and Region exports equal the previous ones, and School
      Level exports match the oracle's student-weighted values for Q1 and the
      week of 11/2/2026.
- [ ] Expected: both worksheets show the same 3 rows in School Level mode.

### Task R4: Look at the render and report

- [ ] Render the Landing Page with School Level and read the panel crop for
      `####`, clipped labels, and the `View by` value fitting its control.
      Expected: `measure_pos.py` still passes.
- [ ] Post the result on #6332.
