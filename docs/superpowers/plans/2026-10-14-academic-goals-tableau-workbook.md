# Academic Goals Tableau Workbook Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking. ALSO REQUIRED: invoke the
> `tableau-workbook-xml` skill before the first workbook edit and follow its
> loop exactly; this plan schedules that loop, it does not replace it.

**Goal:** Rebuild the Academic Goal Roll-Up workbook (luid
`15cb4859-ab6d-46a7-8e4f-1aa786785aa3`) on the merged
`rpt_tableau__academic_goals_dashboard` view with the approved "Option A"
design: a network Goal Scoreboard dashboard and an AP/Teacher Worklist
dashboard.

**Architecture:** Every change is an XML edit to the production workbook's own
`.twb`, verified by the `tableau-workbook-xml` checkers, repacked against the
pulled `.twbx` donor, published as a `ZZ-REVIEW` copy to a non-production
project, and render-verified. The existing workbook's sheets are the skeletons:
the two Rollup tabs already implement Math-and-Reading-side-by-side tables at
every grain Option A needs, so new sheets are clones with re-mapped fields, not
hand-built XML. Production publish happens only at the end, by a human decision,
with the skill's two typed confirmations.

**Tech Stack:** Tableau Server XML (`.twb`/`.twbx`), scripts in
`docs/tableau-xml/scripts/`, `tableauserverclient` via a throwaway
`tests/test_zz_*.py` under `uv run pytest -s`, BigQuery MCP for data checks.

**Spec:**
`docs/superpowers/specs/2026-10-14-academic-goals-dashboard-view-design.md`
(data contract) plus the Design Contract section below (visual contract,
condensed from the approved Option A canvas, v12). Refs #5903.

## Global Constraints

- **Preconditions:** #5893 merged AND `rpt_tableau__academic_goals_dashboard`
  materialized in prod (`kipptaf_tableau`). Task 0 gates on both.
- **Workbook artifacts never enter git.** The `.twbx`, `.twb`, renders, and
  mapping files live in the session scratchpad. Renders contain student PII:
  view them in the terminal, never attach them to GitHub, issues, or PR bodies.
- **Publishes go only to the review project.** Ask the user which non-production
  project to use before the first publish; default `GPA-monitor-temp`, id
  `c74d8e08-b856-4430-a759-ebacb061e376`. Every publish asserts that recorded id
  and a `ZZ-REVIEW-<YYYY-MM-DD>` workbook-name prefix. Production publish
  requires the user naming production in a typed message AND answering yes to
  "Are you sure? This overwrites the production workbook and is visible to the
  whole network." — both quoted verbatim in the handover.
- **Frozen refresh (T&L decision, 2026-10-14):** the rebuilt workbook ships with
  NO extract refresh schedule. One manual refresh happens on a date T&L picks
  (~MOI). Do not add a `cron_schedule` to the `academic_goal_rollup_dashboard`
  exposure.
- **Goals are fractions** (0.44, not 44) in the view. Every percent is a Tableau
  number format, never `*100` in a calc.
- **Fonts and colors:** Verdana. Strong Indigo `#001E62`, orange `#F9A21A`,
  light blue `#57C0E9`, green `#C3D52E`, red `#EE3C37`; gap text red `#b81f1b` /
  green `#7e8c12`; Bucket 4 gray `#b6c0cf`.
- **Known XML limits (from `tableau-workbook-xml`, all Verified):** parameter
  tokens in mark labels render blank; dashboard text zones never resolve dynamic
  text (static copy only); tooltips cannot be render-verified (human hover); a
  render cannot verify Desktop validity (human `.twbx` open).

### The per-edit loop (referenced by every task below)

Run after every `.twb` edit, from the repo root, with `base.twb` = the untouched
Task 1 pull:

```bash
uv run python docs/tableau-xml/scripts/check_twb.py <out>.twb --ref <scratch>/base.twb >/tmp/o1 2>&1; echo "rc1=$?"
uv run python docs/tableau-xml/scripts/check_geometry.py <out>.twb "<edited dashboard>" --baseline <scratch>/base.twb >/tmp/o2 2>&1; echo "rc2=$?"
uv run python docs/tableau-xml/scripts/repack.py <out>.twb <scratch>/base.twbx <out>.twbx
uv run pytest tests/test_zz_goals_workbook.py -s -k publish   # ZZ-REVIEW publish
uv run pytest tests/test_zz_goals_workbook.py -s -k render    # render + crop
```

Every edit script: `encoding="utf-8", newline=""` on read and write; every
substitution anchored and asserted to match exactly once; old-string and
new-string counts asserted (never a byte-delta guard); `ET.fromstring` parse
before write. Before each structural zone edit, write the failing assertion
first and prove it catches a `mutate.py` mutant (run `control` first and confirm
byte-identity).

## Review Focus

1. **A parameter token placed in a mark label renders a blank line** — the
   Count-%-of and planner numbers must live only in tooltips, titles, or
   calc-driven text marks; Task 10's render asserts no blank line in any BAN.
2. **Grade 9 goal columns are NULL until Marya's targets land** — gap and goal
   cells must render empty (not `####`, not `NULL` text); Task 7 renders a
   grade-9 row in both subjects.
3. **Miami has zero stored buckets until the Focus pull refreshes** — the Miami
   tab shows an all-Bucket-4 region; Task 12 renders Miami and confirms it reads
   as "no uploads yet" (untested/Bucket 4 messaging), not as a broken join.
4. **The Enrolled/Tested parameter must move every percent, including the
   planner's head counts** — Task 12 renders both parameter values and asserts a
   value that MUST differ (the Tested % BAN) actually differs.
5. **A non-selected roll-up level sheet must fully collapse** — Task 10 runs
   `check_geometry.py` and a render per `Roll up by` value, all five, looking
   for ghost whitespace or overlapping zones.

## Design Contract (Option A, canvas v12)

**Dashboard 1 — "Goal Scoreboard" (network and regional leaders).**

- Header: workbook title, `SY 2026-27` chip, static note "Buckets as uploaded ·
  frozen at launch — one refresh at MOI", `Count % of` parameter control
  (Enrolled | Tested), Region quick filter (Network/Newark/Camden/Paterson/
  Miami).
- Static reading-guide text zone (verbatim copy below, Task 10).
- Four BANs: **Proficient + projected** (Bucket 1 share), **Students to move**
  (Bucket 2 count), **Plan lands at** (Bucket 1+2 share), **Tested** (tested
  share of enrolled).
- **Goals by grade band** table: rows = grade band (K, 1-2, 3, 4-8, 9), Math and
  ELA column groups side by side, each: plan %, goal %, bullet bar (plan bar +
  goal reference line). K/1-2 Reading shows "DIBELS".
- **Roll-up** section: `Roll up by` parameter (Region | School | Band | Grade |
  School x Grade) swapping five same-column sheets in a vertical container.
  Columns per subject group (Math, then ELA/Reading): bucket-mix stacked bar (B1
  indigo, B2 orange, B3 light blue) with goal reference line, plan %, goal % +
  gap pts (green/red), # to move.
- **Drill panel**: clicking a roll-up row filter-actions a by-grade sheet for
  the selected school (same columns, grade rows).
- **Amendment-planner tooltip** on every plan/gap mark: goal restated as a head
  count at current enrollment, plan head count (B1 + B2), the action line ("Add
  N students to Bucket 2 to reach goal" / "Covered — plan clears the goal by N
  students"), candidates note, and the frozen-refresh footer.

**Dashboard 2 — "Worklist" (APs and teachers).**

- Quick filters: School, Grade Level, Subject, IEP Status, Homeroom Section,
  Course Teacher, Course Section, Student Tier (the legacy School Rollup filter
  set, kept).
- Four bucket BANs (count + share of grade).
- Student table: name, student number, tier (colored chip/cell), benchmark
  assessment type + score, section · teacher, IEP, note column with "Next
  eligible if a Bucket 2 seat opens" on Bucket 3 rows. Ship tier-colored cells
  (like the legacy roster); whole-row shading by tier (B1 `#c6d3ee`, B2
  `#dce4f4`, B3 `#fdf3d3`, B4 none — Marya's palette exploration) is a
  Desktop-polish item listed in the Task 13 handover, not built in XML.
- Buttons: **Open DDI tier roster** (URL action to the DDI dashboard's tier
  roster view, copied from the production DDI workbook URL) and the existing
  **Launch GForm** amendment button (reuse the current School Rollup button's
  URL action verbatim).
- Static note: replacements are never automatic; data as of the last refresh.

**Out of scope (declined in design review):** kanban cards, hover-only chrome,
rounded-corner cards, Option B entirely.

## Calculated fields and parameters (exact definitions)

Add as `<column>` elements on the new datasource (Task 4). Formulas verbatim:

| Name                                                                           | Type                        | Formula / domain                                                                                                                                                                                           |
| ------------------------------------------------------------------------------ | --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Count % of`                                                                   | string parameter            | list: `Enrolled`, `Tested`; default `Enrolled`                                                                                                                                                             |
| `Roll up by`                                                                   | string parameter            | list: `Region`, `School`, `Band`, `Grade`, `School x Grade`; default `School`                                                                                                                              |
| `Denominator Flag`                                                             | calc                        | `IF [Count % of] = 'Tested' THEN [Is Tested Int] ELSE 1 END`                                                                                                                                               |
| `Students (Denom)`                                                             | calc                        | `SUM([Denominator Flag])`                                                                                                                                                                                  |
| `Grade Band`                                                                   | calc                        | `IF [Grade Level] = 0 THEN 'K' ELSEIF [Grade Level] <= 2 THEN '1-2' ELSEIF [Grade Level] = 3 THEN '3' ELSEIF [Grade Level] <= 8 THEN '4-8' ELSE '9' END`                                                   |
| `Plan Students`                                                                | calc                        | `SUM(IIF([Student Tier] = 'Bucket 1' OR [Student Tier] = 'Bucket 2', [Denominator Flag], 0))`                                                                                                              |
| `Plan Share`                                                                   | calc                        | `[Plan Students] / [Students (Denom)]`                                                                                                                                                                     |
| `Bucket 1 Share`                                                               | calc                        | `SUM(IIF([Student Tier] = 'Bucket 1', [Denominator Flag], 0)) / [Students (Denom)]`                                                                                                                        |
| `To Move`                                                                      | calc                        | `SUM(IIF([Student Tier] = 'Bucket 2', 1, 0))`                                                                                                                                                              |
| `Tested Share`                                                                 | calc                        | `SUM([Is Tested Int]) / SUM(1)`                                                                                                                                                                            |
| `Goal (Level)`                                                                 | calc, one per roll-up sheet | `MIN([Region Goal])` / `MIN([School Goal])` / `MIN([Grade Band Goal])` / `MIN([Grade Goal])` — each sheet binds the goal field matching its grain                                                          |
| `Gap Pts (Level)`                                                              | calc, per sheet             | `ROUND(([Plan Share] - [Goal (Level)]) * 100, 0)`                                                                                                                                                          |
| `Goal Students`                                                                | calc, per sheet             | `CEILING([Goal (Level)] * [Students (Denom)])`                                                                                                                                                             |
| `Amendment Need`                                                               | calc, per sheet             | `MAX(0, [Goal Students] - [Plan Students])`                                                                                                                                                                |
| `Planner Line`                                                                 | calc, per sheet             | `IF [Amendment Need] > 0 THEN 'Add ' + STR([Amendment Need]) + ' students to Bucket 2 to reach goal' ELSE 'Covered — plan clears the goal by ' + STR([Plan Students] - [Goal Students]) + ' students' END` |
| `Show Region`, `Show School`, `Show Band`, `Show Grade`, `Show School x Grade` | calc, one per level         | `[Roll up by] = 'Region'` (and the matching literal per sheet); each roll-up sheet filters its own calc to True                                                                                            |

Percent columns get `default-format` number formatting on the `<column>`
(families in `references/formatting.md`); never format a table calc this way.

## File Structure

- `tests/test_zz_goals_workbook.py` — throwaway pytest session (download, gated
  publish, render), copied from `docs/tableau-xml/scripts/tsc_session.py`;
  deleted at handover.
- `<scratchpad>/goals-workbook/base.twbx`, `base.twb` — the Task 1 pull, never
  edited.
- `<scratchpad>/goals-workbook/taskN.twb` — one output per task, each built from
  the previous task's output; checkers always run `--ref base.twb`.
- `<scratchpad>/goals-workbook/edits/taskN_*.py` — one anchored edit script per
  change, rerunnable.
- `<scratchpad>/goals-workbook/renders/` — base and per-task renders/crops.
- `<scratchpad>/goals-workbook/column_mapping.tsv` — Task 2 output.

---

### Task 0: Precondition gate

**Files:** none (checks only).

- [ ] **Step 1:** Confirm #5893 is merged: `gh pr checks 5893` state and
      `mcp__github__pull_request_read` `merged: true`.
- [ ] **Step 2:** Confirm the view exists in prod with rows:

```sql
select count(*) as n, countif(student_tier != 'Bucket 4') as stored_buckets
from `teamster-332318`.kipptaf_tableau.rpt_tableau__academic_goals_dashboard
where academic_year = 2026
```

Expected: `n` > 10,000. Record `stored_buckets`: if 0, the NJ upload has not
landed — proceed (the build does not depend on it) but note it in every render
review and in the handover.

- [ ] **Step 3:** Ask the user which non-production project the review copies
      land in; record the id. Default `GPA-monitor-temp`,
      `c74d8e08-b856-4430-a759-ebacb061e376`.
- [ ] **Step 4:** Invoke the `tableau-workbook-xml` skill and read
      `references/build-workflow.md` and `references/layout-and-zones.md`.

### Task 1: Pull, baseline, inventory

**Files:** Create `tests/test_zz_goals_workbook.py` (from
`docs/tableau-xml/scripts/tsc_session.py`, fill the three `REPLACE-ME`s:
workbook luid `15cb4859-ab6d-46a7-8e4f-1aa786785aa3`, the recorded review
project id, workbook name prefix `ZZ-REVIEW-<date>-academic-goals`).

**Interfaces:** Produces `base.twbx`/`base.twb`, the recorded `updated_at` and
revision number, and `inventory.md` (worksheet names, dashboard names, parameter
names, datasource names + captions, `<windows>` hidden flags) that every later
task reads.

- [ ] **Step 1:** Download with `include_extract=True`; record `updated_at` and
      the current revision number in `inventory.md`.
- [ ] **Step 2:** Extract `base.twb` from the `.twbx`; run both checkers against
      the untouched base (a failure here is a checker bug, not a workbook bug —
      stop and report).
- [ ] **Step 3:** Write `inventory.md`: every worksheet, the two dashboards'
      zone trees (ids, nesting), both embedded datasource names
      (`rpt_tableau__academic_goals_rollup (kipptaf_tableau)` and
      `miami_goals_new (awalters)`), all parameters, all URL actions (capture
      the Launch GForm URL verbatim), and which sheets `<windows>` marks
      publishable.
- [ ] **Step 4:** Render all four existing tabs at 1400x1000 into
      `renders/base/` — these are the faithful-rebuild comparison set.
- [ ] **Step 5:** Commit nothing (no repo files changed except the throwaway
      test, which is never committed).

### Task 2: Column mapping

**Files:** Create `<scratchpad>/goals-workbook/column_mapping.tsv`.

**Interfaces:** Produces the old-name → new-name mapping Task 3 applies.
Columns: `datasource`, `old_name`, `new_name`, `status` (mapped / dropped /
needs-user).

- [ ] **Step 1:** Parse both embedded datasources' `<column>` elements out of
      `base.twb` (name, caption, datatype, role).
- [ ] **Step 2:** Pull the new view's columns:

```sql
select column_name, data_type
from `teamster-332318`.kipptaf_tableau.INFORMATION_SCHEMA.COLUMNS
where table_name = 'rpt_tableau__academic_goals_dashboard'
order by ordinal_position
```

The full list (fixed by the view's contract): academic_year, region, schoolid,
school, grade_level, student_number, student_name, iep_status, homeroom_section,
homeroom_teacher_name, course_section, course_teacher_name, subject,
student_tier, bucket_store, is_exempt_state_testing, performance_level,
scale_score, scale_score_state, is_proficient_int_state, scale_score_iready,
is_proficient_live_int, is_approaching_live_int, is_below_live_int, grade_goal,
school_goal, region_goal, organization_goal, grade_band_goal,
assessment_band_goal, benchmark_assessment_type, is_tested_int.

- [ ] **Step 3:** Map every old column used by any worksheet (grep the `.twb`
      for each `[old_name]` usage; an unused column maps to `dropped`). Known
      renames to seed: `student_tier_calculated` → `student_tier`; the Miami
      extract's columns map to the same new names as the NJ view's.
- [ ] **Step 4:** Any `needs-user` row (an old field with no evident new home)
      goes to the user as a question before Task 3 starts. Zero unresolved rows
      is the exit criterion.

### Task 3: Datasource repoint (faithful rebuild)

**Files:** Create `edits/task3_repoint.py` → `task3.twb`.

**Interfaces:** Produces a workbook whose four existing tabs run entirely on
`rpt_tableau__academic_goals_dashboard`; `miami_goals_new` is no longer
referenced. Every later task edits this file's descendants.

- [ ] **Step 1:** Write the failing assertion: after the edit, zero occurrences
      of `academic_goals_rollup` and `miami_goals_new` outside comments; run it
      against `base.twb` and confirm it fails.
- [ ] **Step 2:** Edit the NJ datasource's `<connection>` relation/table to
      `[kipptaf_tableau].[rpt_tableau__academic_goals_dashboard]`; apply every
      `column_mapping.tsv` rename with one anchored, count-asserted substitution
      per name (datasource `<column>` elements AND worksheet `[field]` refs).
- [ ] **Step 3:** Repoint the Miami tabs' sheets onto the repointed datasource
      (swap their datasource dependency and field refs per the mapping); leave
      the `miami_goals_new` `<datasource>` element in place but unreferenced
      only if removal breaks the content model — prefer removal;
      `check_twb.py --ref` reports what changed.
- [ ] **Step 4:** Run the per-edit loop (edited dashboards: both). Expected:
      rc1=0, rc2=0 per dashboard.
- [ ] **Step 5:** Render all four tabs; compare against `renders/base/` side by
      side. Identical layout, plausible values (NJ numbers match base where the
      old methodology and stored buckets agree; differences must be explainable
      by the stored-bucket cutover, and get listed in the task report). Miami
      tabs: values now come from the warehouse — all Bucket 4 until uploads land
      is CORRECT; say so in the report.

### Task 4: Parameters and calculated fields

**Files:** Create `edits/task4_calcs.py` → `task4.twb`.

**Interfaces:** Produces every parameter and calc in the table above, exactly as
named there; Tasks 5-11 reference them by those names.

- [ ] **Step 1:** Assertion first: each new `<column>` name appears exactly once
      after the edit, zero times before.
- [ ] **Step 2:** Insert the two parameters (clone the structure of an existing
      parameter element in the workbook, including its
      `<calculation class='tableau' formula=...>` default) and the calc columns
      with formulas verbatim from the table. Percent calcs get `default-format`
      (copy a working percent format family from `references/formatting.md`).
- [ ] **Step 3:** Per-edit loop. Then a probe: add the calcs to a copy of one
      existing sheet (probe sheet, deleted in Task 10), publish, render with
      `Count % of` = `Enrolled` and again `Tested`, and confirm `Plan Share`
      moves. A value that does not change proves nothing — pick a school with
      untested students.

### Task 5: Worklist dashboard

**Files:** Create `edits/task5_worklist.py` → `task5.twb`.

**Interfaces:** Produces dashboard `Worklist` (renamed from School Rollup) and
its roster sheet with `benchmark_assessment_type`, tier colors, and the
next-eligible note; Task 11 adds its tooltip; Task 12 renders it.

- [ ] **Step 1:** Rename the School Rollup dashboard to `Worklist`; keep its
      filter set and the Launch GForm button untouched.
- [ ] **Step 2:** Roster sheet edits: add `benchmark_assessment_type` beside the
      score; add a note column calc
      `IF [Student Tier] = 'Bucket 3' THEN 'Next eligible if a Bucket 2 seat opens' ELSE '' END`;
      tier cell colors to the brand palette (encodings copied from the sheet's
      existing tier color encoding, values swapped).
- [ ] **Step 3:** Add the `Count % of` parameter control zone and a static text
      zone: "Buckets are the uploaded lists — moving a student takes the
      amendment form. Replacements are never automatic; Bucket 3 students are
      the next-eligible pool. Data as of the last refresh (next: MOI)."
- [ ] **Step 4:** Add the DDI tier roster URL action: list the DDI dashboard's
      views via the Tableau MCP (`rpt_tableau__ddi_dashboard` exposure's
      workbook), take the tier-roster view's URL, and wire a dashboard URL
      action passing School and Grade Level as parameters in the URL.
- [ ] **Step 5:** Per-edit loop (dashboard `Worklist`); render; compare with
      `renders/base/` School Rollup — same bones, new columns present, no
      `####`, no clipped captions (budget `97 * w / 39676` chars per strip).

### Task 6: Grade-band table sheet

**Files:** Create `edits/task6_band.py` → `task6.twb`.

**Interfaces:** Produces worksheet `Band Goals` (rows `Grade Band`, Math and ELA
measure groups: `Plan Share`, `Goal (Level)` bound to `MIN([Grade Band Goal])`,
bullet bar) consumed by Task 10's scoreboard.

- [ ] **Step 1:** Clone the existing Band Goals section's worksheet (the Goal
      Rollup tab's band block is already band x subject with Math|Reading side
      by side); keep `<simple-id>` unique and the `<view>`'s `<aggregation>`
      (clone, never hand-build — the content-model refusals in the skill's
      catalog all came from hand-built skeletons).
- [ ] **Step 2:** Swap measures: old five-column set → `Plan Share`,
      `Goal (Level)`, `Gap Pts (Level)`, `To Move`. Add the bullet bar:
      `Plan Share` on columns as a bar, `Goal (Level)` as a `<reference-line>`
      (insert AFTER any existing `label-data`/`dropline`/`trendline` and BEFORE
      `customized-tooltip`/`customized-label`/`style` — pane model order).
- [ ] **Step 3:** Per-edit loop; render; grade 9 rows show plan values and EMPTY
      goal/gap cells (Review Focus 2); K and 1-2 Reading rows read "DIBELS" (a
      row-level calc
      `IF [Grade Band] IN ('K','1-2') AND [Subject] = 'Reading' THEN 'DIBELS' END`
      displayed in place of the percent).

### Task 7: Five roll-up level sheets

**Files:** Create `edits/task7_levels.py` → `task7.twb`.

**Interfaces:** Produces worksheets `Rollup - Region`, `Rollup - School`,
`Rollup - Band`, `Rollup - Grade`, `Rollup - School x Grade`, each filtered on
its `Show <Level>` calc, identical columns: bucket-mix stacked bar + goal
reference line, `Plan Share`, `Goal (Level)` + `Gap Pts (Level)`, `To Move`, per
subject group. Task 9's filter action sources `Rollup - School`.

- [ ] **Step 1:** Clone the Task 6 band sheet five times (one clone per level);
      per sheet: swap the row dimension (Region / School / `Grade Band` /
      `Grade Level` / School + `Grade Level`), bind `Goal (Level)` to the
      matching goal field (`region_goal`, `school_goal`, `grade_band_goal`,
      `grade_goal`, `grade_goal`), and add the sheet's `Show <Level>` filter =
      True.
- [ ] **Step 2:** Bucket-mix bar: stacked bar of
      `SUM(IIF([Student Tier]='Bucket N',[Denominator Flag],0))/[Students (Denom)]`
      for N in 1..3, colored indigo/orange/light blue, goal reference line as in
      Task 6.
- [ ] **Step 3:** Per-edit loop; publish; render each sheet standalone (not yet
      in a dashboard) with `Roll up by` set to its level; confirm rows, bars,
      and the goal line. Grade 9 rows per Review Focus 2.

### Task 8: Scoreboard BAN sheets

**Files:** Create `edits/task8_bans.py` → `task8.twb`.

**Interfaces:** Produces four single-value worksheets — `BAN Bucket 1 Share`
(`Bucket 1 Share`), `BAN To Move` (`To Move`), `BAN Plan Share` (`Plan Share`),
`BAN Tested` (`Tested Share`) — titles carry the label text; Task 10 places
them.

- [ ] **Step 1:** Clone a minimal existing sheet per BAN; one measure on Text,
      label text in the worksheet TITLE (NOT the mark label — parameter tokens
      and added text calcs on the Text shelf are the two verified mark-label
      failure modes). Sub-labels ("Buckets 1 + 2 — if every Bucket 2 student
      moves") are static title lines.
- [ ] **Step 2:** Per-edit loop; render all four; big number legible at
      1400-wide, no blank line in any BAN (Review Focus 1).

### Task 9: Drill sheet and filter action

**Files:** Create `edits/task9_drill.py` → `task9.twb`.

**Interfaces:** Produces worksheet `Drill - School by Grade` (clone of
`Rollup - School x Grade` without the `Show` filter) and a dashboard filter
action `School row -> Drill` (source `Rollup - School`, target the drill sheet,
fields School + Region, clearing to exclude-all so the panel is empty until a
click).

- [ ] **Step 1:** Clone the sheet; add the action to `<actions>` cloned from an
      existing filter action in the workbook (the current dashboards carry
      filter actions to copy structurally).
- [ ] **Step 2:** Per-edit loop. A render CANNOT verify a click — render only
      that the panel exists and is empty-by-default, and add "click a school row
      → drill panel populates" to the human checklist.

### Task 10: Assemble the Goal Scoreboard dashboard

**Files:** Create `edits/task10_scoreboard.py` → `task10.twb`.

**Interfaces:** Produces dashboard `Goal Scoreboard`: header zones (title,
parameter controls, region filter), reading-guide static text, BAN row, band
table, roll-up container (five level sheets stacked in one vertical flow
container), drill panel. Replaces the legacy Goal Rollup tab position; the
legacy tabs stay in the file hidden (retire visibly only at production publish,
the owner's call).

- [ ] **Step 1:** `mutate.py control` on the dashboard, then write the zone
      assertions (zone count, nesting parents, container spans) and prove each
      catches a mutant (`duplicate`, `reparent`, `swap`).
- [ ] **Step 2:** Build the zone tree: top-level `layout-basic` spanning the
      100000-unit canvas; header row; text zone with the reading guide verbatim:
      "Every student sits in one of four buckets, set at rollout and uploaded to
      the SIS — this page never recalculates them. Plan lands at = Buckets 1 +
      2: where a grade, school, or region finishes if every named Bucket 2
      student reaches proficient. Results come from NJSLA and EOY diagnostics.
      Count % of re-bases every percent: Enrolled counts all active students
      (untested sit in Bucket 4); Tested counts only students with a baseline
      score." (Static text only — dashboard text zones never resolve dynamic
      tokens.)
- [ ] **Step 3:** BAN row (4 zones), band table zone, roll-up container with the
      five sheets (`show-title='false'` on each; each collapses when its `Show`
      filter is False), drill panel zone, legend strip. Legend heights: 40px =
      one swatch row, 70px = two.
- [ ] **Step 4:** Per-edit loop with `check_geometry.py` on `Goal Scoreboard`;
      then one publish + render PER `Roll up by` value (five renders) and per
      `Count % of` value (Review Focus 4, 5). Crop and inspect every region:
      `####`, clipped captions, missing legend entries, literal `[federated…]`,
      overlaps. Delete the Task 4 probe sheet in this edit.

### Task 11: Amendment-planner tooltip

**Files:** Create `edits/task11_tooltip.py` → `task11.twb`.

**Interfaces:** Produces `<customized-tooltip>` on the plan/gap marks of all
five roll-up sheets, the band sheet, and the drill sheet, using `Planner Line`,
`Goal Students`, `Plan Students`, `Students (Denom)`, `Goal (Level)`.

- [ ] **Step 1:** Copy a WORKING tooltip's `<formatted-text>` runs verbatim from
      this workbook's own sheets (form A per the skill: whole line in one CDATA
      run), swapping only the `[datasource].[instance]` strings for the new
      fields. Line breaks inside `<formatted-text>` reproduce the workbook's own
      byte pattern exactly. Tooltip content: "Goal: <Goal (Level)> of <Students
      (Denom)> enrolled = <Goal Students> students · Plan today: <Plan Students>
      (<Plan Share>) · <Planner Line> · Head counts use enrollment as of the
      last refresh (next: MOI) · changes land through the amendment form."
- [ ] **Step 2:** Insert each `<customized-tooltip>` in pane model order (after
      any `reference-line`, before `customized-label`/`style`); check no pane
      already carries one.
- [ ] **Step 3:** Per-edit loop. A tooltip CANNOT be render-verified — this is
      the top item on the human checklist, with the open-question caveat from
      the skill quoted (a hand-built form-A copy once printed its tokens
      literally).

### Task 12: Full review publish and render sweep

**Files:** Create `edits/task12_final.py` → `final.twb`, `final.twbx`.

- [ ] **Step 1:** Final pass: re-pull the production workbook and diff
      `updated_at` against Task 1's — if the owner republished mid-build, STOP
      and reconcile (diff worksheet/parameter lists) before continuing on the
      stale base.
- [ ] **Step 2:** Set `hidden_views` for the publish: publishable sheets per
      `<windows>` minus the two intended tabs (`Goal Scoreboard`, `Worklist`)
      minus sheets this build added that must stay hidden (all helper sheets).
- [ ] **Step 3:** Publish the complete `ZZ-REVIEW` copy; record the target's
      pre-publish revision number. Render sweep: both dashboards x both
      `Count % of` values x all five `Roll up by` values x each region filter
      value (Miami included — Review Focus 3). Inspect every crop.
- [ ] **Step 4:** Run both checkers one last time against `final.twb` with
      `--ref base.twb`; `repack.py` output byte-verified.

### Task 13: Handover

**Files:** Delete `tests/test_zz_goals_workbook.py`.

- [ ] **Step 1:** Hand the user: the `final.twbx` path, the ZZ-REVIEW scratch
      copy URL, the extract's `updated_at`, the production revision number
      recorded pre-publish, and the human checklist — (a) open `final.twbx` in
      Desktop (the only real content-model check), (b) hover the planner tooltip
      on several marks and confirm fields resolve (open question in the skill),
      (c) click a school row and confirm the drill panel populates, (d) click
      both buttons, (e) flip both parameters by hand, (f) decide the legacy
      tabs' fate and the row-shading polish.
- [ ] **Step 2:** Report verified vs inferred per the skill's step 8, with which
      crops were inspected.
- [ ] **Step 3:** Production publish ONLY on the user's typed go-ahead plus the
      "Are you sure?" yes, quoted verbatim; then tell the user to open the
      production workbook themselves. Post-publish: confirm NO refresh schedule
      exists (frozen until MOI), remind that `miami_goals_new` retires with the
      legacy tabs, and comment completion on #5903.
