# Bridges Carry Only Error Tests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every test on the kipptaf bridge marts is `error` severity and passes
in prod, and the one real orphan class is caught upstream as an actionable
`warn`.

**Architecture:** Three changes. First, a singular `warn` test on
`int_assessments__scaffold` flags replacement-curriculum rows whose region is
not tagged on the assessment. Second,
`bridge_assessment_expectations_student_scoped` drops those rows, and a unit
test proves it. Third, the bridges folder loses its non-regression tests and
gains one `+severity: error` block.

**Tech Stack:** dbt 1.12 on BigQuery, kipptaf project.

**Spec:** #5948 design (issuecomment-6202532128) as written into
`.claude/rules/dbt-yaml.md` → _Test config defaults_; scope and decisions in
#5957.

## Global Constraints

- Worktree:
  `/workspaces/teamster/.claude/worktrees/cbini/test/claude-bridge-error-tests`.
  Every path below is relative to `src/dbt/kipptaf/` inside it.
- Run dbt as
  `uv run dbt ... --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod`
  (the `--state` path is absolute; the worktree has no `target/prod`).
- An `error` test lands only after its query returns 0 rows in prod.
- A `warn` description names the source system, what is wrong, and what to
  change there.
- Keep every `foreign_key` meta and constraint. Only `data_tests:` entries go.
- Columns with per-column `data_tests:` sort to the top of `columns:`.
- No PII in commits or the PR. Report counts only, never student rows.

## Review Focus

1. A non-replacement row whose region is not in `regions_array` must NOT be
   dropped by the bridge filter. Today none exist, because those rows take their
   region from the array. The filter is scoped to `is_replacement` so it cannot
   start dropping them later. Task 2's unit test pins this with one
   non-replacement row.
2. The region strings must match: the scaffold replacement branch reads
   `stg_google_sheets__people__locations.city` (`Paterson`), and `regions_array`
   holds AppSheet values (`Camden`, `Newark`, `Miami`). In prod they matched for
   every non-orphan row. Task 1's prod run returning exactly 5 rows confirms it.
3. Does the folder block reach generic tests defined in the bridge YAMLs? Task 3
   checks every bridge node's resolved severity, not just the YAML.
4. The singular test reads two models. Without `meta.dagster.ref` Dagster never
   sees it. Task 1 sets it.
5. The test deletions must remove exactly the 17 intended nodes. Task 3 diffs
   the parsed test nodes against main.

---

### Task 1: Warn on untagged replacement regions

**Files:**

- Create: `tests/int_assessments__scaffold__replacement_region_untagged.sql`
- Modify: `tests/properties.yml` (new entry beside
  `int_assessments__assessments_members__no_cross_source_canonical`)

**Interfaces:**

- Produces: a singular test named
  `int_assessments__scaffold__replacement_region_untagged`. It returns one row
  per scaffold row where `is_internal_assessment and is_replacement` and
  `region not in unnest(c.regions_array)`. Join scaffold → members on (`source`,
  `assessment_id`) → canonical on (`source`, `canonical_assessment_id`), the
  same joins the bridge uses. Project only `source`, `assessment_id`,
  `canonical_assessment_id`, `region`, `powerschool_school_id`. Do not project
  student identifiers.

- [ ] **Step 1: Write the test SQL**, following the shape of
      `tests/int_assessments__assessments_members__no_cross_source_canonical.sql`.
      Add a one-line comment above the select: replacement students can only be
      reported against a region the assessment is tagged for.
- [ ] **Step 2: Add the properties entry.** Keep the project default severity
      (`warn`). Set `config.meta.dagster.ref.name: int_assessments__scaffold`.
      The description says: a student on a replacement curriculum took an
      Illuminate assessment that is not tagged for the student's region. Fix it
      in one of two ways. Add the region to the assessment's `regions_assessed`
      in the AppSheet Illuminate assessments extension. Or, if the student
      should not have taken it, remove the student's assessment in Illuminate.
      Until then, `bridge_assessment_expectations_student_scoped` leaves the row
      out.
- [ ] **Step 3: Run it against prod.** Run:
      `uv run dbt test --select int_assessments__scaffold__replacement_region_untagged <defer flags>`
      Expected: `WARN 5`.
- [ ] **Step 4: Commit.**
      `test(dbt): warn on replacement assessments outside tagged regions`

### Task 2: Drop untagged replacement rows from the student-scoped bridge

**Files:**

- Modify:
  `models/marts/bridges/bridge_assessment_expectations_student_scoped.sql:40`
- Modify:
  `models/marts/bridges/properties/bridge_assessment_expectations_student_scoped.yml`
  (add `unit_tests:`)

**Interfaces:**

- Consumes: Task 1's rule: a replacement row is kept only when its `region` is
  in the canonical `regions_array`.
- Produces: the bridge selects `sc.region` and `c.regions_array` in the
  `expectations` CTE and applies the filter there.

- [ ] **Step 1: Write the unit test**
      `test_bridge_assessment_expectations_student_scoped_drops_untagged_replacement`.
      Mock `int_assessments__scaffold` (dict) with 3 rows that share one
      assessment, all `is_internal_assessment: true`: (a)
      `is_replacement: true`, `region: Newark`; (b) `is_replacement: true`,
      `region: Paterson`; (c) `is_replacement: false`, `cc_dcid: null`,
      `region: Paterson`. Mock `int_assessments__assessments_members` (dict)
      with that one assessment. Mock `int_assessments__assessments_canonical`
      with `format: sql`, because `regions_array` is an array:
      `regions_array = ['Camden', 'Newark']`. Mock
      `stg_google_sheets__reporting__terms` with zero rows. Expect exactly 2
      rows, (a) and (c), asserting only `assessment_expectation_key`. Compute
      the expected keys by the PK's hash inputs (`student_number`, `source`,
      `assessment_id`, `administered_at`); give each row a distinct
      `student_number` so the keys differ.
- [ ] **Step 2: Run it.** Run:
      `uv run dbt test --select "bridge_assessment_expectations_student_scoped,test_type:unit" <defer flags>`
      Expected: FAIL. Row (b) is present.
- [ ] **Step 3: Implement.** In the `expectations` CTE, select
      `sc.is_replacement` and `c.regions_array`. Change the `where` to keep a
      row when
      `sc.is_internal_assessment and (sc.is_replacement or sc.cc_dcid is null)`
      and it is not a replacement whose `sc.region` is outside
      `c.regions_array`. Put the predicate in `where`, as a comparison of both
      join sides (S10 allows this).
- [ ] **Step 4: Re-run the unit test.** Expected: PASS.
- [ ] **Step 5: Build against prod and check orphans.** Run:
      `uv run dbt build --select bridge_assessment_expectations_student_scoped <defer flags>`
      Expected: success. Then query the dev table left-joined to prod
      `kipptaf_marts.dim_assessment_administrations` on
      `assessment_administration_key`. Expected: 0 orphans. Row count = prod
      count minus 5.
- [ ] **Step 6: Commit.**
      `fix(dbt): drop untagged replacement rows from the student-scoped bridge`

### Task 3: Sort the bridge tests and turn the folder to error

**Files:**

- Modify: all 7 enabled `models/marts/bridges/properties/bridge_*.yml`
- Modify: `dbt_project.yml` (`data_tests:` block, lines 22-25)

**Interfaces:**

- Consumes: Task 2. With the filter in place, the student-scoped
  `assessment_administration_key` test would pass, but it is deleted here like
  the other 15.

- [ ] **Step 1: Delete the 16 `relationships` tests.** Remove each column's
      `data_tests:` block and move the column below the last tested column.
      `/tmp/claude-1000/-workspaces-teamster/695ec3bb-30c5-4464-961b-ce5e3ac5f630/scratchpad/drop_rel.py <yml> <column>`
      does one column per call. Columns: - enrollment_scoped:
      `assessment_administration_key`, `student_section_enrollment_key` -
      student_scoped: `assessment_administration_key`, `student_key`,
      `term_key` - course_section_teachers: `course_section_key`, `staff_key` -
      course_section_terms: `course_section_key`, `term_key` - student_contacts:
      `student_contact_person_key`, `student_key` - survey_expectations:
      `staff_key`, `student_contact_person_key` - survey_questions:
      `survey_key`, `survey_question_key`

      Also, by hand: delete both tests on
      `bridge_survey_expectations.survey_administration_key` (the `not_null` and
      the `relationships`), then move that column down.

- [ ] **Step 2: Add the folder block** under `data_tests:` in `dbt_project.yml`:

      ```yaml
      data_tests:
        +severity: warn
        +store_failures: true
        +store_failures_as: view
        kipptaf:
          marts:
            bridges:
              +severity: error
      ```

- [ ] **Step 3: Diff the parsed test nodes.** Run `dbt parse --no-partial-parse`
      on fresh main and on the branch, then diff the `resource_type == 'test'`
      names. Expected: exactly the 17 deleted nodes removed, and Task 1's
      singular test added. Nothing else.
- [ ] **Step 4: Check resolved severity.** Run:
      `uv run dbt ls --resource-type test --select "path:models/marts/bridges" --output json --output-keys "name config"`
      Expected: 7 nodes, all `severity` `ERROR`.
- [ ] **Step 5: Run the bridge tests against prod.** Run:
      `uv run dbt build --select "path:models/marts/bridges" <defer flags>`
      Expected: every test PASS, 0 WARN, 0 ERROR. Build the student-scoped
      bridge into dev in the same run so its grain test sees Task 2.
- [ ] **Step 6: Lint and commit.** Run `trunk check --force --no-fix` on every
      touched SQL, YAML, and this plan. Commit:
      `test(dbt): bridges carry only error tests`.
