# kipptaf Union Cleanup (PR 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `stg_powerschool__schools`, `int_deanslist__incidents`, and
`int_overgrad__students` pure kipptaf unions, with every consumer's output
unchanged except the 3 unused Overgrad columns.

**Architecture:** Each `location_key` join moves to the model that needs it:
`int_students__schools` (already joins the locations sheet), a new domain model
`int_students__behavioral_incidents` feeding `fct_behavioral_incidents`, and
`rpt_branchingminds__behavior_incident` (joins the sheet on its own id). The
Overgrad top-choice pivot is deleted.

**Tech Stack:** dbt (BigQuery), kipptaf project only.

**Spec:** `docs/superpowers/specs/2026-10-09-kipptaf-union-cleanup-design.md`
(PR 1 section). Refs #5832.

## Global Constraints

- Worktree:
  `/workspaces/teamster/.claude/worktrees/cbini/refactor/claude-kipptaf-union-cleanup`
  (`wt` below). Every path and `git -C` call uses it.
- kipptaf only. No district or package file changes.
- Location filters, copied verbatim everywhere the sheet is joined:
  `not loc.is_pathways and loc.location_name <> 'KIPP Whittier Elementary'`.
- Union models produce `_dbt_source_project` with
  `{{ extract_source_project("<alias>") }}` (unchanged from today).
- SQL rules: `.claude/rules/dbt-sql.md` (S6 select order, S11 filters, S16
  aliases). Every new or modified model and column has a `description:`.
- Local union builds read empty `zz_<user>_*` district sources. Validate SQL
  with `dbt compile --target staging` (no warehouse write); prove values with
  the dbt Cloud CI build compared to prod (Task 4).

## Review Focus

1. A school or incident whose id matches no sheet row: `location_key` must stay
   NULL (left join), not drop the row. Pinned by row-count parity in Task 4.
2. PowerSchool `school_number` 0: the sheet has 11 rows with
   `powerschool_school_id = 0`. Today's join fans out on it if PowerSchool has
   school 0; the moved join must reproduce today's row count exactly, fan-out
   included, and the `int_students__schools` uniqueness test must stay green.
3. DeansList id with NULL on the sheet: 14 filtered sheet rows have a NULL
   `deanslist_school_id`; an equality join never matches NULL, so no incident
   picks one up. Pinned by Task 4's `location_key` per-row match.
4. The `rpt_branchingminds__behavior_incident` inner join: switching it from
   `location_key` to `deanslist_school_id` must keep the same rows, since an
   incident with no sheet match was already dropped. Pinned by Task 4 row
   parity.
5. Cross-region id reuse: incident ids repeat across regions, so the new model's
   uniqueness test is on `incident_id` + `_dbt_source_project`, never
   `incident_id` alone.

---

### Task 1: `stg_powerschool__schools` → pure union

**Files:**

- Modify:
  `src/dbt/kipptaf/models/powerschool/staging/stg_powerschool__schools.sql`
- Modify:
  `src/dbt/kipptaf/models/powerschool/staging/properties/stg_powerschool__schools.yml`
- Modify:
  `src/dbt/kipptaf/models/students/intermediate/int_students__schools.sql`
- Modify:
  `src/dbt/kipptaf/models/students/intermediate/properties/int_students__schools.yml`

**Interfaces:**

- Produces: `stg_powerschool__schools` with every column it has today except
  `location_key`. `int_students__schools` keeps its exact column list.

- [ ] **Step 1:** In `stg_powerschool__schools.sql`, drop the `loc` join and
      `loc.location_key`; final select becomes
      `select u.*, {{ extract_source_project("u") }} as _dbt_source_project, from unioned as u`.
- [ ] **Step 2:** In its yml, delete the `location_key` column block (with its
      `relationships` test). Leave `_dbt_source_project` and `school_number`
      untouched.
- [ ] **Step 3:** In `int_students__schools.sql`, the PowerSchool branch reads
      `{{ ref("stg_powerschool__schools") }} as ps` left-joined to
      `{{ ref("stg_google_sheets__people__locations") }} as loc` on
      `ps.school_number = loc.powerschool_school_id` plus the 2 Global
      Constraints filters in the `on` clause (they filter the joined table, so
      they stay in `on`, not `where`). Select `loc.location_key`; every other
      column comes from `ps` in today's order. The Focus branch is unchanged.
- [ ] **Step 4:** In `int_students__schools.yml`, move the `relationships` test
      (`to: ref('dim_locations')`, `field: location_key`, `severity: error`)
      onto `location_key`, sort that column to the top of `columns:`, and reword
      its description to cover both branches: resolved from the people locations
      sheet on the PowerSchool school id (NJ) or on Focus's school code (Miami).
- [ ] **Step 5:** Compile both models:
      `uv run dbt compile --project-dir $wt/src/dbt/kipptaf --target staging --select stg_powerschool__schools int_students__schools`
      Expected: success, and the compiled `stg_powerschool__schools` lists
      columns from `zz_stg_*` (not an empty expansion).
- [ ] **Step 6:** Commit:
      `refactor(dbt): move location_key join out of stg_powerschool__schools`.

### Task 2: `int_deanslist__incidents` → pure union; new domain model

**Files:**

- Modify:
  `src/dbt/kipptaf/models/deanslist/api/intermediate/int_deanslist__incidents.sql`
- Modify:
  `src/dbt/kipptaf/models/deanslist/api/intermediate/properties/int_deanslist__incidents.yml`
- Create:
  `src/dbt/kipptaf/models/students/intermediate/int_students__behavioral_incidents.sql`
- Create:
  `src/dbt/kipptaf/models/students/intermediate/properties/int_students__behavioral_incidents.yml`
- Modify: `src/dbt/kipptaf/models/marts/facts/fct_behavioral_incidents.sql:74`
- Modify:
  `src/dbt/kipptaf/models/extracts/branchingminds/rpt_branchingminds__behavior_incident.sql`

**Interfaces:**

- Produces: `int_students__behavioral_incidents` = every
  `int_deanslist__incidents` column plus `location_key` (string), 1 row per
  `incident_id` + `_dbt_source_project`.

- [ ] **Step 1:** `int_deanslist__incidents.sql`: drop the `loc` join and
      `loc.location_key`. Its yml keeps `materialized: table` and loses the
      `location_key` column block.
- [ ] **Step 2:** Create `int_students__behavioral_incidents.sql`:
      `select i.*, loc.location_key,` from `int_deanslist__incidents as i`
      left-joined to the sheet `as loc` on
      `i.school_id = loc.deanslist_school_id` plus the 2 filters in `on`.
- [ ] **Step 3:** Create its yml: model `description:` (DeansList incidents
      across regions with the canonical school location attached); model-level
      `dbt_utils.unique_combination_of_columns` on `incident_id`,
      `_dbt_source_project` at `severity: error`; `location_key` column with the
      `relationships` test moved from the union yml and the union's description.
      Inherit the folder's default materialization (no `materialized:` key).
- [ ] **Step 4:** `fct_behavioral_incidents.sql`: change the `from` ref to
      `int_students__behavioral_incidents`. Nothing else changes.
- [ ] **Step 5:** `rpt_branchingminds__behavior_incident.sql`: change the sheet
      join to `i.school_id = loc.deanslist_school_id` plus the 2 filters.
      `school_id` output is still `cast(loc.powerschool_school_id as string)`.
- [ ] **Step 6:** Compile:
      `uv run dbt compile --project-dir $wt/src/dbt/kipptaf --target staging --select int_deanslist__incidents int_students__behavioral_incidents fct_behavioral_incidents rpt_branchingminds__behavior_incident`
      Expected: success.
- [ ] **Step 7:** Run the layer check on the touched files (find the hook or
      script that runs `scripts/check_dbt_standard.py` in
      `.pre-commit-config.yaml` / `.trunk/trunk.yaml` and run it the same way).
      Expected: no new violation; `fct_behavioral_incidents` no longer reads a
      source `int_`.
- [ ] **Step 8:** Commit:
      `refactor(dbt): move incident location_key into int_students__behavioral_incidents`.

### Task 3: `int_overgrad__students` → pure union

**Files:**

- Modify:
  `src/dbt/kipptaf/models/overgrad/intermediate/int_overgrad__students.sql`

- [ ] **Step 1:** Delete `choices_long`, `choices_pivot`, the left join, and the
      3 `*_choice_school` columns. Final select:
      `select ur.*, {{ extract_source_project("ur") }} as _dbt_source_project, from union_relations as ur`.
      The yml needs no change (its uniqueness test stays).
- [ ] **Step 2:** Confirm nothing reads the removed columns:
      `grep -rn "first_choice_school\|second_choice_school\|third_choice_school" $wt/src`
      Expected: no output.
- [ ] **Step 3:** Compile `int_overgrad__students` with the Task 1 command
      shape. Expected: success.
- [ ] **Step 4:** Commit:
      `refactor(dbt): drop unused top-choice pivot from int_overgrad__students`.

### Task 4: Lint, open PR, prove parity against prod

- [ ] **Step 1:** Lint every changed `.sql`, `.yml`, and the plan:
      `cd $wt && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`.
      Fix findings; formatting is the hook's.
- [ ] **Step 2:** Push, open the PR from `.github/pull_request_template.md` with
      `Refs #5832`, then follow `pr-ci-review` to watch dbt Cloud CI. Expected:
      CI green (pre-existing failures checked against prod per
      `src/dbt/kipptaf/CLAUDE.md` before attributing them).
- [ ] **Step 3:** With BigQuery MCP, compare the CI build
      (`dbt_cloud_pr_<job>_<pr>_<schema>`) to prod for each model below:
      `count(*)` and `count(distinct format("%T|%T", <keys>))` must match. -
      `int_students__schools` keys `school_number, _dbt_source_project`; plus
      `location_key` equal per key. - `fct_behavioral_incidents` key
      `behavioral_incident_key`; plus `location_key` equal per key. -
      `rpt_branchingminds__behavior_incident` key `incident_id`, `school_id`. -
      `int_overgrad__students` keys `id, _dbt_source_project`. Expected: zero
      differences. Post counts only (no row values) in the PR.

## Self-review notes

- Spec PR 1 coverage: Tasks 1-3 map to the spec's 3 subsections; Task 4 is its
  verification. The spec said the incidents union "carries" a uniqueness test;
  it does not, so Task 2 adds one on the new model.
