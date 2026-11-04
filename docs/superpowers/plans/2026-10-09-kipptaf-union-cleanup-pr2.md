# Kipptaf union cleanup, PR 2 (star and i-Ready) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move star and i-Ready single-source logic out of the kipptaf union
models into the renlearn and iready packages and a new domain model, with no
change to any consumer's output.

**Architecture:** Each package gains a source `int_` that holds the per-district
logic (decodes, windows). The kipptaf union reads that `int_` and keeps only the
union, Focus student-number conversion and region lookup. i-Ready's cross-source
joins (crosswalk sheet, reporting terms) move to a new domain model, and the 12
consumers that read those columns, plus the domain unpivot, move with them.
Ships single-PR via `src/dbt/kipptaf/CLAUDE.md` → _Single-PR cross-project
workflow_.

**Tech Stack:** dbt on BigQuery, dbt Cloud CI (kipptaf only), `uv run dbt`.

**Spec:** `docs/superpowers/specs/2026-10-09-kipptaf-union-cleanup-design.md`
(section _PR 2_). Issue #5832.

## Global Constraints

- Worktree:
  `/workspaces/teamster/.claude/worktrees/cbini/refactor/claude-kipptaf-union-cleanup-pkg`,
  branch `cbini/refactor/claude-kipptaf-union-cleanup-pkg`. Every path below is
  relative to it.
- No consumer's output changes. Same columns, same rows, same values.
- `int_people__location_crosswalk` region lookups and `focus_student_number`
  stay in kipptaf.
- Window partitions in the packages drop `_dbt_source_relation` (1 relation per
  district); the spec's prod checks show this matches today.
- Every `--target staging` write is a shared `zz_stg` write. Each one needs the
  user's authorization in the turn immediately before, in its own Bash call.
- Rename sweep for the unpivot covers `*.{sql,yml,md}` under `src/`, but not
  `docs/superpowers/` (historical specs and plans are not edited).
- Do not flip any materialization (#5831 owns that), except the new domain
  model, which is a table (see Task 4).

## Review Focus

1. Star `rn_subject_round` / `rn_subject_year` now rank on the raw
   `student_identifier`, not the Focus-converted one. Expect identical ranks;
   Task 6's `except distinct` covers it.
2. i-Ready windows drop the rewritten region `_dbt_source_relation` from the
   partition. Expect identical `most_recent_*` and `rn_subj_year`; Task 6 covers
   it.
3. `rn_subj_round` and the unpivot's `rn_subject_test` still partition on the
   kipptaf-rewritten `_dbt_source_relation`, so the domain model must carry that
   column through unchanged.
4. Dropping `deactivation_reason` from the package `stg_renlearn__star` breaks
   any reader that names it. `int_renlearn__star_rollup` is the only one; Task 2
   removes its now-redundant filter.
5. A consumer missed in the repoint fails at compile (`Name <col> not found`),
   so CI catches it. A consumer repointed by mistake only costs a hop. Task 4's
   grep list is the check.

---

### Task 1: renlearn package — decode in `stg_`, windows in a new `int_`

**Files:**

- Modify: `src/dbt/renlearn/models/staging/stg_renlearn__star.sql`
- Modify: `src/dbt/renlearn/models/staging/properties/stg_renlearn__star.yml`
- Create: `src/dbt/renlearn/models/intermediate/int_renlearn__star.sql`
- Create:
  `src/dbt/renlearn/models/intermediate/properties/int_renlearn__star.yml`

**Interfaces:**

- Produces: package `stg_renlearn__star` with 9 new columns
  `completed_date_value` (date), `academic_year` (int64), `grade_level` (int64),
  `star_subject`, `star_discipline`, `subject`, `administration_window`
  (string), `is_district_benchmark_proficient_int`,
  `is_state_benchmark_proficient_int` (int64). Rows with
  `deactivation_reason is not null` are filtered out and the column is dropped.
- Produces: package `int_renlearn__star` = `stg_renlearn__star` plus
  `rn_subject_round`, `rn_subject_year` (int64).

- [ ] **Step 1:** Add the 9 decode columns to the package `stg_`, copying the
      expressions verbatim from kipptaf `stg_renlearn__star.sql` lines 37-93
      (rewrite `_dagster_partition_fiscal_year - 1` and the raw source column
      names to match the `stg_`'s source columns). Add
      `where deactivationreason is null` and drop `deactivation_reason` from the
      select. Cast once (S9); the decodes read raw source columns, so no
      re-reference of an alias in the same select list.
- [ ] **Step 2:** Update the `stg_` properties: add the 9 columns with
      `data_type` and descriptions; remove `deactivation_reason`; change the
      `assessment_id` `unique` test to drop its `where:` (keep
      `severity: error`).
- [ ] **Step 3:** Write `int_renlearn__star.sql`: `select *,` plus the 2
      `row_number()` windows from kipptaf lines 95-112, with
      `_dbt_source_relation` removed from both partitions.
- [ ] **Step 4:** Write its properties: model description, every column
      described (copy from the `stg_` yml), and `unique` on `assessment_id`.
- [ ] **Step 5:** Verify in kippmiami (the only consumer): per the
      `dbt-local-dev` skill,
      `uv run dbt build --select stg_renlearn__star int_renlearn__star --project-dir src/dbt/kippmiami --target dev --defer --state /workspaces/teamster/src/dbt/kippmiami/target/prod`.
      Expected: both models build, contract passes, `unique` passes.
- [ ] **Step 6:** Commit
      `refactor(dbt): move star decodes and windows into the renlearn package`.

### Task 2: kipptaf star union reads the package `int_`

**Files:**

- Modify: `src/dbt/kipptaf/models/renlearn/sources-kippmiami.yml`
- Modify: `src/dbt/kipptaf/models/renlearn/staging/stg_renlearn__star.sql`
- Modify:
  `src/dbt/kipptaf/models/renlearn/staging/properties/stg_renlearn__star.yml`
- Modify:
  `src/dbt/kipptaf/models/renlearn/intermediate/int_renlearn__star_rollup.sql:66`

**Interfaces:**

- Consumes: Task 1's `int_renlearn__star` (source table
  `kippmiami_renlearn.int_renlearn__star`).
- Produces: kipptaf `stg_renlearn__star` with the same column set as on main,
  minus `deactivation_reason`.

- [ ] **Step 1:** In `sources-kippmiami.yml`, add the
      `elif target.name == 'staging' -%}zz_stg_` branch to the schema (match
      `iready/sources-kippmiami.yml`), and add table `int_renlearn__star` with
      asset key `[kippmiami, renlearn, int_renlearn__star]`.
- [ ] **Step 2:** Rewrite kipptaf `stg_renlearn__star.sql`: union
      `source("kippmiami_renlearn", "int_renlearn__star")`, keep the `sourced`
      CTE (Focus conversion) and the final `int_people__location_crosswalk`
      join. Delete the `derived` CTE and its `where`.
- [ ] **Step 3:** Remove `deactivation_reason` from the kipptaf yml. Leave the
      description's content claims accurate (it no longer computes the derived
      columns; say they come from the package).
- [ ] **Step 4:** Delete `where deactivation_reason is null` from
      `int_renlearn__star_rollup.sql`. It is redundant: the package `stg_`
      already filters.
- [ ] **Step 5:**
      `uv run dbt compile --select stg_renlearn__star --project-dir src/dbt/kipptaf --target staging`
      (no warehouse write). Expected: compiles. The union column list stays
      empty until Task 5 seeds `zz_stg_kippmiami_renlearn`; re-run then and read
      the compiled SQL.
- [ ] **Step 6:** Commit
      `refactor(dbt): read star logic from the renlearn package`.

### Task 3: iready package — windows in a new `int_`

**Files:**

- Create:
  `src/dbt/iready/models/intermediate/int_iready__diagnostic_results.sql`
- Create:
  `src/dbt/iready/models/intermediate/properties/int_iready__diagnostic_results.yml`

**Interfaces:**

- Produces: package `int_iready__diagnostic_results` = package
  `stg_iready__diagnostic_results` with the 8 `most_recent_*` columns replaced
  by their `max(...) over` values, plus `rn_subj_year` (int64).

- [ ] **Step 1:** Write the model: `select * except (<8 most_recent_*>)`, the 8
      `max(...) over` columns, and `rn_subj_year`, copied from kipptaf
      `int_iready__diagnostic_results.sql` lines 56-105 with partitions
      `student_id, academic_year, subject` (no `_dbt_source_relation`).
- [ ] **Step 2:** Write its properties: description, columns (copy from the
      package `stg_` yml, plus `rn_subj_year`), and the same
      `unique_combination_of_columns` the package `stg_` carries.
- [ ] **Step 3:** Build in kippmiami and kippnewark (both consume the package):
      `uv run dbt build --select int_iready__diagnostic_results --project-dir src/dbt/<district> --target dev --defer --state /workspaces/teamster/src/dbt/<district>/target/prod`.
      Expected: builds, uniqueness passes, in both.
- [ ] **Step 4:** Commit
      `refactor(dbt): move i-Ready windows into the iready package`.

### Task 4: kipptaf i-Ready union, domain model, and consumers

**Files:**

- Modify: `src/dbt/kipptaf/models/iready/sources-kippnj.yml`,
  `src/dbt/kipptaf/models/iready/sources-kippmiami.yml`
- Modify:
  `src/dbt/kipptaf/models/iready/intermediate/int_iready__diagnostic_results.sql`
  and its yml
- Create:
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__iready_diagnostic_results.sql`
  and `properties/int_assessments__iready_diagnostic_results.yml`
- Move:
  `src/dbt/kipptaf/models/iready/intermediate/int_iready__domain_unpivot.{sql,yml}`
  →
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__iready_domain_unpivot.{sql,yml}`
- Modify: the 12 consumers below, and `src/dbt/kipptaf/standard-baseline.tsv`

**Interfaces:**

- Consumes: Task 3's package `int_iready__diagnostic_results` (source tables
  `kippnj_iready.int_iready__diagnostic_results`,
  `kippmiami_iready.int_iready__diagnostic_results`).
- Produces: kipptaf `int_iready__diagnostic_results` (union + Focus + region +
  `state_assessment_type` + rewritten `_dbt_source_relation` +
  `_dbt_source_project`), and `int_assessments__iready_diagnostic_results` =
  that union plus every column built from the crosswalk and terms joins
  (`projected_*`, `*_with_typical`, `proficent_scale_score`, `test_round`,
  `round_number`, `iready_proficiency`, `scale_points_to_proficiency`,
  `progress_to_typical`, `progress_to_stretch`, `rn_subj_round`).

- [ ] **Step 1:** Add `int_iready__diagnostic_results` to both sources files,
      asset keys `[kippnewark, iready, ...]` and `[kippmiami, iready, ...]`.
- [ ] **Step 2:** Rewrite the kipptaf union: union the 2 package `int_` sources,
      keep `sourced` and `transformations`, delete `window_calcs` and the joins,
      and select `*` plus `_dbt_source_project`.
- [ ] **Step 3:** Write the domain model: the deleted final select (lines
      108-226 of main's file) reading `ref("int_iready__diagnostic_results")` as
      `wc`. Properties: `config: materialized: table` (it carries the heavy
      joins the union table carried, and 12 consumers read it), the union's
      `unique_combination_of_columns`, and the moved column docs.
- [ ] **Step 4:** Split the 1,147-line union yml: columns produced by the domain
      model move to the domain yml; the union keeps the rest. Both model
      descriptions say what each one now does.
- [ ] **Step 5:** `git mv` the unpivot to the new name and folder, repoint it to
      `ref("int_assessments__iready_diagnostic_results")`, update its yml name
      and the `_dbt_source_relation` literal at yml line 128 only if the test
      changes meaning (it should not). Check the folder move's inherited config
      (`assessments` vs `iready` `+schema`) per `.claude/rules/dbt-models.md`.
- [ ] **Step 6:** Repoint these 12 to the domain model (they read crosswalk or
      terms columns): `dim_assessment_administrations`,
      `int_topline__iready_diagnostic_weekly`,
      `rpt_gsheets__kippmiami_payout_roster`, `rpt_tableau__miami_k2_iready`,
      `int_extracts__student_enrollments_subjects`,
      `int_assessments__benchmark_scores`, `int_ignite__interim_assessment`,
      `rpt_tableau__miami_fast`, `rpt_tableau__iready_apm`,
      `int_reporting__promotional_status`, `rpt_tableau__academic_goals_rollup`,
      `rpt_deanslist__iready_diagnostics`. Repoint
      `rpt_tableau__miami_k2_iready` and
      `fct_assessment_scores_enrollment_scoped` to the renamed unpivot.
      `dim_assessments`, `rpt_tableau__mtss_rti`, `rpt_gsheets__mtss_rti` stay
      on the union.
- [ ] **Step 7:** Sweep: `rg -l 'int_iready__domain_unpivot' src/` returns
      nothing. Run the layer check the way CI does:
      `uv run dbt parse --project-dir src/dbt/kipptaf` then
      `uv run scripts/check_dbt_standard.py --project-dir src/dbt/kipptaf --diff <(git diff -U0 --no-renames origin/main...HEAD)`.
      Delete each baseline row it reports as no longer occurring. Expected
      removals include rows 99, 198, 393, 461, 511, 514, 515 and 37 (by today's
      line numbers); rows 43, 338, 521 stay.
- [ ] **Step 8:** Commit
      `refactor(dbt): move i-Ready crosswalk joins to a domain model`.

### Task 5: Seed `zz_stg` and compile against it (needs user authorization)

- [ ] **Step 1:** Ask the user to authorize, by name, these shared writes: broad
      `dbt clone --target staging` of kippmiami (the renlearn source now reads
      `zz_stg_kippmiami_renlearn`), and `dbt build --target staging` of
      `stg_renlearn__star int_renlearn__star int_iready__diagnostic_results` in
      kippmiami and `int_iready__diagnostic_results` in kippnewark. Stop until
      they answer.
- [ ] **Step 2:** Run each authorized write in its own Bash call, per the
      _Single-PR cross-project workflow_ commands. Expected: all succeed.
- [ ] **Step 3:** Re-run Task 2 Step 5 and the same compile for the kipptaf
      union and domain models. Expected: the compiled union lists the new
      package columns.
- [ ] **Step 4:** Lint every touched SQL, YAML and the plan with
      `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`.
      Fix findings; commit.

### Task 6: Push, CI, and parity against prod

- [ ] **Step 1:** Push and open the PR (template, `Refs #5832`), then watch CI
      and process `claude-review` per CLAUDE.local.md.
- [ ] **Step 2:** On green dbt Cloud CI, compare the CI schema
      (`dbt_cloud_pr_70403104388001_<pr>_*`) to prod:
      `int_assessments__iready_diagnostic_results` vs prod
      `kipptaf_iready.int_iready__diagnostic_results`, and kipptaf
      `stg_renlearn__star` vs prod. Row count, key-distinct count, and a
      full-row `except distinct` both ways on shared columns. Expected: 0 rows
      each way, except rows explained by source lag (count them, report counts
      only).
- [ ] **Step 3:** Post the counts as a PR comment (no row values).
