# i-Ready Domain Unpivot: Placement + Scale Score Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `placement` and `scale_score` to `int_iready__domain_unpivot`
alongside the existing `relative_placement`, unpivoting all three per-domain
attributes from `int_iready__diagnostic_results` in one pass.

**Architecture:** Replace the model's single-value `UNPIVOT` with a multi-column
tuple `UNPIVOT` (BigQuery syntax, precedented in this repo by
`int_collegeboard__ap_unpivot.sql`) that pulls
`(placement, relative_placement, scale_score)` together per domain, labeling
each domain group with an explicit clean slug (e.g. `'phonics'`) instead of
reusing the suffixed source column name. The sole consumer's now-unnecessary
suffix-stripping `domain_name` derivation is simplified to match.

**Tech Stack:** dbt (BigQuery adapter), `src/dbt/kipptaf` project.

## Global Constraints

- Design doc:
  `docs/superpowers/specs/2026-08-03-iready-domain-unpivot-placement-scale-score-design.md`.
  Issue: [#4706](https://github.com/TEAMSchools/teamster/issues/4706).
- Grain of `int_iready__domain_unpivot` is unchanged: one row per domain per
  test administration. `rn_subject_test`'s partition/order logic is unchanged.
- `domain_name` changes from the current suffixed value (e.g.
  `'phonics_relative_placement'`) to a clean slug (e.g. `'phonics'`).
- Do **not** add `up.placement` / `up.scale_score` to
  `rpt_tableau__miami_k2_iready.sql`'s `SELECT` list — only its `domain_name`
  derivation is simplified. The new columns' intended consumer is a future Cube
  mart update, tracked separately.
- Do **not** add a uniqueness/data test to `int_iready__domain_unpivot` — a
  pre-existing gap, out of scope for this change.
- All new or modified models require `description:` on the model and every
  column (house convention) — `int_iready__domain_unpivot` is being modified, so
  every column in its `properties.yml`, including pre-existing ones that
  currently lack a description, gets one.
- SQL follows `.trunk/config/.sqlfluff` (BigQuery dialect, trailing commas in
  `SELECT`, single-quoted strings, reserved words backtick-quoted).
- dbt unit-test `given`/`expect` scalars are unquoted (dates as `YYYY-MM-DD`),
  per house convention — quoting them trips yamllint at CI.
- This is a fresh worktree — run `dbt deps` before any other dbt command.
- Absolute worktree path:
  `/workspaces/teamster/.worktrees/anthonygwalters/feat/claude-iready-domain-unpivot-placement-scale-score`.
  Project dir for all dbt commands: `<worktree>/src/dbt/kipptaf`. Prod manifest
  for `--defer --state` is the MAIN repo's (absolute path, not the worktree's):
  `/workspaces/teamster/src/dbt/kipptaf/target/prod`.

## File Structure

- **Modify**
  `src/dbt/kipptaf/models/iready/intermediate/int_iready__domain_unpivot.sql` —
  the multi-column tuple `UNPIVOT` rewrite.
- **Modify**
  `src/dbt/kipptaf/models/iready/intermediate/properties/int_iready__domain_unpivot.yml`
  — new `placement`/`scale_score` column docs, descriptions on every column, and
  a new `unit_tests:` block proving the tuple-to-domain mapping and the
  all-null-domain exclusion behavior.
- **Modify**
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__miami_k2_iready.sql` —
  simplify the `domain_name` derivation (drop the now-unneeded suffix-stripping
  regex).

---

### Task 1: Multi-column unpivot in `int_iready__domain_unpivot`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/iready/intermediate/int_iready__domain_unpivot.sql`
- Modify:
  `src/dbt/kipptaf/models/iready/intermediate/properties/int_iready__domain_unpivot.yml`

**Interfaces:**

- Consumes: `int_iready__diagnostic_results` columns `<domain>_placement`
  (string), `<domain>_relative_placement` (string), `<domain>_scale_score`
  (int64) for each of the 14 domains: `phonics`,
  `algebra_and_algebraic_thinking`, `geometry`, `measurement_and_data`,
  `number_and_operations`, `high_frequency_words`, `phonological_awareness`,
  `reading_comprehension_informational_text`,
  `reading_comprehension_literature`, `reading_comprehension_overall`,
  `vocabulary`, `comprehension_informational_text`, `comprehension_literature`,
  `comprehension_overall`. Also consumes `_dbt_source_relation`, `student_id`,
  `subject`, `academic_year_int`, `start_date`, `completion_date`.
- Produces: `int_iready__domain_unpivot` with columns `student_id`, `subject`,
  `academic_year_int`, `start_date`, `completion_date`, `domain_name` (string,
  clean slug), `placement` (string), `relative_placement` (string),
  `scale_score` (int64), `rn_subject_test` (int64). Task 2 consumes this shape.

- [ ] **Step 1: Set up the fresh worktree's dbt packages**

  Run:

  ```bash
  uv run dbt deps --project-dir /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-iready-domain-unpivot-placement-scale-score/src/dbt/kipptaf
  ```

  Expected: completes with installed package versions listed, no errors.

- [ ] **Step 2: Write the failing unit test**

  Add a `unit_tests:` block (top-level key, sibling of `models:`) to
  `src/dbt/kipptaf/models/iready/intermediate/properties/int_iready__domain_unpivot.yml`:

  ```yaml
  unit_tests:
    - name: unit_iready_domain_unpivot_placement_scale_score
      description:
        Verifies the multi-column tuple UNPIVOT maps each domain's (placement,
        relative_placement, scale_score) triple to the correct domain_name slug
        — not just relative_placement as before — using a distinct value per
        domain so a mismatched tuple mapping would show up as a wrong value on
        the wrong row. vocabulary is given all-null
        placement/relative_placement/scale_score to prove BigQuery's
        multi-column UNPIVOT drops a domain row only when every value in its
        tuple is null, matching the prior single-column unpivot's behavior of
        excluding an unmeasured domain rather than emitting a row of nulls for
        it.
      model: int_iready__domain_unpivot
      given:
        - input: ref('int_iready__diagnostic_results')
          format: sql
          rows: |
            select
                'kippnj_iready.stg_iready__diagnostic_results'
                    as _dbt_source_relation,
                90001 as student_id,
                'Reading' as `subject`,
                2026 as academic_year_int,
                date('2025-09-01') as `start_date`,
                date('2025-09-15') as completion_date,

                'P9' as phonics_placement,
                'RP9' as phonics_relative_placement,
                409 as phonics_scale_score,

                'P1' as algebra_and_algebraic_thinking_placement,
                'RP1' as algebra_and_algebraic_thinking_relative_placement,
                401 as algebra_and_algebraic_thinking_scale_score,

                'P5' as geometry_placement,
                'RP5' as geometry_relative_placement,
                405 as geometry_scale_score,

                'P7' as measurement_and_data_placement,
                'RP7' as measurement_and_data_relative_placement,
                407 as measurement_and_data_scale_score,

                'P8' as number_and_operations_placement,
                'RP8' as number_and_operations_relative_placement,
                408 as number_and_operations_scale_score,

                'P6' as high_frequency_words_placement,
                'RP6' as high_frequency_words_relative_placement,
                406 as high_frequency_words_scale_score,

                'P10' as phonological_awareness_placement,
                'RP10' as phonological_awareness_relative_placement,
                410 as phonological_awareness_scale_score,

                'P11' as reading_comprehension_informational_text_placement,
                'RP11'
                    as reading_comprehension_informational_text_relative_placement,
                411 as reading_comprehension_informational_text_scale_score,

                'P12' as reading_comprehension_literature_placement,
                'RP12' as reading_comprehension_literature_relative_placement,
                412 as reading_comprehension_literature_scale_score,

                'P13' as reading_comprehension_overall_placement,
                'RP13' as reading_comprehension_overall_relative_placement,
                413 as reading_comprehension_overall_scale_score,

                cast(null as string) as vocabulary_placement,
                cast(null as string) as vocabulary_relative_placement,
                cast(null as int64) as vocabulary_scale_score,

                'P2' as comprehension_informational_text_placement,
                'RP2' as comprehension_informational_text_relative_placement,
                402 as comprehension_informational_text_scale_score,

                'P3' as comprehension_literature_placement,
                'RP3' as comprehension_literature_relative_placement,
                403 as comprehension_literature_scale_score,

                'P4' as comprehension_overall_placement,
                'RP4' as comprehension_overall_relative_placement,
                404 as comprehension_overall_scale_score,
      expect:
        rows:
          - {
              student_id: 90001,
              subject: Reading,
              academic_year_int: 2026,
              start_date: 2025-09-01,
              completion_date: 2025-09-15,
              domain_name: algebra_and_algebraic_thinking,
              placement: P1,
              relative_placement: RP1,
              scale_score: 401,
              rn_subject_test: 1,
            }
          - {
              student_id: 90001,
              subject: Reading,
              academic_year_int: 2026,
              start_date: 2025-09-01,
              completion_date: 2025-09-15,
              domain_name: comprehension_informational_text,
              placement: P2,
              relative_placement: RP2,
              scale_score: 402,
              rn_subject_test: 2,
            }
          - {
              student_id: 90001,
              subject: Reading,
              academic_year_int: 2026,
              start_date: 2025-09-01,
              completion_date: 2025-09-15,
              domain_name: comprehension_literature,
              placement: P3,
              relative_placement: RP3,
              scale_score: 403,
              rn_subject_test: 3,
            }
          - {
              student_id: 90001,
              subject: Reading,
              academic_year_int: 2026,
              start_date: 2025-09-01,
              completion_date: 2025-09-15,
              domain_name: comprehension_overall,
              placement: P4,
              relative_placement: RP4,
              scale_score: 404,
              rn_subject_test: 4,
            }
          - {
              student_id: 90001,
              subject: Reading,
              academic_year_int: 2026,
              start_date: 2025-09-01,
              completion_date: 2025-09-15,
              domain_name: geometry,
              placement: P5,
              relative_placement: RP5,
              scale_score: 405,
              rn_subject_test: 5,
            }
          - {
              student_id: 90001,
              subject: Reading,
              academic_year_int: 2026,
              start_date: 2025-09-01,
              completion_date: 2025-09-15,
              domain_name: high_frequency_words,
              placement: P6,
              relative_placement: RP6,
              scale_score: 406,
              rn_subject_test: 6,
            }
          - {
              student_id: 90001,
              subject: Reading,
              academic_year_int: 2026,
              start_date: 2025-09-01,
              completion_date: 2025-09-15,
              domain_name: measurement_and_data,
              placement: P7,
              relative_placement: RP7,
              scale_score: 407,
              rn_subject_test: 7,
            }
          - {
              student_id: 90001,
              subject: Reading,
              academic_year_int: 2026,
              start_date: 2025-09-01,
              completion_date: 2025-09-15,
              domain_name: number_and_operations,
              placement: P8,
              relative_placement: RP8,
              scale_score: 408,
              rn_subject_test: 8,
            }
          - {
              student_id: 90001,
              subject: Reading,
              academic_year_int: 2026,
              start_date: 2025-09-01,
              completion_date: 2025-09-15,
              domain_name: phonics,
              placement: P9,
              relative_placement: RP9,
              scale_score: 409,
              rn_subject_test: 9,
            }
          - {
              student_id: 90001,
              subject: Reading,
              academic_year_int: 2026,
              start_date: 2025-09-01,
              completion_date: 2025-09-15,
              domain_name: phonological_awareness,
              placement: P10,
              relative_placement: RP10,
              scale_score: 410,
              rn_subject_test: 10,
            }
          - {
              student_id: 90001,
              subject: Reading,
              academic_year_int: 2026,
              start_date: 2025-09-01,
              completion_date: 2025-09-15,
              domain_name: reading_comprehension_informational_text,
              placement: P11,
              relative_placement: RP11,
              scale_score: 411,
              rn_subject_test: 11,
            }
          - {
              student_id: 90001,
              subject: Reading,
              academic_year_int: 2026,
              start_date: 2025-09-01,
              completion_date: 2025-09-15,
              domain_name: reading_comprehension_literature,
              placement: P12,
              relative_placement: RP12,
              scale_score: 412,
              rn_subject_test: 12,
            }
          - {
              student_id: 90001,
              subject: Reading,
              academic_year_int: 2026,
              start_date: 2025-09-01,
              completion_date: 2025-09-15,
              domain_name: reading_comprehension_overall,
              placement: P13,
              relative_placement: RP13,
              scale_score: 413,
              rn_subject_test: 13,
            }
  ```

  Note: `vocabulary` does not appear in `expect` — its all-null tuple must be
  dropped by the `UNPIVOT`, so only 13 of the 14 domains produce a row.

- [ ] **Step 3: Run the unit test and confirm it fails**

  Run:

  ```bash
  uv run dbt test --select int_iready__domain_unpivot,test_type:unit --project-dir /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-iready-domain-unpivot-placement-scale-score/src/dbt/kipptaf
  ```

  Expected: FAIL. The current model only selects `relative_placement` (no
  `placement` or `scale_score` column), so the unit test errors or reports a
  column mismatch against `expect`.

- [ ] **Step 4: Rewrite the model with a multi-column tuple UNPIVOT**

  Replace the full contents of
  `src/dbt/kipptaf/models/iready/intermediate/int_iready__domain_unpivot.sql`
  with:

  ```sql
  with
      domain_unpivot as (
          select
              _dbt_source_relation,
              student_id,
              `subject`,
              academic_year_int,
              `start_date`,
              completion_date,
              domain_name,
              placement,
              relative_placement,
              scale_score,
          from
              {{ ref("int_iready__diagnostic_results") }} unpivot (
                  (placement, relative_placement, scale_score) for domain_name in (
                      (
                          phonics_placement,
                          phonics_relative_placement,
                          phonics_scale_score
                      ) as 'phonics',
                      (
                          algebra_and_algebraic_thinking_placement,
                          algebra_and_algebraic_thinking_relative_placement,
                          algebra_and_algebraic_thinking_scale_score
                      ) as 'algebra_and_algebraic_thinking',
                      (
                          geometry_placement,
                          geometry_relative_placement,
                          geometry_scale_score
                      ) as 'geometry',
                      (
                          measurement_and_data_placement,
                          measurement_and_data_relative_placement,
                          measurement_and_data_scale_score
                      ) as 'measurement_and_data',
                      (
                          number_and_operations_placement,
                          number_and_operations_relative_placement,
                          number_and_operations_scale_score
                      ) as 'number_and_operations',
                      (
                          high_frequency_words_placement,
                          high_frequency_words_relative_placement,
                          high_frequency_words_scale_score
                      ) as 'high_frequency_words',
                      (
                          phonological_awareness_placement,
                          phonological_awareness_relative_placement,
                          phonological_awareness_scale_score
                      ) as 'phonological_awareness',
                      (
                          reading_comprehension_informational_text_placement,
                          reading_comprehension_informational_text_relative_placement,
                          reading_comprehension_informational_text_scale_score
                      ) as 'reading_comprehension_informational_text',
                      (
                          reading_comprehension_literature_placement,
                          reading_comprehension_literature_relative_placement,
                          reading_comprehension_literature_scale_score
                      ) as 'reading_comprehension_literature',
                      (
                          reading_comprehension_overall_placement,
                          reading_comprehension_overall_relative_placement,
                          reading_comprehension_overall_scale_score
                      ) as 'reading_comprehension_overall',
                      (
                          vocabulary_placement,
                          vocabulary_relative_placement,
                          vocabulary_scale_score
                      ) as 'vocabulary',
                      (
                          comprehension_informational_text_placement,
                          comprehension_informational_text_relative_placement,
                          comprehension_informational_text_scale_score
                      ) as 'comprehension_informational_text',
                      (
                          comprehension_literature_placement,
                          comprehension_literature_relative_placement,
                          comprehension_literature_scale_score
                      ) as 'comprehension_literature',
                      (
                          comprehension_overall_placement,
                          comprehension_overall_relative_placement,
                          comprehension_overall_scale_score
                      ) as 'comprehension_overall'
                  )
              )
      )

  select
      student_id,
      `subject`,
      academic_year_int,
      `start_date`,
      completion_date,
      domain_name,
      placement,
      relative_placement,
      scale_score,

      row_number() over (
          partition by
              _dbt_source_relation,
              student_id,
              `subject`,
              academic_year_int,
              `start_date`,
              completion_date
          order by domain_name asc
      ) as rn_subject_test,
  from domain_unpivot
  ```

- [ ] **Step 5: Run the unit test and confirm it passes**

  Run:

  ```bash
  uv run dbt test --select int_iready__domain_unpivot,test_type:unit --project-dir /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-iready-domain-unpivot-placement-scale-score/src/dbt/kipptaf
  ```

  Expected: PASS.

- [ ] **Step 6: Add column descriptions and the new columns to
      `properties.yml`**

  In the same file, replace the `models:` block (everything above the
  `unit_tests:` key added in Step 2) with:

  ```yaml
  models:
    - name: int_iready__domain_unpivot
      description:
        Unpivots per-domain placement, relative placement, and scale score from
        i-Ready diagnostic results into one row per domain per test
        administration.
      config:
        materialized: table
      columns:
        - name: student_id
          data_type: int64
          description: PowerSchool student number for the student tested.
        - name: subject
          data_type: string
          description: i-Ready subject the diagnostic covers — Reading or Math.
        - name: academic_year_int
          data_type: int64
          description: Academic year of the diagnostic administration.
        - name: start_date
          data_type: date
          description: Date the student started the diagnostic.
        - name: completion_date
          data_type: date
          description: Date the student completed the diagnostic.
        - name: domain_name
          data_type: string
          description:
            i-Ready domain this row's placement, relative placement, and scale
            score apply to.
        - name: placement
          data_type: string
          description: Domain-specific placement label from the diagnostic.
        - name: relative_placement
          data_type: string
          description:
            Domain-specific relative grade-level placement from the diagnostic.
        - name: scale_score
          data_type: int64
          description: Domain-specific i-Ready scale score from the diagnostic.
        - name: rn_subject_test
          data_type: int64
          description:
            ROWNUMBER of value partitioned by _dbt_source_relation, student_id,
            subject, academic_year_int, start_date, completion_date ordered by
            domain_name.
  ```

- [ ] **Step 7: Re-run the unit test after the properties change**

  Run:

  ```bash
  uv run dbt test --select int_iready__domain_unpivot,test_type:unit --project-dir /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-iready-domain-unpivot-placement-scale-score/src/dbt/kipptaf
  ```

  Expected: PASS (properties changes are docs-only and don't affect model
  behavior, but this confirms the yml still parses and the test still runs).

- [ ] **Step 8: Lint the changed files**

  Run:

  ```bash
  cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-iready-domain-unpivot-placement-scale-score && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/kipptaf/models/iready/intermediate/int_iready__domain_unpivot.sql src/dbt/kipptaf/models/iready/intermediate/properties/int_iready__domain_unpivot.yml </dev/null
  ```

  Expected: No issues (or autofix-and-recheck reports clean, matching how the
  spec markdown was handled earlier in this branch). If sqlfluff flags
  formatting, address it before committing — don't rely on the pre-commit hook
  alone, since it only runs `fmt`, not `sqlfluff`/`yamllint`.

- [ ] **Step 9: Commit**

  ```bash
  git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-iready-domain-unpivot-placement-scale-score add src/dbt/kipptaf/models/iready/intermediate/int_iready__domain_unpivot.sql src/dbt/kipptaf/models/iready/intermediate/properties/int_iready__domain_unpivot.yml
  git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-iready-domain-unpivot-placement-scale-score commit -m "$(cat <<'EOF'
  feat(dbt): unpivot placement and scale_score in int_iready__domain_unpivot

  Refs #4706
  EOF
  )"
  ```

---

### Task 2: Simplify the consumer's `domain_name` derivation

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__miami_k2_iready.sql:42-44`

**Interfaces:**

- Consumes: `int_iready__domain_unpivot.domain_name` (now a clean slug, e.g.
  `'phonics'`, per Task 1) and `int_iready__domain_unpivot.relative_placement`
  (unchanged). Does **not** consume the new `placement` / `scale_score` columns.
- Produces: `rpt_tableau__miami_k2_iready` with the same column set as before —
  only the `domain_name` value's derivation changes (readable slug with spaces
  instead of a suffix-trimmed string).

- [ ] **Step 1: Simplify the `domain_name` derivation**

  In `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__miami_k2_iready.sql`,
  replace:

  ```sql
      regexp_replace(
          left(up.domain_name, length(up.domain_name) - 19), '_', ' '
      ) as domain_name,
  ```

  with:

  ```sql
      regexp_replace(up.domain_name, '_', ' ') as domain_name,
  ```

- [ ] **Step 2: Validate the SQL compiles against prod (no warehouse write)**

  Run:

  ```bash
  uv run dbt compile --select rpt_tableau__miami_k2_iready --target prod --project-dir /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-iready-domain-unpivot-placement-scale-score/src/dbt/kipptaf
  ```

  Expected: compiles with no errors.

- [ ] **Step 3: Build both changed models into your dev schema**

  Run:

  ```bash
  uv run dbt build --select int_iready__domain_unpivot rpt_tableau__miami_k2_iready --target dev --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod --project-dir /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-iready-domain-unpivot-placement-scale-score/src/dbt/kipptaf
  ```

  Expected: PASS for both models. Every other upstream (
  `int_iready__diagnostic_results`, `base_powerschool__course_enrollments`,
  `int_extracts__student_enrollments`) resolves to prod via `--defer` since
  neither is selected.

- [ ] **Step 4: Inspect the rebuilt `domain_name` values**

  Run:

  ```bash
  uv run dbt show --select rpt_tableau__miami_k2_iready --target dev --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod --project-dir /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-iready-domain-unpivot-placement-scale-score/src/dbt/kipptaf --limit 20
  ```

  Expected: `domain_name` values read as clean space-separated labels (e.g.
  `algebra and algebraic thinking`, `phonics`) with no residual digits or
  leftover suffix fragments — confirming the new slug-based `domain_name` from
  Task 1 flows through correctly.

- [ ] **Step 5: Lint the changed file**

  ```bash
  cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-iready-domain-unpivot-placement-scale-score && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__miami_k2_iready.sql </dev/null
  ```

  Expected: No issues.

- [ ] **Step 6: Commit**

  ```bash
  git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-iready-domain-unpivot-placement-scale-score add src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__miami_k2_iready.sql
  git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-iready-domain-unpivot-placement-scale-score commit -m "$(cat <<'EOF'
  refactor(dbt): simplify domain_name derivation in rpt_tableau__miami_k2_iready

  Refs #4706
  EOF
  )"
  ```
