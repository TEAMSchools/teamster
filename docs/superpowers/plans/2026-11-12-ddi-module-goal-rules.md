# DDI Module Goal Rules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move every goal value the DDI Suite workbook hard-codes into the goals
lookup, so its 3 goal calculations read data instead of literals.

**Architecture:** A new "Module Goal Rules" tab on the Assessments sheet holds
the ET, CRQ and TP rules. A new domain intermediate expands each rule to the
Illuminate subject areas of its discipline. `rpt_tableau__ddi_dashboard` keeps
`grade_goal`, `school_goal` and `region_goal` raw and adds 3
`*_goal_differentiated` columns that apply the QA goal (PR #6357) and the rules.
After merge, the workbook's 3 goal calculations point at the new columns.

**Tech Stack:** Google Sheets (Sheets connector), dbt on BigQuery (`kipptaf`),
Tableau `.twb` XML (`tableau-workbook-xml` skill).

**Spec:** No separate spec. Issue #6117 plus the decisions below, made on
2026-11-11 and 2026-11-12 in the session that wrote this plan.

## Decisions

1. Everything ships in PR #6357 (draft), branch
   `anthonygwalters/feat/claude-k2-qa-goal-column`, worktree
   `/workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-k2-qa-goal-column`.
   The PR keeps `Refs #6117`.
2. The ET, CRQ and TP rules live on a new "Module Goal Rules" tab, one row per
   region, module type, discipline and grade range.
3. The view adds `grade_goal_differentiated`, `school_goal_differentiated` and
   `region_goal_differentiated`. The raw goal columns go back to the plain
   lookup values, which moves #6357's QA override into the new columns. The live
   workbook ignores the new columns until its calculations switch, so no goal is
   double-counted between merge and republish.
4. Grade 9 ET keeps today's behavior: no rule, so the plain lookup goal. It is
   an open question for T&L (see the end of this plan).
5. The workbook edit deletes the 7 unused goal parameters and leaves the i-Ready
   80% lesson goal on `O3 - i-Ready` as it is.

## Global Constraints

- Rule values come from the production DDI Suite (luid
  `6d82b643-59a8-4106-b2f9-97ddf7f638e7`, updated 2026-11-11 23:42 UTC):
  - ET: 0.80 for NJ ELA, grades 0-8.
  - ET: 0.80 for NJ, any subject, grades 10-12.
  - CRQ: lookup goal + 0.10 for NJ Math, grades 1-8.
  - TP: lookup goal + 0.10 for NJ ELA, Math and Science, grades 3-12.
- NJ means `region` in `Newark`, `Camden`, `Paterson`. Miami rows get
  differentiated goals equal to the raw goals.
- Precedence, highest first: a fixed rule goal, then the QA goal on QA and CRQ
  modules, then a rule offset added to the raw goal, then the raw goal.
- A rule row with a blank discipline applies to every subject.
- Disciplines come from `Illuminate_Subject_Area` → `Discipline` in
  `stg_google_sheets__assessments__course_subject_crosswalk`.
- A Sheets named range must cover whole columns. The connector saves it bounded
  to the grid's rows, so the user resets it in the Sheets UI.
- Shared staging writes (`--target staging`) go to the user's terminal; the
  auto-mode classifier blocks them.
- A production workbook publish needs the user's 2 typed confirmations
  (`tableau-workbook-xml` step 6).

## Review Focus

1. K-2 CRQ Math, grades 1-2: expect the QA goal, not QA goal + 0.10. The CRQ
   rule covers grades 1-8, so precedence alone keeps the QA goal. Pinned in the
   Task 4 oracle query.
2. A row with no lookup goal row (for example an HS subject the Academic Goals
   tab lacks): ET still shows 0.80, because a fixed goal does not need the raw
   goal. Pinned in the Task 4 oracle query.
3. A subject the crosswalk does not map (Dance, Physical Education): only the
   blank-discipline ET rule for grades 10-12 applies. Pinned in the Task 3 unit
   test and the Task 4 oracle query.
4. A subject the crosswalk maps to 2 disciplines would match 2 rules and fan out
   the view. The Task 3 uniqueness test and the view's grain test both fail at
   `error`.
5. Crosswalk disciplines are wider than the workbook's `[Discipline]` group: 11
   subjects (`Algebra II Honors`, `Algebra IIA`, `Algebra IIB`, `AP Calculus`,
   `AP Calculus AB`, `AP Statistics`, `Pre-Calculus`, `AP Literature`,
   `Composition 100`, `Composition 200`, `Composition 300`, `Writing`) map to
   Math or ELA in the crosswalk and to `Other` in the workbook. On 2026-11-12
   they had 0 NJ ET, CRQ or TP rows, so the oracle query expects no difference;
   a difference on one of them is a behavior change to report, not a bug.

---

### Task 1: Module Goal Rules tab

**Files:**

- Modify: Assessments sheet `1G2z9rwXsFaMdFL6iOYdfQTVjZ7bctXMyz_Q09IhP4QE`, new
  tab `Module Goal Rules`, new named range `src_assessments__module_goal_rules`

**Interfaces:**

- Produces: columns A:G in this order, header row 1: `Region`, `Module Type`,
  `Discipline`, `Grade Min`, `Grade Max`, `Goal`, `Goal Offset`.

- [ ] **Step 1: Load the `anthropic-skills:google-workspace` skill and its
      Sheets reference, then add the tab, the header and these 18 rows in 1
      `update_spreadsheet` batch (`addSheet`, `updateCells`, `addNamedRange`
      over columns A:G).**

  For each region in `Newark`, `Camden`, `Paterson`, write these 6 rows. A blank
  cell is blank, not 0.

  | Module Type | Discipline | Grade Min | Grade Max | Goal | Goal Offset |
  | ----------- | ---------- | --------- | --------- | ---- | ----------- |
  | ET          | ELA        | 0         | 8         | 0.8  |             |
  | ET          |            | 10        | 12        | 0.8  |             |
  | CRQ         | Math       | 1         | 8         |      | 0.1         |
  | TP          | ELA        | 3         | 12        |      | 0.1         |
  | TP          | Math       | 3         | 12        |      | 0.1         |
  | TP          | Science    | 3         | 12        |      | 0.1         |

- [ ] **Step 2: Read the tab back with `get_values` over
      `'Module Goal Rules'!A1:G19`.** Expected: 19 rows, values as above.
- [ ] **Step 3: Ask the user to set the named range to `'Module Goal Rules'!A:G`
      in Data → Named ranges.** Verify with `get_spreadsheet`
      (`fields: ["namedRanges"]`): the range has no `startRowIndex` or
      `endRowIndex`.

### Task 2: Staging model for the rules

**Files:**

- Modify: `src/dbt/kipptaf/models/google/sheets/sources-external.yml` (new table
  after `src_google_sheets__assessments__academic_goals`)
- Create:
  `src/dbt/kipptaf/models/google/sheets/staging/stg_google_sheets__assessments__module_goal_rules.sql`
- Create:
  `src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__assessments__module_goal_rules.yml`
- Create:
  `src/dbt/kipptaf/tests/stg_google_sheets__assessments__module_goal_rules__overlap.sql`
- Modify: `src/dbt/kipptaf/tests/properties.yml`

**Interfaces:**

- Consumes: Task 1's tab and named range.
- Produces: `stg_google_sheets__assessments__module_goal_rules` with columns
  `Region` string, `Module_Type` string, `Discipline` string, `Grade_Min` int64,
  `Grade_Max` int64, `Goal` float64, `Goal_Offset` float64.

- [ ] **Step 1: Add the source**
      `src_google_sheets__assessments__module_goal_rules` on the same
      spreadsheet URI, `sheet_range: src_assessments__module_goal_rules`,
      `skip_leading_rows: 1`, asset key
      `[kipptaf, google, sheets, assessments, module_goal_rules]`, and the 7
      columns above declared at the source level in sheet order.
- [ ] **Step 2: Write the staging model:** `select *` from the source
      `where Region is not null` (drops phantom grid rows). Contract columns as
      in Interfaces.
- [ ] **Step 3: Add tests**, each with `config: severity: error`:
  - model-level `dbt_utils.unique_combination_of_columns` on `Region`,
    `Module_Type`, `Discipline`, `Grade_Min`;
  - `not_null` on `Region`, `Module_Type`, `Grade_Min`, `Grade_Max`;
  - model-level `dbt_utils.expression_is_true` with
    `(Goal is null) != (Goal_Offset is null)` and with `Grade_Min <= Grade_Max`;
  - singular test `..._overlap`: 1 row per pair of rows with the same `Region`
    and `Module_Type`, overlapping `Grade_Min`-`Grade_Max` ranges, and
    disciplines that are equal or where either is null. Keep 1 direction of each
    pair. Register it in `tests/properties.yml` with `severity: error` and
    `tags: [google_sheet]`, following the existing
    `stg_google_sheets__assessments__academic_goals__sheet_duplicates` entry.
- [ ] **Step 4: Stage your dev copy and build:**

  ```bash
  cd /workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-k2-qa-goal-column
  uv run dbt run-operation stage_external_sources --args "select: google_sheets.src_google_sheets__assessments__module_goal_rules" --vars '{ext_full_refresh: true}' --target dev --project-dir src/dbt/kipptaf
  uv run dbt build --select stg_google_sheets__assessments__module_goal_rules --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod --project-dir src/dbt/kipptaf
  ```

  Expected: 1 model OK, all tests PASS, 18 rows.

- [ ] **Step 5: Prove the overlap test fails without editing the sheet.**
      Compile the test (`uv run dbt compile --select ..._overlap ...`), replace
      its relation with the dev staging table `union all` 1 extra row
      (`'Newark', 'ET', null, 8, 9, 0.8, null`), and run it with the BigQuery
      MCP. Expected: 1 row (it overlaps the Newark ET ELA 0-8 row). Editing the
      live sheet instead would trigger prod rebuilds of every tab on that
      spreadsheet.
- [ ] **Step 6: Commit** (`feat(dbt): stage the DDI module goal rules sheet`).

### Task 3: Rules expanded to subject areas

**Files:**

- Create:
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__module_goal_rules.sql`
- Create:
  `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__module_goal_rules.yml`

**Interfaces:**

- Consumes: Task 2's staging model;
  `stg_google_sheets__assessments__course_subject_crosswalk`
  (`Illuminate_Subject_Area`, `Discipline`).
- Produces: `int_assessments__module_goal_rules`, 1 row per `region`,
  `module_type`, `illuminate_subject_area` and `grade_min`. Columns `region`,
  `module_type`, `illuminate_subject_area` (null means every subject),
  `grade_min`, `grade_max`, `goal`, `goal_offset`.

- [ ] **Step 1: Write the failing unit test**
      `unit_int_assessments__module_goal_rules_expands_by_discipline`, both
      inputs `format: sql` (the staging model is new). Given rules: Newark ET
      ELA 0-8 goal 0.8; Newark ET blank 10-12 goal 0.8; Newark TP Math 3-12
      offset 0.1. Given crosswalk rows: (`Text Study`, `ELA`), (`English 100`,
      `ELA`) twice, (`Mathematics`, `Math`), (`Algebra I`, `Math`), (`Dance`,
      null). Expect exactly these 5 rows:

  | module_type | illuminate_subject_area | grade_min | grade_max | goal | goal_offset |
  | ----------- | ----------------------- | --------- | --------- | ---- | ----------- |
  | ET          | Text Study              | 0         | 8         | 0.8  | null        |
  | ET          | English 100             | 0         | 8         | 0.8  | null        |
  | ET          | null                    | 10        | 12        | 0.8  | null        |
  | TP          | Mathematics             | 3         | 12        | null | 0.1         |
  | TP          | Algebra I               | 3         | 12        | null | 0.1         |

  All rows have `region` `Newark`.

- [ ] **Step 2: Run it and confirm it fails** (model missing):
      `uv run dbt test --select int_assessments__module_goal_rules --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod --project-dir src/dbt/kipptaf`
- [ ] **Step 3: Write the model.** A CTE projects distinct
      (`Illuminate_Subject_Area`, `Discipline`) from the crosswalk (annotate
      `grain projection, not dup-masking`). Rules with a discipline inner join
      it on discipline; rules without one keep a null subject. `union all` the 2
      branches with the same column list. Lowercase output names.
- [ ] **Step 4: Add the YAML:** description, every column described, and
      model-level `unique_combination_of_columns` on `region`, `module_type`,
      `illuminate_subject_area`, `grade_min` at `severity: error`.
- [ ] **Step 5: Build and test:**
      `uv run dbt build --select stg_google_sheets__assessments__module_goal_rules+1 --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod --project-dir src/dbt/kipptaf`.
      Expected: unit test PASS, uniqueness PASS.
- [ ] **Step 6: Commit**
      (`feat(dbt): expand DDI module goal rules to subject areas`).

### Task 4: Differentiated goals in the DDI view

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__ddi_dashboard.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__ddi_dashboard.yml`

**Interfaces:**

- Consumes: Task 3's model; `int_assessments__academic_goals.qa_goal` and
  `is_qa_goal_module` (already on the branch).
- Produces: `grade_goal_differentiated`, `school_goal_differentiated`,
  `region_goal_differentiated`, all float64. Task 6 points the workbook at these
  3 names.

- [ ] **Step 1: In the `identifiers` CTE**, left join
      `int_assessments__module_goal_rules` twice: once on `region`,
      `module_type`, `subject_area = illuminate_subject_area` and the grade
      range; once on `region`, `module_type`, the grade range and
      `illuminate_subject_area is null`. Grade range:
      `r.grade_level between <alias>.grade_min and <alias>.grade_max`. Add
      `module_goal` and `module_goal_offset`, each a `coalesce` of the 2 joins.
- [ ] **Step 2: In the ES/MS and HS branches**, put `g.grade_goal`,
      `g.school_goal` and `g.region_goal` back as plain columns right after
      `g.organization_goal`. At the end of each branch, add 1 `case` per level
      implementing the precedence in Global Constraints. In the walkthrough
      branch, match the new order with `null as` columns.
- [ ] **Step 3: YAML:** restore the 3 raw goal descriptions to "from the
      academic goals sheet" with no QA override; describe the 3 new columns by
      the precedence.
- [ ] **Step 4: Build both changed chains together** (a narrower selection
      repoints the unmerged goals models at prod):

  ```bash
  uv run dbt build --select stg_google_sheets__assessments__academic_goals+ stg_google_sheets__assessments__module_goal_rules+ --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod --project-dir src/dbt/kipptaf
  ```

  Expected: 0 errors; the only warning is the existing
  `..._academic_goals__sheet_duplicates`.

- [ ] **Step 5: Run the oracle query.** It rebuilds the workbook's current
      formula in SQL from the dev view's raw goals and compares it to the dev
      differentiated columns. Expected: 0 rows.

  ```sql
  with
      d as (
          select
              region, grade_level, module_type, subject_area,
              grade_goal, school_goal, region_goal,
              grade_goal_differentiated, school_goal_differentiated,
              region_goal_differentiated,
              region in ('Newark', 'Camden', 'Paterson') as is_nj,
              case
                  when subject_area in ('AP Language', 'English 100', 'English 200', 'English 300', 'English 400', 'Text Study') then 'ELA'
                  when subject_area in ('Algebra I', 'Algebra I MS', 'Algebra II', 'AP Pre Calculus', 'Geometry', 'Geometry Honors', 'Math 4', 'Mathematics') then 'Math'
                  when subject_area in ('Biology', 'Chemistry', 'Human Anatomy and Physiology', 'Physics', 'Science') then 'Science'
                  else 'Other'
              end as discipline,
          from `teamster-332318.zz_anthonygwalters_kipptaf_tableau.rpt_tableau__ddi_dashboard`
          where student_number is not null
      ),
      qa as (
          select * from unnest([
              struct('Newark' as region, 0 as grade_level, 'ELA' as discipline, 0.78 as goal),
              ('Newark', 1, 'ELA', 0.63), ('Newark', 2, 'ELA', 0.76),
              ('Newark', 0, 'Math', 0.90), ('Newark', 1, 'Math', 0.79), ('Newark', 2, 'Math', 0.71),
              ('Camden', 0, 'ELA', 0.61), ('Camden', 1, 'ELA', 0.63), ('Camden', 2, 'ELA', 0.76),
              ('Camden', 0, 'Math', 0.83), ('Camden', 1, 'Math', 0.77), ('Camden', 2, 'Math', 0.53),
              ('Paterson', 0, 'ELA', 0.78), ('Paterson', 1, 'ELA', 0.50), ('Paterson', 2, 'ELA', 0.64),
              ('Paterson', 0, 'Math', 0.90), ('Paterson', 1, 'Math', 0.78), ('Paterson', 2, 'Math', 0.79)
          ])
      ),
      expected as (
          select
              d.*,
              case
                  when is_nj and d.grade_level < 9 and d.discipline = 'ELA' and module_type = 'ET' then 'fixed'
                  when is_nj and d.grade_level > 9 and module_type = 'ET' then 'fixed'
                  when is_nj and d.grade_level <= 2 and d.discipline in ('ELA', 'Math') and module_type in ('QA', 'CRQ') then 'qa'
                  when is_nj and d.grade_level between 1 and 8 and d.discipline = 'Math' and module_type = 'CRQ' then 'offset'
                  when is_nj and d.grade_level > 2 and d.discipline in ('ELA', 'Math', 'Science') and module_type = 'TP' then 'offset'
                  else 'raw'
              end as branch,
              qa.goal as qa_goal,
          from d
          left join qa
              on d.region = qa.region
              and d.grade_level = qa.grade_level
              and d.discipline = qa.discipline
      )
  select region, grade_level, module_type, subject_area, branch, count(*) as n_rows,
  from expected
  where (
      case branch
          when 'fixed' then grade_goal_differentiated = 0.8 and school_goal_differentiated = 0.8 and region_goal_differentiated = 0.8
          when 'qa' then grade_goal_differentiated = qa_goal and school_goal_differentiated = qa_goal and region_goal_differentiated = qa_goal
          when 'offset' then abs(grade_goal_differentiated - (grade_goal + 0.1)) < 1e-9 and abs(school_goal_differentiated - (school_goal + 0.1)) < 1e-9 and abs(region_goal_differentiated - (region_goal + 0.1)) < 1e-9
          else grade_goal_differentiated is not distinct from grade_goal and school_goal_differentiated is not distinct from school_goal and region_goal_differentiated is not distinct from region_goal
      end
  ) is not true
  group by region, grade_level, module_type, subject_area, branch
  order by n_rows desc
  ```

  `is not true` counts a null comparison as a mismatch. A null raw goal under
  `offset` gives a null comparison, and the workbook also shows null there, so
  check any `offset` row the query returns for a null raw goal before treating
  it as a defect.

- [ ] **Step 6: Confirm the raw goals match prod.** Group dev and prod by
      region, year, grade, module type, subject and the 4 raw goal columns;
      `except distinct` both ways. Expected: 0 groups either way (prod still has
      the pre-#6357 raw goals).
- [ ] **Step 7: Lint and commit.** Run
      `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <changed files> </dev/null`
      from the worktree; commit
      (`feat(dbt): add differentiated DDI goals from the module goal rules`).

### Task 5: Ship the PR

**Files:**

- Modify: `docs/models/ddi-stack-data-model.md` (sheet inventory row for the new
  tab; Yearly upkeep step 3 names both tabs)

- [ ] **Step 1: Update the DDI stack doc**, lint it with the same trunk command,
      and commit (`docs: add the module goal rules tab to the DDI stack model`).
- [ ] **Step 2: Hand the user the shared staging command** for the new source
      and wait for them to run it:
      `uv run dbt run-operation stage_external_sources --args "select: google_sheets.src_google_sheets__assessments__module_goal_rules" --vars '{ext_full_refresh: true}' --target staging --project-dir src/dbt/kipptaf`
      from the worktree. Verify with `INFORMATION_SCHEMA.COLUMNS` on
      `zz_stg_kipptaf_google_sheets`: 7 columns.
- [ ] **Step 3: Push** (confirm dbt Cloud is not mid-run first, per
      `pr-ci-review`).
- [ ] **Step 4: Rewrite the PR #6357 title and body** from
      `.github/pull_request_template.md`: title
      `feat(dbt): move DDI Suite goal rules into the goals lookup`; keep
      `Refs #6117`; list the grade 9 ET question and Review Focus item 5.
- [ ] **Step 5: Post a follow-up on #6192** replacing the earlier note (comment
      `6799827269`): the rules now live on the Module Goal Rules tab and in
      `int_assessments__module_goal_rules`, the precedence is the one in Global
      Constraints, and Cube reads marts only, so PR D decides whether the rules
      get a mart.
- [ ] **Step 6: Mark #6357 ready for review** (re-runs `claude-review`), then
      run `pr-ci-review` for CI and findings.

### Task 6: Workbook edit (after merge and an extract refresh)

**Files:**

- Modify: DDI Suite workbook, luid `6d82b643-59a8-4106-b2f9-97ddf7f638e7`
  (review copy first)

**Interfaces:**

- Consumes: Task 4's 3 column names, live in the refreshed extract.

- [ ] **Step 1: Load `tableau-workbook-xml` and follow its loop.** Pull fresh
      with the extract and record `updated_at`. Confirm the 3
      `*_goal_differentiated` fields appear in the embedded datasource. If they
      do not, stop: the owner refreshes the data source in Desktop first.
- [ ] **Step 2: Write the assertions before editing** and confirm they fail on
      the base: every copy of the 3 calculations (11 of
      `[Calculation_5386727405859295237]` Grade Goal, 4 of
      `[Grade Goal (Differentiated) (copy)_82612946412630026]` School Goal, 4 of
      `[School Goal (Differentiated) (copy)_82612946415091724]` Region Goal) has
      the formula `[grade_goal_differentiated]`, `[school_goal_differentiated]`
      or `[region_goal_differentiated]`; no `TEMPORARY`, `THEN 0.8` or `+ .1`
      remains in them; and the 7 parameters `[Parameter 3]`,
      `[Individual Proficiency Goal Parameter]`, `[LLI Comment (copy)]`,
      `[Goal % (copy 2)]`, `[PARCC Goal % - 3 (copy) (copy)]`,
      `[PARCC ELA Goal % - 3 (copy)]` and `[PARCC ELA Goal % - 4 (copy)]` are
      gone.
- [ ] **Step 3: Edit, run `check_twb.py --ref`, repack, publish a dated
      `ZZ-REVIEW` copy to `GPA-monitor-temp`** (or the project the user names).
- [ ] **Step 4: Render base and review copy** for `DKI View`,
      `Module Dashboard`, `Mastery Over Time [School]` and
      `Mastery Over Time [Region]`. Expected: identical goal lines, goal
      distances and goal statuses.
- [ ] **Step 5: Production publish** only after the user names production and
      answers yes to the skill's confirmation. Then ask the user to open the
      production workbook and check it, and close #6117.

## Open questions

- **Grade 9 ET (for T&L):** the workbook's ET rules skip grade 9, so grade 9 ET
  rows show the plain lookup goal. Is that intended, or should grade 9 get 80%
  like grades 10-12? If 80%, change the Newark, Camden and Paterson ET
  blank-discipline rows to `Grade Min` 9; no code change.
- **Task 6 field refresh:** whether a Server extract refresh adds the 3 new
  columns to the embedded datasource without a Desktop "Refresh data source" is
  not verified. Task 6 Step 1 checks it.
