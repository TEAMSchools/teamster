# Score Sat Measures in Partial DIBELS PM Rounds Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** On the Literacy Dashboard's Aimline tabs, score each measure a student
sat in a partial PM round, while the Round view and the ⏳ Round Incomplete tile
keep counting the student as unfinished.

**Architecture:** One rule change in `int_amplify__pm_met_criteria_aimline`
(drop the round-completion override at measure-standard and measure-name-code
grain; key the round grain on `completed_test_round` directly), proven by a dbt
unit test and a dev-vs-prod diff. One formula change in the Literacy Dashboard
workbook so the ⏳ tile reads round completion instead of the category column.
The workbook ships first; on today's data it changes no number.

**Tech Stack:** dbt (BigQuery), Tableau `.twb` XML through the
`tableau-workbook-xml` skill, BigQuery MCP for verification.

**Spec:**
`docs/superpowers/specs/2026-11-24-dibels-partial-round-measures-design.md`

All paths below are relative to the worktree
`/workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-dibels-partial-round-measures`.
Run every command from there. `--state` is always the absolute main-checkout
manifest `/workspaces/teamster/src/dbt/kipptaf/target/prod`.

## Global Constraints

- Internal-method rows (`model_type = 'Internal'`) do not change, in any column.
- Round-grain columns do not change: `aimline_round_category`,
  `pm_round_status`, `round_benchmark_status`, `round_test_status`.
- The ⏳ tile counts the same students it counts today, at every granularity.
- The rule applies to every academic year; no cutover year.
- The ⏳ tile's title does not change.
- Ship order: the workbook edit reaches production before the dbt PR merges.
- A production workbook publish needs the user to name production in a typed
  message and then answer yes to "Are you sure? This overwrites the production
  workbook and is visible to the whole network."
- No student-level values in commits, the PR, or issue comments; aggregates
  only.

## Review Focus

1. A partial round whose sat measure has no published aimline verdict should
   read `No Aimline Data, ...` split by benchmark, not `Round Incomplete`.
   Pinned by student 1002 in Task 1.
2. A two-standard code (ORF) sat in a partial round should roll up to its worst
   standard at measure-name-code grain. Pinned by student 1001 in Task 1.
3. Removing the measure-grain override must not let `aimline_round_category`
   score a partial round, because it counted `aimline_category` values. Pinned
   by 1001 and 1002 expecting `Round Incomplete` in Task 1.
4. A complete round must still score normally at every grain. Pinned by student
   1003 in Task 1.
5. The ⏳ tile at Round granularity, where `BAN Category` is
   `aimline_round_category` rather than a measure column, must still match
   today. Pinned by the Round render in Task 4.

---

### Task 1: Score sat measures in `int_amplify__pm_met_criteria_aimline`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/amplify/intermediate/int_amplify__pm_met_criteria_aimline.sql`
  (`measure_category` CTE, `round_category` CTE, final select)
- Modify:
  `src/dbt/kipptaf/models/amplify/intermediate/properties/int_amplify__pm_met_criteria_aimline.yml`
  (add `unit_tests:`; rewrite the descriptions of `aimline_category`,
  `aimline_round_category`, `measure_name_code_aimline_benchmark_status`, and
  the last paragraph of `measure_standard_goal_status`)

**Interfaces:**

- Consumes: nothing from other tasks.
- Produces: the same column names and types as today. Only values change:
  `aimline_category` and `measure_name_code_aimline_benchmark_status` never read
  `Round Incomplete`; `aimline_round_category` reads `Round Incomplete` exactly
  when `not completed_test_round`.

- [ ] **Step 1: Write the failing unit test**

Add a top-level `unit_tests:` block to the properties yml. Name:
`int_amplify__pm_met_criteria_aimline__partial_round_scores_sat_measures`.
Fixture shared values: `academic_year: 2026`, `region: Newark`, grade 3
(`assessment_grade: 3`, `assessment_grade_int: 3`, `grade: 3`,
`grade_level: 3`), season `BOY->MOY` (`period` on assessments, `admin_season` on
the other two), `round_number: 2`, level `Below Benchmark`
(`overall_probe_eligible` on assessments, `measure_standard_level` on the gate).
Scalars unquoted.

- `ref("int_google_sheets__dibels__expected_assessments_by_levels")`: 3 rows,
  `pm_goal_criteria: AND`, `assessment_include: null`, `pm_goal_include: null`,
  `start_date: 2026-10-19`, `end_date: 2026-10-26`, and
  `expected_measure_standard` / `benchmark_goal` of `Reading Fluency (ORF)` /
  70, `Reading Accuracy (ORF-Accu)` / 95, `Maze` / 10.
- `ref("int_amplify__all_assessments")`, every row `assessment_type: PM`,
  `model_type: Aimline`. Columns `student_number`, `measure_standard`,
  `measure_name_code`, `measure_standard_score`, `met_measure_standard_goal`:

  | student | measure_standard            | code          | score | met  |
  | ------- | --------------------------- | ------------- | ----- | ---- |
  | 1001    | Reading Fluency (ORF)       | ORF           | 40    | 0    |
  | 1001    | Reading Accuracy (ORF-Accu) | ORF           | 96    | 1    |
  | 1002    | Maze                        | Comprehension | 12    | null |
  | 1003    | Reading Fluency (ORF)       | ORF           | 75    | 1    |
  | 1003    | Reading Accuracy (ORF-Accu) | ORF           | 90    | 1    |
  | 1003    | Maze                        | Comprehension | 5     | 0    |

- `ref("int_students__dibels_participation_roster")`: one row per student,
  `model_type: Aimline`; `completed_test_round` false for 1001 and 1002, true
  for 1003 (`completed_test_round_int` to match).

Expect, every row listing the same five columns:

| student_number | measure_standard            | aimline_category                      | measure_name_code_aimline_benchmark_status | aimline_round_category |
| -------------- | --------------------------- | ------------------------------------- | ------------------------------------------ | ---------------------- |
| 1001           | Reading Fluency (ORF)       | Below Aimline                         | Below Aimline                              | Round Incomplete       |
| 1001           | Reading Accuracy (ORF-Accu) | Meeting Aimline, Meeting Benchmark    | Below Aimline                              | Round Incomplete       |
| 1002           | Maze                        | No Aimline Data, Meeting Benchmark    | No Aimline Data                            | Round Incomplete       |
| 1003           | Reading Fluency (ORF)       | Meeting Aimline, Meeting Benchmark    | Meeting Aimline, Not Yet at Benchmark      | Below Aimline          |
| 1003           | Reading Accuracy (ORF-Accu) | Meeting Aimline, Not Yet at Benchmark | Meeting Aimline, Not Yet at Benchmark      | Below Aimline          |
| 1003           | Maze                        | Below Aimline                         | Below Aimline                              | Below Aimline          |

- [ ] **Step 2: Run the test and confirm it fails**

If `src/dbt/kipptaf/dbt_packages/` is missing, first run
`uv run dbt deps --project-dir src/dbt/kipptaf`.

Run:
`uv run dbt test --select "int_amplify__pm_met_criteria_aimline,test_type:unit" --project-dir src/dbt/kipptaf --target dev --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod 2>&1 | tail -n 40`

Expected: FAIL. The diff shows `Round Incomplete` in `aimline_category` and
`measure_name_code_aimline_benchmark_status` for students 1001 and 1002.

- [ ] **Step 3: Change the SQL**

- `aimline_category`: delete the first branch,
  `when not completed_test_round then 'Round Incomplete'`.
- `measure_name_code_aimline_benchmark_status`: delete the
  `when n_code_incomplete > 0` branch and the `n_code_incomplete` window.
- `aimline_round_category`: replace `when n_round_incomplete > 0` with
  `when not completed_test_round`, and delete the `n_round_incomplete` window.

- [ ] **Step 4: Run the test and confirm it passes**

Same command as Step 2. Expected: PASS.

- [ ] **Step 5: Prove the round-grain guard is load-bearing**

Temporarily put `when n_round_incomplete > 0` back (with its window) in place of
`when not completed_test_round`, rerun Step 2's command, and confirm it FAILS on
`aimline_round_category` for 1001 (`Below Aimline`) and 1002
(`No Aimline Data`). Restore the Step 3 version and rerun to PASS.

- [ ] **Step 6: Rewrite the four descriptions**

State the new rule: a measure the student sat carries its verdict whether or not
the round is finished; only the round grain holds an unfinished round out as
`Round Incomplete`, keyed on `completed_test_round`. Remove every sentence
saying the measure-grain columns read `Round Incomplete`. Keep the Not Tested
versus Round Incomplete distinction (no row means never sat). Follow
`.claude/rules/comments.md`: no dates, issue numbers, or history.

- [ ] **Step 7: Lint and commit**

Run:
`/workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/kipptaf/models/amplify/intermediate/int_amplify__pm_met_criteria_aimline.sql src/dbt/kipptaf/models/amplify/intermediate/properties/int_amplify__pm_met_criteria_aimline.yml </dev/null 2>&1 | tail -n 20`

Expected: no lint issues (a formatting-only flag is fixed by the commit hook).

```bash
git add -u
git commit -m "feat(dbt): score sat measures in partial DIBELS aimline PM rounds"
```

End the message with the `Co-Authored-By` trailer and `Refs #6493`.

---

### Task 2: Prove the change on real data and update the extract's descriptions

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__dibels_dashboard.yml`
  (model description, roughly lines 38-57; `aimline_round_category`,
  `aimline_category`, `measure_name_code_aimline_benchmark_status` column
  descriptions; the note near line 1014 contrasting another column with
  `aimline_category`)

**Interfaces:**

- Consumes: Task 1's column behavior.
- Produces: the dev views `int_amplify__pm_met_criteria_aimline` and
  `rpt_tableau__dibels_dashboard` in your `zz_<user>_kipptaf_*` schemas, used
  only for this task's queries.

- [ ] **Step 1: Build both views into dev**

Run:
`uv run dbt build --select int_amplify__pm_met_criteria_aimline rpt_tableau__dibels_dashboard --project-dir src/dbt/kipptaf --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod 2>&1 | tail -n 30`

Expected: both models and their tests pass. The grain warning tracked on #6022
may still warn. Find the dev schemas through the `dbt-local-dev` skill's _Local
dev schema naming_ section.

- [ ] **Step 2: Everything except the two changed columns is identical**

With the BigQuery MCP, run both directions of
`select * except (aimline_category, measure_name_code_aimline_benchmark_status)`
from the prod `kipptaf_tableau.rpt_tableau__dibels_dashboard`, `except distinct`
the same select from the dev view. Also compare `count(*)`.

Expected: 0 rows each way, and equal counts.

- [ ] **Step 3: Only Round Incomplete rows moved**

Per side, group Aimline PM rows by `aimline_category`, and separately by
`measure_name_code_aimline_benchmark_status`.

Expected: dev has no `Round Incomplete` in either column. Every other category
count in dev is at least its prod count. The increases add up to the prod
`Round Incomplete` count (3,899 `aimline_category` rows across academic years
2025 and 2026 on 2026-11-24; it grows as testing continues). Internal rows have
identical counts.

- [ ] **Step 4: Rewrite the extract's descriptions**

Same rule as Task 1 Step 6, in the extract's terms: the measure-grain
`Aimline and Benchmark` columns score every measure sat;
`aimline_round_category` keeps `Round Incomplete` from the roster's
`round_test_status`; the ⏳ tile reads `round_test_status` together with
`measure_test_status`.

- [ ] **Step 5: Lint and commit**

Run trunk check on the yml as in Task 1 Step 7. Commit:
`docs(dbt): describe partial-round scoring on the DIBELS dashboard extract`.

---

### Task 3: Update the DIBELS reference doc and skill

**Files:**

- Modify: `docs/models/dibels-dashboard-data-model.md`
- Modify: `.claude/skills/dibels-dashboard/references/aimline-method.md`
- Modify: `.claude/skills/dibels-dashboard/references/diagnosing.md`

**Interfaces:**

- Consumes: Task 1's rule and the ⏳ formula from the spec.
- Produces: nothing code reads.

- [ ] **Step 1: Find every statement of the old rule**

Run:
`rg -n "Round Incomplete|BAN|ban5" docs/models/dibels-dashboard-data-model.md .claude/skills/dibels-dashboard/`

Each hit that says `Aimline and Benchmark` holds a sat measure out at Measure
Standard or Measure, or that the BANs always count `aimline_category`, is in
scope.

- [ ] **Step 2: Edit the reference doc**

- In the decisions table, the "Partial rounds" row's Decision says sat measures
  are scored at Measure Standard and Measure on every comparison item; Round
  granularity and the ⏳ tile keep `Round Incomplete` (academics, 2026-11-24).
  Status: built.
- The "Uncoloured No Aimline Data categories" row:
  `No Aimline Data, Meeting Benchmark` is `#1170aa` and
  `No Aimline Data, Not Yet at Benchmark` is `#ffbc79`. Status: built in the
  workbook.
- The _Labels and reporting_ bullet that says any unfinished round reads
  `Round Incomplete` "even if a measure the student sat was below": restate it
  for the Round grain only.

- [ ] **Step 3: Edit the skill**

- `aimline-method.md`: in the _Aimline_ bullet near line 203 and the
  partial-rounds bullet near line 518, state the new rule. Replace "Do not align
  the two" with what is now true (all comparison items score sat measures at
  Measure Standard and Measure; only Round holds them out). Rewrite the BAN
  paragraph near line 367: the BANs follow Granularity through the
  `BAN Category` calc; the ⏳ tile alone reads `round_test_status` and
  `measure_test_status`, so the tiles can add to more than 100% while a round is
  open, by design.
- `diagnosing.md`: change the BAN query's `ban5_incomplete` to count
  `round_test_status = 'Round Incomplete' and measure_test_status = 'Tested'`.
- Per `.claude/rules/claude-md-editing.md`: state behavior, not evidence; no run
  ids or counts.

- [ ] **Step 4: Lint and commit**

Run trunk check on the three files. Commit:
`docs(dbt): record the 2026-11-24 partial-round decision for the DIBELS dashboard`.

---

### Task 4: Repoint the ⏳ tile in the Literacy Dashboard workbook

Use the `tableau-workbook-xml` skill for every step; its loop, scripts, and
publish gate govern. Workbook LSID `72b16a4a-b3a9-47e5-bdff-ae641d9ee9e6`. Work
in the session scratchpad, not the repo.

**Files:**

- Modify: a fresh download of the production `.twb` (not committed)

**Interfaces:**

- Consumes: the extract columns `round_test_status`, `measure_test_status`,
  `student_number`, all already in the published datasource.
- Produces: `BAN 5 - Numerator` (`[Calculation_154811283872104470]`) with the
  formula
  `COUNTD(IF [round_test_status] = 'Round Incomplete' AND [measure_test_status] = 'Tested' THEN [student_number] END)`.

- [ ] **Step 1: Pull fresh and record the restore point**

Download with `include_extract=True`. Record `updated_at` and the revision
number. Diff its worksheet and parameter lists against revision 105 in the
scratchpad (`litdash/prod.twb`); stop and report if anything outside
`<datasources>` changed.

- [ ] **Step 2: Write the assertion and confirm it fails on the base**

The assertion checks that all 3 definitions of
`[Calculation_154811283872104470]` (the datasource, plus the
`Region Overview PM Aim - BAN 5` and `School Overview PM Aim - BAN 5` dependency
blocks) carry the new formula, and that both of those worksheets'
`<datasource-dependencies>` declare `[round_test_status]` and
`[measure_test_status]`. Run it on the base. Expected: FAIL.

- [ ] **Step 3: Edit**

Replace the formula in exactly 3 places, asserting 3 matches of the old formula
before and 0 after. Copy the two `<column>` definitions verbatim from the
datasource into both worksheets' dependency blocks. Parse with `ET.fromstring`
before writing.

- [ ] **Step 4: Check**

Run the assertion (expected PASS) and `check_twb.py <out.twb> --ref <base.twb>`
(expected exit 0). No zone changed, so `check_geometry.py` does not apply; say
so in the hand-over.

- [ ] **Step 5: Repack and publish a review copy**

Ask the user which non-production project to use (default `GPA-monitor-temp`).
Publish as `ZZ-REVIEW-2026-11-24 Literacy Dashboard` with `hidden_views` set per
the skill.

- [ ] **Step 6: Render and compare**

Render the base and the review copy, same size, for `Region Overview PM Aim` and
`School Overview PM Aim`, with the Aimline Granularity Parameter set explicitly
to `Measure Standard`, `Measure`, and `Round`, and the Comparison Item at
`Aimline and Benchmark`. Crop the BAN row.

Expected: every ⏳ value and every other tile identical between base and review
copy at all three granularities.

- [ ] **Step 7: Production publish (human gate)**

Stop and hand the user the review-copy link and the comparison. Publish to
production only after the two typed confirmations in Global Constraints. After
the publish, tell the user to open the production workbook and check it, and
give the pre-publish revision number as the restore point. Delete the throwaway
test file.

---

### Task 5: Open the PR

**Files:** none new.

- [ ] **Step 1: Lint everything the branch changed**

Run trunk check with `--force --no-fix` on every file in
`git diff --name-only origin/main...HEAD`. Expected: no issues.

- [ ] **Step 2: Ask the DIBELS push question**

Ask, in these words: "We need to update the skill and ref doc — do you authorize
the update checks?" On yes, recheck Task 3's edits against the final diff. On
no, say in the PR body that the reference doc and skill were not rechecked.

- [ ] **Step 3: Push and open the PR**

Push the branch. Open the PR from `.github/pull_request_template.md` with
`Closes #6493`. Say in the body: merge only after the ⏳ tile edit is live in
production (Task 4 Step 7); the Cube facts (#6473) should adopt the same rule.
Report aggregates only. End the body with the generated-with line.

- [ ] **Step 4: Offer CI watch and review response**

Offer both, per root `CLAUDE.md` _Pull requests and CI_.
