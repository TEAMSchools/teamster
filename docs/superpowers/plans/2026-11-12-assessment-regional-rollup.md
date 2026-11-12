# Region-Aware Assessment Roll-Up Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Internal assessment copies with the same tags combine for a region
only when both are tagged for that region, so each region's scores carry its own
title, date, report card tags and band set.

**Architecture:** The members model keeps one row per copy and its group column
is renamed to `tag_group_assessment_id`. A new crosswalk model at one row per
copy and region carries the regional `canonical_assessment_id`. The canonical
model gets one row per regional group, the scaffold reads the crosswalk, and
everything downstream follows the scaffold's group ID. A last, separately
revertible commit makes the performance band set follow the regional group.

**Tech Stack:** dbt on BigQuery (`src/dbt/kipptaf`), dbt unit tests, BigQuery
read-only MCP for dev-versus-prod checks, trunk for lint.

**Spec:**
`docs/superpowers/specs/2026-11-12-assessment-regional-rollup-design.md`. Read
it first. Closes #6308.

## Global Constraints

- Work only in the worktree
  `/workspaces/teamster/.claude/worktrees/anthonygwalters/fix/claude-assessment-regional-dates`
  (called `$wt` below), with `git -C $wt` and `uv run` from it. Never touch the
  main checkout's files. Never bare `dbt`.
- Every dbt command uses these flags, called `$dbt_flags` below:
  `--project-dir $wt/src/dbt/kipptaf --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod`.
  Never `--target staging` or `--target prod`.
- Invoke the `dbt-local-dev` skill before the first build. Dev relations land in
  `zz_<github user>_kipptaf_<schema>`; find the name with
  `INFORMATION_SCHEMA.SCHEMATA`.
- Dev-versus-prod checks run through the BigQuery read-only MCP against the dev
  schema and `kipptaf_assessments` / `kipptaf_marts`. Always build with the same
  selection, `int_assessments__assessments_members+`, before comparing; a
  narrower selection points changed parents back at prod.
- Do not edit inside the `row_number()` pick in `int_assessments__score_anchors`
  (A5).
- The group change (Task 2) is one commit: producer and every consumer of the
  group ID and date together.
- The band change (Task 3) is its own commit after Task 2, so it can be reverted
  alone.
- S and A rules in `.claude/rules/dbt-*.md` apply to lines you add or change.
  Comments follow `.claude/rules/comments.md`: no counts, dates or history.
- No student-level values in commits, the PR or the issue. Counts only.
- Every commit message ends with the trailer
  `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`.
- Mock a ref with `format: sql` in a unit test when the fixture needs a column
  this branch adds or an array.

## Review Focus

1. A region typed twice in one tag, or a trailing comma (an empty-string
   region): the crosswalk stays unique and carries the empty string like any
   other region. Pinned in Task 2, Step 1.
2. A tag group whose first copy has no region while a later copy does: the tag
   group ID keeps a canonical row with an empty `regions_array`. Pinned in Task
   2, Step 2.
3. An out-of-grade (replacement) sitting on a copy that is not tagged for the
   student's region, while another copy in the tag group is: the row takes that
   region's group and `is_region_tagged` is true. Pinned in Task 2, Step 3.
4. A student rostered under two regions for one tag group in the same year (a
   mid-year move between Camden and Newark): after the split they can hold a row
   in each regional group. Expected: reported as a count, not hidden. Pinned in
   Task 2, Step 9.
5. A standard that only another region's copies carry: a row in a group whose
   copies lack it gets a null band set and no label, and is not dropped. Pinned
   in Task 3, Steps 4 and 6.

---

### Task 1: Rename the group column on the members model

No behavior change. Every reader keeps today's values under the new name.

**Files:**

- Modify:
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__assessments_members.sql`
  and `properties/int_assessments__assessments_members.yml`
- Modify: `int_assessments__assessments_canonical.sql` and its yml,
  `int_assessments__scaffold.sql` and its yml (members fixtures only),
  `int_assessments__performance_bands.sql` and its yml, in the same folder
- Modify:
  `src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_enrollment_scoped.sql`,
  `marts/dimensions/dim_assessments.sql` and `properties/dim_assessments.yml`,
  `marts/bridges/bridge_assessment_expectations_enrollment_scoped.sql`,
  `marts/bridges/bridge_assessment_expectations_student_scoped.sql` and its yml,
  `marts/bridges/bridge_assessment_administration_members.sql` (disabled)
- Modify:
  `src/dbt/kipptaf/tests/int_assessments__assessments_members__no_cross_source_canonical.sql`
  and its entry in `tests/properties.yml`

**Interfaces:**

- Produces: `int_assessments__assessments_members.tag_group_assessment_id`
  (int64), replacing `canonical_assessment_id` with the same values. Every other
  model keeps its own `canonical_assessment_id` column name and values.

- [ ] **Step 1: Rename in the members model and its yml.** Column, description
      and the three unit tests' expected rows. The description says it is the
      lowest `assessment_id` among copies that share tags, and that the regional
      group lives in `int_assessments__assessment_region_groups`.
- [ ] **Step 2: Point each reader at the new name.** In each file above, read
      `tag_group_assessment_id` where it read the members' group column, and
      alias it back to `canonical_assessment_id` where the model outputs that
      name. Update members fixtures in the unit tests of the scaffold, band
      model, `dim_assessments` and the student-scoped bridge.
- [ ] **Step 3: Check the one reader the build cannot.** A missed reader fails
      the Step 4 build with `Name canonical_assessment_id not found`, except the
      disabled bridge, which never compiles.

Run:
`rg -n "a\.canonical_assessment_id" $wt/src/dbt/kipptaf/models/marts/bridges/bridge_assessment_administration_members.sql`
Expected: no output.

- [ ] **Step 4: Run unit tests and build.**

Run:
`uv run dbt build --select "int_assessments__assessments_members+" $dbt_flags 2>&1 | tail -n 30`
Expected: no errors; warn tests may warn as they do in prod.

- [ ] **Step 5: Prove parity with prod.** For `int_assessments__response_rollup`
      and `fct_assessment_scores_enrollment_scoped`, dev and prod have the same
      `count(*)` and the same count of distinct keys (roll-up: student, source,
      `assessment_id`, `is_replacement`, `response_type`, `response_type_id`;
      fact: `assessment_score_key`), and an anti-join of fact keys in either
      direction returns 0 rows. If prod rebuilt mid-session, re-read the prod
      baseline before judging a difference.
- [ ] **Step 6: Lint and commit.**

```bash
cd $wt && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix $(git diff --name-only) </dev/null
git -C $wt add -u
git -C $wt commit -m "refactor(dbt): rename members group column to tag_group_assessment_id" -m "Refs #6308"
```

---

### Task 2: Regional groups (one commit)

**Files:**

- Create:
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__assessment_region_groups.sql`
  and `properties/int_assessments__assessment_region_groups.yml`
- Modify: `int_assessments__assessments_canonical.sql` and yml,
  `int_assessments__scaffold.sql` and yml
- Modify: `fct_assessment_scores_enrollment_scoped.sql`, both
  `bridge_assessment_expectations_*` models and the student-scoped yml,
  `bridge_assessment_administration_members.sql` (disabled; SQL only)
- Modify: `properties/int_assessments__response_rollup.yml`,
  `int_assessments__score_anchors.yml`,
  `int_assessments__resolved_section_enrollments.yml`,
  `int_assessments__college_assessment_practice.yml` (descriptions that say what
  the group is)

**Interfaces:**

- Consumes: `int_assessments__assessments_members.tag_group_assessment_id`.
- Produces:
  - `int_assessments__assessment_region_groups`: one row per `source`,
    `assessment_id`, `region`, with `tag_group_assessment_id` and
    `canonical_assessment_id` (int64), internal assessments only.
  - `int_assessments__assessments_canonical`: same grain and columns, plus
    `tag_group_assessment_id`; `regions_array` holds only the regions whose
    group the row is.
  - `int_assessments__scaffold.canonical_assessment_id`: the regional group ID
    on internal rows.

- [ ] **Step 1: Write the crosswalk's unit test,
      `test_region_groups_split_by_region`.** Members fixture (`format: sql`),
      as
      `source, assessment_id, tag_group_assessment_id, regions_assessed_array, is_internal_assessment`:

```text
illuminate, 101, 101, ['Camden'],            true
illuminate, 102, 101, ['Newark', 'Camden'],  true
illuminate, 103, 101, ['Newark', 'Newark'],  true
illuminate, 201, 201, ['Newark', ''],        true
illuminate, 202, 201, ['Miami', 'Newark'],   true
illuminate, 301, 301, ['Camden'],            false
apex,       101, 101, ['Miami'],             true
```

Expected rows, as
`source, assessment_id, region, tag_group_assessment_id, canonical_assessment_id`:

```text
illuminate, 101, Camden, 101, 101
illuminate, 102, Camden, 101, 101
illuminate, 102, Newark, 101, 102
illuminate, 103, Newark, 101, 102
illuminate, 201, Newark, 201, 201
illuminate, 201, '',     201, 201
illuminate, 202, Miami,  201, 202
illuminate, 202, Newark, 201, 201
apex,       101, Miami,  101, 101
```

- [ ] **Step 2: Write the canonical model's unit test,
      `test_canonical_one_row_per_regional_group`.** Members: copies 101
      (`['Camden']`) and 102 (`['Newark']`) in tag group 101 with different
      titles and dates; copies 401 (`[]`) and 402 (`['Camden']`) in tag
      group 401. Crosswalk rows to match. Expected, as
      `canonical_assessment_id, tag_group_assessment_id, title, regions_array`:
      101 / 101 / title of 101 / `['Camden']`; 102 / 101 / title of 102 /
      `['Newark']`; 401 / 401 / title of 401 / `[]`; 402 / 401 / title of 402 /
      `['Camden']`. Each row's `administered_date` is its own copy's date.
- [ ] **Step 3: Extend the scaffold's unit tests.** Add the crosswalk as an
      input to `test_replacement_region_tagged` and add
      `test_rows_take_regional_group`: tag group 1 holds copy 1 (`['Newark']`)
      and copy 2 (`['Camden']`), grade 5. Expected `canonical_assessment_id` and
      `is_region_tagged`:
  - a Newark student rostered to copy 1: 1, null
  - a Camden student rostered to copy 2: 2, null
  - a Camden-school student out of grade who sat copy 1: 2, true
  - a Paterson-school student out of grade who sat copy 1: 1, false
- [ ] **Step 4: Run the three unit tests and see them fail.**

Run:
`uv run dbt test --select "test_type:unit,int_assessments__assessment_region_groups test_type:unit,int_assessments__assessments_canonical test_type:unit,int_assessments__scaffold" $dbt_flags 2>&1 | tail -n 20`
Expected: the new tests fail or error (model not found, column not found).

- [ ] **Step 5: Build the crosswalk.** Spec section 2 gives the SQL. Add a
      grain-projection `distinct` (S12) so a region typed twice yields one row.
      The yml carries descriptions and a
      `dbt_utils.unique_combination_of_columns` test on `source`,
      `assessment_id`, `region` at `severity: error`.
- [ ] **Step 6: Rewrite the canonical model.** Its ID set is every
      `canonical_assessment_id` in the crosswalk plus every internal
      `tag_group_assessment_id`. Each row's attributes come from the members row
      whose `assessment_id` equals the ID, so remove the
      `dbt_utils.deduplicate`. `regions_array` aggregates the crosswalk's
      regions for that ID and is `[]` when there are none. Add
      `tag_group_assessment_id`. Keep the uniqueness test; update the
      description, which names the old pick.
- [ ] **Step 7: Change the scaffold.**
  - `assessment_region_scaffold` joins the crosswalk on `source` and
    `assessment_id` in place of the `unnest`, and takes `region` and
    `canonical_assessment_id` from it.
  - The replacement branch joins the canonical model on `source`,
    `tag_group_assessment_id` and `str.region in unnest(c.regions_array)`.
    `canonical_assessment_id` is
    `coalesce(c.canonical_assessment_id, a.tag_group_assessment_id)` and
    `is_region_tagged` is `c.canonical_assessment_id is not null`.
  - The non-internal and Apex branches are unchanged from Task 1.
  - Update the yml descriptions of `canonical_assessment_id` and
    `is_region_tagged`.
- [ ] **Step 8: Change the marts.**
  - Scores fact, `internal_assessments`: join the canonical model on
    `rr.assessment_id`, not on the member's tag group.
  - Both expectation bridges: hash and join on `sc.canonical_assessment_id`.
    Keep reading raw `academic_year` and `module_code` from the members row.
  - Disabled members bridge: read `region` and `canonical_assessment_id` from
    the crosswalk. Do not enable it.
  - `dim_assessments` stays on `tag_group_assessment_id` from Task 1.
- [ ] **Step 9: Build and verify against prod.**

Run:
`uv run dbt build --select "int_assessments__assessments_members+" $dbt_flags 2>&1 | tail -n 30`
Expected: no errors, all unit tests pass.

Then, dev against prod, internal non-replacement Illuminate rows:

1. Roll-up: join on student, response type, response type ID and
   `to_json_string(assessment_ids)`. Same row count both sides, 0 rows unmatched
   either way, 0 rows where `percent_correct` differs. Report separately the
   count of students who hold rows in more than one regional group of one tag
   group (Review Focus 4); it is expected to be small and is not a failure.
2. Rows whose `assessment_id` differs from prod: by school year, close to
   SY24-25 1,177, SY25-26 13,735, SY26-27 2,708 student-assessments (prod drifts
   daily), 0 in earlier years, and every one in a tag group with more than one
   regional group.
3. Keys: 0 internal `assessment_administration_key` values on the scores fact or
   either expectation bridge missing from `dim_assessment_administrations`. For
   rows whose group ID did not change, `assessment_score_key` matches prod.
4. Dates: Literacy G3 ET3 SY25-26, Newark and Paterson rows carry 2026-01-28
   (group 205680) and Camden rows carry 2025-09-22 (group 190084).
5. CARAT: 0 `assessment_id` values in
   `int_assessments__college_assessment_practice` sit in a tag group with more
   than one regional group.

- [ ] **Step 10: Lint and commit.**

```bash
cd $wt && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix $(git diff --name-only) src/dbt/kipptaf/models/assessments/intermediate/int_assessments__assessment_region_groups.sql src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__assessment_region_groups.yml </dev/null
git -C $wt add -u
git -C $wt add src/dbt/kipptaf/models/assessments/intermediate/int_assessments__assessment_region_groups.sql src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__assessment_region_groups.yml
git -C $wt commit -m "fix(dbt): roll internal assessments up by region" -m "Refs #6308"
```

---

### Task 3: Band set follows the regional group (own commit)

**Files:**

- Create:
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__group_performance_bands.sql`
  and `properties/int_assessments__group_performance_bands.yml`
- Modify: `int_assessments__response_rollup.sql` and yml
- Modify:
  `src/dbt/kipptaf/models/extracts/deanslist/rpt_deanslist__mod_standards.sql`

**Interfaces:**

- Consumes: `int_assessments__assessment_region_groups`,
  `int_assessments__assessments_canonical`,
  `int_assessments__assessments_members` (`assessment_id`,
  `tag_group_assessment_id`, `is_internal_assessment`), and
  `int_assessments__performance_bands` (`assessment_id`, `response_type`,
  `response_type_id`, `performance_band_set_id`, `canonical_response_type_id`),
  which this task does not change.
- Produces: `int_assessments__group_performance_bands`, one row per
  `canonical_assessment_id`, `response_type`, `response_type_id` (the canonical
  response type ID), with `performance_band_set_id` (nullable). Illuminate only.

A group's copies are: for a canonical row with a non-empty `regions_array`, the
crosswalk's copies for that ID; for one with an empty `regions_array`, every
member of the tag group; for a non-internal assessment, itself.

The band set for a group, response type and canonical response type ID:

- null when the group's records for it have more than one `response_type_id` and
  their band sets differ or any is null (today's split-standard rule);
- otherwise the band set of the first record by `assessment_id`, then
  `response_type_id`.

- [ ] **Step 1: Write the unit test,
      `test_group_bands_follow_regional_first_copy`.** Crosswalk: copy 1 in
      Camden's group 1; copy 2 in Camden's group 1 and Newark's group 2 (tag
      group 1). Copy 3 alone in group 3. Copy 9 non-internal. Members and
      canonical fixtures match: canonical rows 1 (`['Camden']`), 2
      (`['Newark']`) and 3 (`['Camden']`). Band rows, as
      `assessment_id, response_type, response_type_id, performance_band_set_id, canonical_response_type_id`:

```text
1, overall,  -1,  10, -1
2, overall,  -1,  20, -1
2, standard, 500, 20, 500
3, overall,  -1,  40, -1
3, standard, 600, 40, 600
3, standard, 601, 41, 600
9, overall,  -1,  30, -1
```

Expected, as
`canonical_assessment_id, response_type, response_type_id, performance_band_set_id`:

```text
1, overall,  -1,  10
1, standard, 500, 20
2, overall,  -1,  20
2, standard, 500, 20
3, overall,  -1,  40
3, standard, 600, null
9, overall,  -1,  30
```

- [ ] **Step 2: Run it and see it fail.**

Run:
`uv run dbt test --select "test_type:unit,int_assessments__group_performance_bands" $dbt_flags 2>&1 | tail -n 10`
Expected: error, model not found.

- [ ] **Step 3: Build the model and its yml.** Uniqueness test on the three
      grain columns at `severity: error`.
- [ ] **Step 4: Move the roll-up's band set lookup.** `responses_keyed` keeps
      the band model join for `canonical_response_type_id` only.
      `responses_merged` drops the band set from its select and `group by`.
      `scaffold_responses` left joins the new model on
      `s.canonical_assessment_id`, `asr.response_type` and
      `asr.response_type_id` and takes `canonical_performance_band_set_id` from
      it. Update the two roll-up unit tests' inputs to match, and add a case to
      `test_int_assessments__response_rollup_split_standard`: a sitting scored
      on a standard with no row in the new model keeps its row, with a null
      `performance_band_label`.
- [ ] **Step 5: Point `rpt_deanslist__mod_standards` at the new model.** Join on
      `r.assessment_id = canonical_assessment_id` and
      `response_type = 'overall'`.
- [ ] **Step 6: Build and verify.**

Run:
`uv run dbt build --select "int_assessments__assessments_members+" $dbt_flags 2>&1 | tail -n 30`
Expected: no errors.

Then, dev against prod, internal non-replacement Illuminate `overall` rows with
a `percent_correct`:

1. `is_mastery` differs only in these tag groups, with counts close to: SY26-27
   Chemistry ET1 Newark 67; SY25-26 Literacy G3 ET4 Camden 22, G4 ET1 Camden 9,
   G4 ET4 Camden 12, G7 ET1 Newark 20. Any other module is a defect.
2. 0 rows that had a `performance_band_set_id` in prod and lack one in dev.
3. Report, for replacement rows and for `standard` and `group` rows, how many
   lost or changed a band set. These were not measured in the spec; hand the
   counts to the user before pushing.

- [ ] **Step 7: Lint and commit.**

```bash
cd $wt && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix $(git diff --name-only) src/dbt/kipptaf/models/assessments/intermediate/int_assessments__group_performance_bands.sql src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__group_performance_bands.yml </dev/null
git -C $wt add -u
git -C $wt add src/dbt/kipptaf/models/assessments/intermediate/int_assessments__group_performance_bands.sql src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__group_performance_bands.yml
git -C $wt commit -m "fix(dbt): label internal scores from their region's band set" -m "Refs #6308"
```

---

### Task 4: Reference doc and skill

**Files:**

- Modify: `docs/models/ddi-stack-data-model.md` (the "Canonical assessment" term
  near line 114 and the decision "Canonical grouping by attributes, not region"
  near line 493)
- Modify: `.claude/skills/ddi-stack/references/tagging.md` ("Canonical grouping"
  and the `regions_assessed` row of the tag table),
  `.claude/skills/ddi-stack/references/report-cards.md` (step 1, "The gate")

- [ ] **Step 1: Rewrite the three passages** to state the regional rule in the
      spec's _Terms_, that the title, date, report card tags and band set come
      from the region's own first copy, that a copy tagged for several regions
      sits in each, and that a wrong module tag still combines different tests.
      Keep the Miami note, reworded: Miami-only copies still form their own tag
      group.
- [ ] **Step 2: Lint and commit.**

```bash
cd $wt && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix docs/models/ddi-stack-data-model.md .claude/skills/ddi-stack/references/tagging.md .claude/skills/ddi-stack/references/report-cards.md </dev/null
git -C $wt add -u
git -C $wt commit -m "docs(dbt): describe the regional assessment roll-up" -m "Refs #6308"
```

---

### Task 5: Report card check, pull request and follow-ups

- [ ] **Step 1: Report card check (spec verification 4).** With the Task 3 dev
      build, count Camden grade 1 and 2 students with a Q1 row in dev and not in
      prod, on `rpt_deanslist__mod_standards_domains`: literacy report card
      domain rows for grade 2 (expected close to 172 students) and literacy
      progress report rows for grades 1 and 2 (close to 141 and 173). Counts
      only.
- [ ] **Step 2: Run the layer check** on the lines this branch changed, using
      the invocation in `scripts/check_dbt_standard.py --help`, and fix any A or
      S finding.
- [ ] **Step 3: Push and open the pull request** from
      `.github/pull_request_template.md`. The body lists: the key churn and its
      size, the verification counts from Tasks 2, 3 and 5, and these post-merge
      steps for the Data Team: confirm every changed table rebuilt in one pass,
      then rebuild the `proficiency_rollup` partitions before July 1, 2025 by
      hand in Cube Cloud.
- [ ] **Step 4: File the follow-up issue** for replacement scores missing from
      the scores fact, using `.github/ISSUE_TEMPLATE/bug_report.md`, and add it
      to project board 4 (`gh-token-scopes` skill if the token lacks scope).
- [ ] **Step 5: Offer to watch CI and answer `claude-review`** (`pr-ci-review`
      skill).
