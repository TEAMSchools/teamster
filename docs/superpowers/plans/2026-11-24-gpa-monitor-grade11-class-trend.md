# Cumulative GPA Monitor: end-of-11th-grade GPA by graduating class — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-key the Trends pop-up's grade 11 chart (`GPA - Splay over time`)
from school year to graduating class, one row per high school plus an "All high
schools" total row, backed by 2 new dbt flags.

**Architecture:** 2 boolean columns on `rpt_tableau__gpa_cumulative_year`
(passed through `rpt_tableau__gpa_goal_progress`) carry the "last completed
11th-grade year" pick and the rolling 7-class window. The worksheet filters on
them. The owner refreshes the data source in Desktop and republishes, a subagent
rebuilds the worksheet through the `tableau-workbook-xml` skill and publishes a
review copy, and Claude checks the render against a warehouse answer key before
the owner publishes to production from Desktop.

**Tech Stack:** dbt (BigQuery), dbt unit tests, Tableau Desktop,
`tableauserverclient` via `docs/tableau-xml/scripts/`, Tableau MCP (read-only
renders), BigQuery MCP.

**Execution:** Tasks 1 to 3 run natively in this session. Task 4 waits on the
owner. Task 5 is one subagent. Task 6 is this session plus the owner.

**Spec:**
`docs/superpowers/specs/2026-11-24-gpa-monitor-grade11-class-trend-design.md`
(issue #6478)

Worktree:
`/workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-gpa-monitor-grade11-cohorts`
(abbreviated `<wt>` below). Every `git` call is `git -C <wt>`; every dbt call
passes `--project-dir <wt>/src/dbt/kipptaf`.

## Who does what in Tableau, and why

- The owner refreshes the data source in Desktop and republishes (Task 4). The 2
  new columns reach the embedded extract only through that Refresh; hand-adding
  `<metadata-record>` entries has no tested pattern in the
  `tableau-workbook-xml` skill.
- A subagent does the worksheet rebuild through that skill and publishes a
  review copy only (Task 5). A `tableauserverclient` publish drops embedded
  credentials (skill: _What a publish drops_), so a scripted production publish
  would break the scheduled refresh.
- The owner opens the agent's `.twbx` in Desktop, the skill's only real check,
  and publishes to production from there with credentials embedded (Task 6).

## Global Constraints

- Measure: `cumulative_y1_gpa_unweighted`; bands: `gpa_band_label` (`3.5+`,
  `3.0-3.49`, `2.5-2.99`, `2.0-2.49`, `below 2.0`) with colors `#001e62`,
  `#2f5fc4`, `#b6c0cf`, `#f9a21a`, `#d8342f`.
- Window: `graduation_year` between `current_academic_year - 5` and
  `current_academic_year + 1`. Today (`current_academic_year: 2026`) that is the
  classes of 2021 to 2027.
- Population: no new logic. The extract's existing filters (`rn_year = 1`,
  `is_enrolled_recent`, `enroll_status in (0, 2, 3)`, not out of district,
  Newark and Camden) already mean "enrolled at the end of the year".
- Each student counts once, at their last completed (non-`is_projected`) 11th
  grade year.
- Worksheet name stays `GPA - Splay over time`, in the same place in the
  `Trends` container.
- Total row on top, labelled `All high schools`. Columns labelled
  `Class of YYYY`. Above each bar `≥3.0: NN%`; below each bar `n=NNN`.
- Year logic lives in dbt. Tableau may read the flags but must not compute a
  window from dates.
- Only the owner publishes to production.
- PR body and commits carry no band-level counts (small cells); class totals
  only.

## Review Focus

1. **The total row disagrees with the school rows.** Its `n` per class must
   equal the sum of the school rows' `n`, and its band shares must come from
   distinct students, not averaged school percentages. Checked in Task 6 against
   the answer key.
2. **Region parameter set to Newark or Camden.** The total row must follow it
   (Camden shows only KHS, total equal to KHS). Checked in Task 6 by rendering
   with `Region` set each way.
3. **July rollover.** The window must move with `current_academic_year` and
   nothing else. Pinned by the second unit test in Task 1.
4. **A current 11th grader whose `graduation_year` falls in the window.** Their
   projected row must not count. Pinned by student 103 in the Task 1 unit test.
5. **The dashboard school filter.** Picking a school elsewhere on the dashboard
   must not blank the other school rows. Checked in Task 6 by rendering with a
   school selected.

---

### Task 1: Flags on `rpt_tableau__gpa_cumulative_year`

**Files:**

- Modify:
  `<wt>/src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gpa_cumulative_year.sql`
- Modify:
  `<wt>/src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gpa_cumulative_year.yml`

**Interfaces:**

- Produces: `is_last_completed_grade_11` (`boolean`, never null when
  `grade_level` and `is_projected` are non-null) and `is_grade_11_trend_class`
  (`boolean`, never null) on `rpt_tableau__gpa_cumulative_year`.

- [ ] **Step 1: Install packages in the fresh worktree**

Run: `uv run dbt deps --project-dir <wt>/src/dbt/kipptaf` Expected: packages
installed, exit 0.

- [ ] **Step 2: Write the failing unit tests**

Add a `unit_tests:` block to the properties file. Student numbers are fake.
Every `given` row for `int_extracts__student_enrollments` also carries
`rn_year: 1`, `is_out_of_district: false`, `enroll_status: 0`,
`is_enrolled_recent: true` (except student 108's 2024 row), `region: Newark`,
`schoolid: 73252`, `_dbt_source_project: kippnewark`; every
`int_powerschool__gpa_cumulative_year` row carries the matching `studentid`,
`academic_year`, `schoolid`, `_dbt_source_project`, plus `grade_level`,
`is_projected`, and `cumulative_y1_gpa_unweighted: 3.1`.
`int_powerschool__gpa_cumulative` is `rows: []`; `int_powerschool__gpa_term`
gets 1 row (`yearid: 35, gpa_y1: 3.0, _dbt_source_project: kippnewark`).

Test `rpt_tableau__gpa_cumulative_year__grade_11_flags`, with
`overrides: {vars: {current_academic_year: 2026}}`:

| studentid | student_number | graduation_year | academic_year, grade_level, is_projected                                                                                    |
| --------- | -------------- | --------------- | --------------------------------------------------------------------------------------------------------------------------- |
| 1         | 101            | 2025            | (2022, 10, false), (2023, 11, false)                                                                                        |
| 2         | 102            | 2026            | (2023, 11, false), (2024, 11, false) — repeated 11th                                                                        |
| 3         | 103            | 2027            | (2025, 10, false), (2026, 11, true) — in 11th now                                                                           |
| 4         | 104            | 2020            | (2018, 11, false)                                                                                                           |
| 5         | 105            | 2028            | (2026, 10, true)                                                                                                            |
| 6         | 106            | null            | (2023, 11, false)                                                                                                           |
| 7         | 107            | 2021            | (2019, 11, false)                                                                                                           |
| 8         | 108            | 2025            | (2023, 11, false), (2024, 11, false) — left during the repeat year: its 2024 enrollment row has `is_enrolled_recent: false` |

`expect` columns, every row: `student_number`, `academic_year`,
`is_last_completed_grade_11`, `is_grade_11_trend_class`:

```yaml
- {
    student_number: 101,
    academic_year: 2022,
    is_last_completed_grade_11: false,
    is_grade_11_trend_class: true,
  }
- {
    student_number: 101,
    academic_year: 2023,
    is_last_completed_grade_11: true,
    is_grade_11_trend_class: true,
  }
- {
    student_number: 102,
    academic_year: 2023,
    is_last_completed_grade_11: false,
    is_grade_11_trend_class: true,
  }
- {
    student_number: 102,
    academic_year: 2024,
    is_last_completed_grade_11: true,
    is_grade_11_trend_class: true,
  }
- {
    student_number: 103,
    academic_year: 2025,
    is_last_completed_grade_11: false,
    is_grade_11_trend_class: true,
  }
- {
    student_number: 103,
    academic_year: 2026,
    is_last_completed_grade_11: false,
    is_grade_11_trend_class: true,
  }
- {
    student_number: 104,
    academic_year: 2018,
    is_last_completed_grade_11: true,
    is_grade_11_trend_class: false,
  }
- {
    student_number: 105,
    academic_year: 2026,
    is_last_completed_grade_11: false,
    is_grade_11_trend_class: false,
  }
- {
    student_number: 106,
    academic_year: 2023,
    is_last_completed_grade_11: true,
    is_grade_11_trend_class: false,
  }
- {
    student_number: 107,
    academic_year: 2019,
    is_last_completed_grade_11: true,
    is_grade_11_trend_class: true,
  }
- {
    student_number: 108,
    academic_year: 2023,
    is_last_completed_grade_11: true,
    is_grade_11_trend_class: true,
  }
```

Student 108's 2024 row is dropped by the model's existing `is_enrolled_recent`
filter, so it has no `expect` row; this pins the spec's call that a repeater who
left counts at the last 11th-grade year they finished enrolled.

Test `rpt_tableau__gpa_cumulative_year__trend_window_rolls`, with
`overrides: {vars: {current_academic_year: 2027}}`, given students 105 and 107
only, expects `is_grade_11_trend_class`: 105 `true`, 107 `false`.

These two tests satisfy the spec's "at most one flagged row per student" check:
a data test for it would be unfailable given the model's
`(student_number, academic_year)` grain test (`.claude/rules/dbt-yaml.md`,
_Choosing a test_), so none is added.

- [ ] **Step 3: Run the unit tests to see them fail**

Run:
`uv run dbt test --select "rpt_tableau__gpa_cumulative_year,test_type:unit" --project-dir <wt>/src/dbt/kipptaf --target dev --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod 2>&1 | tail -n 20`
Expected: both FAIL on the missing columns.

- [ ] **Step 4: Add the 2 columns to the model SQL**

Follow `.claude/rules/dbt-sql.md` S6 ordering. `is_grade_11_trend_class` is a
simple function, placed before the existing `is_latest_graded_year` logical:

```sql
-- current 12th graders (current_academic_year + 1) and the 6 classes before them
ifnull(
    e.graduation_year between {{ var("current_academic_year") }} - 5
    and {{ var("current_academic_year") }} + 1,
    false
) as is_grade_11_trend_class,
```

`is_last_completed_grade_11` contains a window, so it goes last, after the 2
`case` columns. The window runs after the model's `where`, so it only sees kept
rows. `false and null` is `false` in BigQuery, so non-grade-11 rows never come
out null:

```sql
gcy.grade_level = 11
and not gcy.is_projected
and gcy.academic_year = max(
    if(gcy.grade_level = 11 and not gcy.is_projected, gcy.academic_year, null)
) over (partition by e.student_number) as is_last_completed_grade_11,
```

- [ ] **Step 5: Add the 2 columns to the properties file**

`data_type: boolean`, `config.meta.contains_pii: true` on both. Descriptions:

- `is_last_completed_grade_11`: True on the student's latest grade 11 row that
  is not the current year's projection, among the rows this model keeps (the
  student was enrolled at the end of that year). A student who repeated 11th
  grade is true only on the later year; a student in 11th grade now is false on
  every row. The Cumulative GPA Monitor's by-class chart counts each student
  once on this row.
- `is_grade_11_trend_class`: True when `graduation_year` is one of the current
  12th graders' class (`current_academic_year` + 1) or the 6 classes before it.
  Moves forward each July with the `current_academic_year` variable. False when
  `graduation_year` is null.

- [ ] **Step 6: Run the unit tests and build to see them pass**

Run:
`uv run dbt build --select rpt_tableau__gpa_cumulative_year --project-dir <wt>/src/dbt/kipptaf --target dev --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod 2>&1 | tail -n 20`
Expected: both unit tests PASS, the view builds, the grain test passes.

- [ ] **Step 7: Lint and commit**

Run, with cwd `<wt>`:
`/workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gpa_cumulative_year.sql src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gpa_cumulative_year.yml </dev/null 2>&1 | tail -n 20`
Expected: no lint findings (formatting is the hook's).

Commit: `feat(kipptaf): flag last completed 11th-grade year and trend classes`
with `Refs #6478`.

---

### Task 2: Pass the flags through `rpt_tableau__gpa_goal_progress` and document them

**Files:**

- Modify:
  `<wt>/src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gpa_goal_progress.sql`
- Modify:
  `<wt>/src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gpa_goal_progress.yml`
- Modify: `<wt>/docs/models/academic-health-data-model.md`

**Interfaces:**

- Consumes: `is_last_completed_grade_11`, `is_grade_11_trend_class` from Task 1.
- Produces: the same 2 columns on `rpt_tableau__gpa_goal_progress`, the
  Monitor's only data source.

- [ ] **Step 1: Add `cy.is_last_completed_grade_11` and
      `cy.is_grade_11_trend_class` to the select list**, after
      `cy.gpa_band_as_of_today_label`.

- [ ] **Step 2: Add both to the properties file**, `data_type: boolean`,
      description
      `Passthrough from rpt_tableau__gpa_cumulative_year, unchanged.` (same form
      as the neighbouring passthroughs), `contains_pii: true`.

- [ ] **Step 3: Build and check the contract**

Run:
`uv run dbt build --select rpt_tableau__gpa_cumulative_year rpt_tableau__gpa_goal_progress --project-dir <wt>/src/dbt/kipptaf --target dev --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod 2>&1 | tail -n 20`
Expected: both views build, contract enforcement passes, all tests pass.

- [ ] **Step 4: Update the reference page**

In `docs/models/academic-health-data-model.md`:

- _Bands and flags_ table: add both flags, one line each, meaning only.
- `rpt_tableau__gpa_cumulative_year` _Worth knowing_: add 1 bullet saying the 2
  flags drive the by-class chart and that the window follows
  `current_academic_year`.
- `rpt_tableau__gpa_goal_progress` _What it shows_: add "the share of each
  graduating class in each band at the end of 11th grade, by high school".

- [ ] **Step 5: Lint and commit**

`trunk check --force --no-fix` on the 3 files (same form as Task 1). Commit:
`feat(kipptaf): pass grade 11 trend flags to the Cumulative GPA Monitor` with
`Refs #6478`.

---

### Task 3: Answer key, then the PR

**Files:**

- Create:
  `/tmp/claude-1000/-workspaces-teamster/3869dc22-9b10-402f-b03b-c931c0df44ad/scratchpad/gpa-grade11-answer-key.sql`
  (session scratchpad; not committed)

- [ ] **Step 1: Write the answer-key query**

```sql
select
    graduation_year,
    coalesce(school, 'All high schools') as school,
    count(*) as n,
    round(100 * countif(gpa_band_label in ('3.5+', '3.0-3.49')) / count(*)) as pct_ge_3_0,
from `<dataset>.rpt_tableau__gpa_goal_progress`
where is_last_completed_grade_11 and is_grade_11_trend_class and gpa_band_label is not null
group by grouping sets ((graduation_year, school), (graduation_year))
```

`<dataset>` is the dev schema in this task and `kipptaf_tableau` after merge.

- [ ] **Step 2: Run it against the dev build and reconcile**

Run it through the BigQuery MCP on the dev relation Task 2 built. Then run the
same grouping on prod without the flags (grade 11, not `is_projected`,
`row_number()` over `student_number, graduation_year` by `academic_year desc`,
keep 1). Expected: identical rows. As of 2026-11-24 the class totals were 203,
210, 288, 428, 415, 419, 431 for 2021 to 2027.

- [ ] **Step 3: Push and open the PR**

Body from `.github/pull_request_template.md`, `Refs #6478`, class totals only
(Global Constraints). Merging this linked branch closes #6478 regardless of the
body; reopen it after merge, since Tasks 4 to 6 remain.

- [ ] **Step 4: Offer CI watch and `claude-review` follow-up** per the root
      CLAUDE.md _Pull requests and CI_.

---

### Task 4: Owner refreshes the data source and republishes

Starts after the PR merges and prod rebuilds both views.

- [ ] **Step 1 (Claude): Confirm the columns are in prod.** Through the BigQuery
      MCP:
      `select column_name from teamster-332318.kipptaf_tableau.INFORMATION_SCHEMA.COLUMNS where table_name = 'rpt_tableau__gpa_goal_progress' and column_name like 'is_%grade_11%'`.
      Expected: 2 rows. Then tell the owner Task 4 Step 2 can start.

- [ ] **Step 2 (owner): Refresh and republish.** Open the production workbook in
      Desktop, refresh `rpt_tableau__gpa_goal_progress (kipptaf_tableau)`,
      confirm both new fields appear, refresh the extract, and republish to
      production with no design change.

- [ ] **Step 3 (Claude): Confirm the republish carried the fields.** Download
      the workbook through the Tableau MCP into a new empty scratchpad folder
      and check that `<remote-name>is_last_completed_grade_11</remote-name>` and
      `<remote-name>is_grade_11_trend_class</remote-name>` appear in the
      `rpt_tableau__gpa_goal_progress` data source. Expected: both present.

- [ ] **Step 4 (Claude): Ask where the review copy goes.** Ask the owner which
      non-production project the review copy should land in (skill step 6). With
      no preference, use `GPA-monitor-temp`,
      `c74d8e08-b856-4430-a759-ebacb061e376`. Record the id for Task 5.

---

### Task 5: Rebuild the worksheet with `tableau-workbook-xml` (subagent)

Dispatch one subagent on the most capable model. Its prompt carries: the spec
path, this task's build target and limits verbatim, the project id from Task 4
Step 4, the workbook LUID `b3c14d67-3130-46ac-82a0-0637a5cc2da5`, and the
instruction to invoke the `tableau-workbook-xml` skill before any other step.

Limits the agent works under:

- Review copies only. It never publishes to production and never restores a
  revision.
- It follows the skill's loop in order: pull fresh with `include_extract=True`,
  write each assertion before its edit, edit, run `check_twb.py --ref` and
  `check_geometry.py` on `Cumulative GPA Monitor`, repack, publish as
  `ZZ-REVIEW 2026-MM-DD Academic & Gradebook Health Suite` with `hidden_views`,
  render and look.
- Grand totals and second-axis labels have no precedent in the skill. It probes
  each on a 1-sheet `ZZ-PROBE` copy before the full build. If grand totals
  cannot render as a labelled top row, it falls back to a separate total
  worksheet stacked directly above the school worksheet with matching column
  widths, and reports the fallback.

Build target on `GPA - Splay over time`:

- [ ] **Filters.** Remove the `academic_year` (2021 to 2025),
      `grade_level = 11`, and `is_projected = false` filters. Add
      `is_last_completed_grade_11 = True` and `is_grade_11_trend_class = True`.
      Keep `Region filter = True`, the `is_hs_honors_program` filter, and
      `gpa_band_label` excluding null. Remove this sheet from the dashboard
      school filter's target worksheets.
- [ ] **Layout.** `graduation_year` (discrete) on Columns, shown as
      `Class of YYYY`. `school` (discrete) on Rows. Column grand totals on top,
      labelled `All high schools` and shaded. Keep the existing
      `Measured (projected)` percent-of-total computed along `gpa_band_label`,
      and its band colors.
- [ ] **Headers.** A second column header line: `11th grade YYYY–YY` from
      `graduation_year - 2` and `graduation_year - 1`, or `Current 12th graders`
      where
      `[graduation_year] = {FIXED : MAX(IF [is_grade_11_trend_class] THEN [graduation_year] END)}`.
      That reads the dbt flag; it computes no window of its own.
- [ ] **Labels.** A second axis, following the pattern on `GPA - Change`: a text
      mark above each bar labelled `≥3.0: NN%` from the existing `At 3.0+` calc
      over `Measured (projected)`, and one below labelled `n=NNN`. Synchronize
      and hide the second axis. Segment labels inside the bars stay as they are.
- [ ] **Title, caption, tooltip.** Title:
      `Cumulative GPA at the end of 11th grade, by graduating class`. Caption,
      word for word:
      `Who counts: students enrolled on the last day of their 11th-grade year. GPA: cumulative unweighted, as of the end of 11th grade. A student who repeated 11th grade counts once, at their last 11th-grade year. NLH has data from the class of 2023 and KHS from the class of 2024.`
      Tooltip, copying the form of a working tooltip in this workbook:
      `Class of <graduation_year> · <school>`, then
      `<band>: <count> of <Measured> students (<pct>)`, then
      `At 3.0 or above: <At 3.0+> of <Measured> (<pct>)`.
- [ ] **Container.** The `Trends` container gets enough height for 4 rows.
      `GPA - Trend by grade` stays unchanged.

The agent's hand-over (skill step 8): the `.twbx` path, the review copy's LUID,
the target's revision number before the publish, what it verified and what it
inferred, the regions it rendered, the probe outcome for grand totals and the
second axis, and that embedded credentials were not carried. Check that report
with the checks in `.claude/context/agent.md` before relying on it.

---

### Task 6: Check the review copy, then production

- [ ] **Step 1: Run the answer key against prod** (`kipptaf_tableau`).

- [ ] **Step 2: Render the review copy's Cumulative GPA Monitor** through the
      Tableau MCP with the `Trends` container shown, 3 times: `Region` All,
      Newark, Camden. Crop the chart and compare every `n=` and `≥3.0:` label to
      the answer key. Expected: all match; Camden shows only KHS with a total
      equal to KHS.

- [ ] **Step 3: Render once with a school picked** in the dashboard school
      filter. Expected: all 3 school rows still show.

- [ ] **Step 4: Report to the owner** what matched and what a render cannot show
      (tooltip text, the show/hide click).

- [ ] **Step 5 (owner): Open the agent's `.twbx` in Desktop**, hover one bar,
      and publish to production from Desktop with credentials embedded.

- [ ] **Step 6: Check production.** Render production once (Region All) against
      the answer key, comment the result on #6478, and close it.
