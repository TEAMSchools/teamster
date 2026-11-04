# Tableau rpt Error Tests (PR 5 of #5948) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every test on a `rpt_tableau__*` model runs at `error`, except grain
tests that fail in prod on a tracked source defect, which stay `warn` with a
`TODO(#N)`.

**Architecture:** Add a `kipptaf: extracts: tableau: +severity: error` block.
Move the 11 business-unit `accepted_values` tests from the `rpt_` models to the
2 upstream models that first see those values, and delete the `student_tier`
enum test, which the upstream bucket model already guards. Pin `warn` on the
`int_tableau__*` tests the folder block would otherwise flip, and on the 6
failing grain tests. Set severity explicitly on the singular tests in `tests/`.
No model SQL changes.

**Tech Stack:** dbt (BigQuery), kipptaf project.

**Spec:** `docs/superpowers/specs/2026-10-15-mart-test-rule.md` and the sorting
rule in `.claude/rules/dbt-yaml.md` → _Test config defaults_. Precedent:
`docs/superpowers/plans/2026-10-16-dim-error-tests.md` (#5983).

## Global Constraints

- Worktree:
  `/workspaces/teamster/.claude/worktrees/cbini/test/claude-tableau-rpt-error-tests`,
  branch `cbini/test/claude-tableau-rpt-error-tests`. Use `git -C <worktree>`
  and absolute paths. Always `uv run`. Stage with `git add -u` (plus explicit
  new paths).
- dbt commands run from `src/dbt/kipptaf` in the worktree. Prod-deferred form:
  `uv run dbt <cmd> --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod`.
  Select with `path:models/extracts/tableau`. That selection also picks up the
  singular tests in `tests/` that read a Tableau model.
- Scope: tests already on `extracts/tableau/` models, plus the 2 upstream
  `accepted_values` tests Task 2 adds. Adding grain tests to the 48 `rpt_`
  models with none is a follow-up PR, not this one.
- `int_tableau__*` tests keep their current severity. The rule covers marts and
  `rpt_` only.
- A `warn` test carries `# TODO(#N): <one line>` on the line above, N an open
  issue.
- PR body: `Refs #5948` (no `Closes`). No PII in commits, comments, or the PR;
  counts and column names only.
- Lint before push:
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  from inside the worktree.

## Settled decisions this plan rests on

Prod run on `origin/main` (`5d3d4d9110`): PASS=83 WARN=6 ERROR=0 over 88 tests
plus 1 unit test. The 6 warnings are all grain tests:

| Model                                                 | Groups | TODO    |
| ----------------------------------------------------- | ------ | ------- |
| `rpt_tableau__kfwd_career_launch_survey`              | 128    | `#3818` |
| `rpt_tableau__college_assessment_dashboard_de`        | 198    | `#5889` |
| `rpt_tableau__dibels_dashboard`                       | 273    | `#5889` |
| `rpt_tableau__college_assessment_dashboard_over_time` | 326    | `#4871` |
| `rpt_tableau__graduation_requirements`                | 4      | `#5920` |
| `rpt_tableau__sight_words_dashboard`                  | 5,459  | `#5700` |

`college_assessment_dashboard_de`: in 196 of the 198 groups, one PowerSchool
stored grade joins more than one row of `stg_powerschool__u_storedgrades_de`
(different DE course and semester). Which row wins is the dashboard owner's
call. No issue tracks it yet; Task 1 records it on #5889.

Test sorting:

- Moved upstream (source data, earliest model that sees it):
  - 10 `home_business_unit_name` `accepted_values` → 1 test on
    `int_people__staff_roster.home_business_unit_name`, `warn`. The `rpt_`
    `entity` logic already maps any business unit it does not know to Region, so
    a new ADP business unit has a downstream defense.
  - `rpt_tableau__operations_ekg.school_business_unit_name` `accepted_values` →
    1 test on `stg_google_sheets__people__locations.location_region`, `error`
    (staging tests are always `error`).
- Deleted as an upstream promise:
  `rpt_tableau__academic_goals_dashboard.student_tier` `accepted_values`.
  `int_students__bucket_assignments` already gates Buckets 1-3 at `error`, and
  Bucket 4 is the coalesce default.
- Kept and flipped to `error`: every `not_null`, every passing grain test, the 3
  DIBELS singulars and the GPA singular. All pass in prod.
- Removed `severity: warn` overrides on passing tests: 1 in
  `rpt_tableau__manager_survey_details.yml`, 2 in
  `rpt_tableau__operations_ekg.yml`.
- Kept `warn` (int, out of scope): the
  `int_tableau__state_assessments_demographic_comps` `accepted_values` and grain
  tests, the 3-column `int_tableau__fresh_enrollment_scaffold` grain test, and
  `test_int_tableau__fresh_goals_scaffold_region_matches_scaffold`.

## Review Focus

- A `warn` override removed from a test that fails in prod turns CI red. Every
  removal must match a test that passed in the Task 1 run.
- The 2 new upstream tests run on far more rows than the `rpt_` copies did. Each
  must return 0 in prod before it lands at its planned severity.
- The folder block also reaches the `int_tableau__*` tests. `dbt ls` must show
  all 4 int `warn` tests still at `warn`.
- A column whose last test is deleted must not keep an empty `data_tests:` key,
  and tested columns stay at the top of `columns:`.
- The `TODO(#N)` issues must all be open when the PR opens.

---

### Task 1: Record the DE duplicates and save the baseline

**Interfaces:**

- Produces: `<scratchpad>/tableau-tests-main.txt` (sorted test node names on
  main). Task 3 diffs against it.

- [ ] **Step 1: Save the main test list**

`uv run dbt parse --no-partial-parse`, then
`uv run dbt ls --resource-type test --select path:models/extracts/tableau --output name | sort > <scratchpad>/tableau-tests-main.txt`.
Expected: 88 lines.

- [ ] **Step 2: Comment on #5889**

Add a bullet-style comment: `rpt_tableau__college_assessment_dashboard_de` grain
(`student_number`, `storedgrades_dcid`) fails on 198 groups; in 196, one stored
grade joins more than one DE extension row with a different DE course and
semester. The dashboard owner decides which row wins, or the grain gains the DE
semester. Counts only.

No commit.

### Task 2: Move the business-unit and tier enum tests

**Files:**

- Modify: `models/people/intermediate/properties/int_people__staff_roster.yml`
- Modify:
  `models/google/sheets/staging/properties/stg_google_sheets__people__locations.yml`
- Modify: the 10 `rpt_tableau__*.yml` files carrying a business-unit
  `accepted_values` (`operations_ekg` has 2), and
  `rpt_tableau__academic_goals_dashboard.yml`

**Interfaces:**

- Produces: 12 fewer `rpt_` tests and 2 new upstream tests. Task 3 counts them.

- [ ] **Step 1: Confirm each `rpt_` column's source**

`rg` each of the 10 `rpt_` SQL files for `home_business_unit_name`. Expected:
each reads it from `int_people__staff_roster` (directly or through `dim_staff`).
Any that reads another model: rule on it in the ledger before deleting that
test.

- [ ] **Step 2: Prove the new tests pass in prod**

Run against prod with the BigQuery MCP:
`select count(*) from kipptaf_people.int_people__staff_roster where home_business_unit_name not in (<the 5 names from the rpt tests>)`
and the same for
`kipptaf_google_sheets.stg_google_sheets__people__locations.location_region`
against the 4 names on `operations_ekg`. Expected: 0 and 0. A nonzero count
means the test lands at `warn` with a `TODO(#N)` (file the issue first).

- [ ] **Step 3: Add the 2 upstream tests**

`accepted_values` with the same value lists. Roster: `config: severity: warn`
plus a description line naming ADP Workforce Now as the source and saying a new
business unit must be added to the `entity` mapping in the Tableau extracts.
Locations: `config: severity: error`. Keep `not_null` pairing where the column
already has it; do not add one.

- [ ] **Step 4: Delete the 12 `rpt_` tests**

The 11 business-unit `accepted_values` and the `student_tier` `accepted_values`.
Keep every `not_null` on those columns. Delete any `data_tests:` key left empty
and re-sort tested columns to the top.

- [ ] **Step 5: Commit**

`test(dbt): move Tableau business-unit enum tests to their source models`.

### Task 3: Flip the folder to `error`

**Files:**

- Modify: `src/dbt/kipptaf/dbt_project.yml` (`data_tests:` block, after
  `dimensions:`)
- Modify: the 6 failing models' properties YAML,
  `int_tableau__state_assessments_demographic_comps.yml`,
  `int_tableau__fresh_enrollment_scaffold.yml`,
  `rpt_tableau__manager_survey_details.yml`, `rpt_tableau__operations_ekg.yml`
- Modify: `src/dbt/kipptaf/tests/properties.yml`

**Interfaces:**

- Consumes: Task 1's baseline; Task 2's test set.

- [ ] **Step 1: Add the folder block**

```yaml
kipptaf:
  extracts:
    tableau:
      +severity: error
```

nested under the existing `kipptaf:` key in `data_tests:`.

- [ ] **Step 2: Pin the `warn` tests**

The 6 grain tests in the table above: `config: severity: warn` with
`# TODO(#N): <one line>` above. DIBELS and sight words already carry `warn`; add
the TODO only. The 3 int YAML tests: `config: severity: warn`, no TODO (they are
out of scope, not defects). Remove the 3 passing `warn` overrides on
`manager_survey_details` and `operations_ekg`.

- [ ] **Step 3: Set singular severities**

In `tests/properties.yml`: `severity: error` on the 3 DIBELS singulars and
`rpt_tableau__gpa_cumulative_year__one_latest_graded_year`; `severity: warn` on
`test_int_tableau__fresh_goals_scaffold_region_matches_scaffold`. Add an entry
for any of these that has none.

- [ ] **Step 4: Check the node diff and resolved severity**

Re-parse with `--no-partial-parse`, list the same selection, `comm -3` against
the Task 1 baseline. Expected: 12 removed (the Task 2 deletions), 0 added. Then
`dbt ls ... --output json --output-keys "name config"` and count by severity.
Expected: 66 `error`, 10 `warn` (6 grain + 4 int). Separately confirm the 2
upstream tests resolve to `warn` (roster) and `error` (locations).

- [ ] **Step 5: Run against prod**

`uv run dbt test --select path:models/extracts/tableau <prod-deferred flags> 2>&1 | tail -n 15`,
then the 2 upstream tests by name. Expected: `ERROR=0`, `WARN=6` plus any of the
4 int tests that warn today (0 in the baseline run).

- [ ] **Step 6: Lint and commit**

Trunk check every changed file. Commit
`test(dbt): run Tableau extract tests at error severity`.

### Task 4: Ship

- [ ] **Step 1: Push and open the PR**

Body from `.github/pull_request_template.md`: `Refs #5948`, the 12 deletions and
2 moved tests, the 6 `warn` grain tests with their issue links, the 4 int tests
left alone, and 2 caveats. First, every `rpt_tableau__*` model is a view, so its
tests run only when its code changes, not when data loads. Second, 48 Tableau
`rpt_` models have no grain test; a follow-up PR adds them. Read the body back
after creating it.
