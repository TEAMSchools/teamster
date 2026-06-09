# Enrollment-Scoped Assessment Fact — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the diamond path in
`fct_assessment_scores_enrollment_scoped` by dropping the direct `student_key`
FK and reaching the student through a single, total
`student_section_enrollment_key → dim_student_section_enrollments → dim_student_enrollments → dim_students`
chain.

**Architecture:** Expand `int_assessments__resolved_section_enrollments` into
the single section-resolver for all scores (internal + state), sourcing the
enrollment inventory `int_assessments__course_enrollments` directly. Resolve
each score to one section by date-window containment, tiered
`subject_section → homeroom`; unresolved rows drop. Thread a real per-student
`test_date` from state sources so state anchors on a real date. The fact drops
`student_key`, INNER-joins the resolver, and gains an `enrollment_resolution`
degenerate dim.

**Tech Stack:** dbt (BigQuery), `dbt_utils` (`union_relations`,
`generate_surrogate_key`, `deduplicate`), dbt unit tests + data tests, single-PR
cross-project clone workflow.

**Spec:**
`docs/superpowers/specs/2026-06-05-fct-assessment-scores-enrollment-scoped-diamond-design.md`
· **Issue:** [#4135](https://github.com/TEAMSchools/teamster/issues/4135) ·
**Follow-up:** [#4139](https://github.com/TEAMSchools/teamster/issues/4139)

**Validation idiom (not pytest):** dbt changes are validated by (a) dbt
data/unit tests, (b) `uv run dbt build --select <model>` against kipptaf, (c)
`dbt show` / BigQuery `INFORMATION_SCHEMA` + row-count checks against the
PR-branch schema. All `dbt`/`git` commands run against the worktree:
`/workspaces/teamster/.worktrees/cbini/refactor/claude-assessment-scores-enrollment-scoped`.
Use `uv run dbt ... --project-dir <worktree>/src/dbt/<project>` and
`git -C <worktree>`.

---

## File Structure

**Cross-project source threading (single-PR clone workflow):**

- `src/dbt/kippmiami/models/fldoe/intermediate/int_fldoe__all_assessments.sql` —
  district FLDOE int: expose `test_date` (from `date_taken`).
- NJGPA upstream (exact file TBD in Task 3): one of
  `src/dbt/pearson/models/staging/stg_pearson__njgpa.sql` or
  `src/dbt/kipppaterson/models/.../int_pearson__njgpa.sql` — stop dropping unit
  datetimes.
- `src/dbt/kipptaf/models/sources-kippmiami.yml` (+
  `sources-kippnewark/camden/paterson.yml` if NJGPA needs them) — add the
  `target=staging` schema branch.

**kipptaf state intermediates:**

- `src/dbt/kipptaf/models/pearson/staging/stg_pearson__{njsla,njsla_science,njgpa,parcc}.sql`
  — derive `test_date`.
- `src/dbt/kipptaf/models/pearson/intermediate/int_pearson__all_assessments.sql`
  — add `test_date` to `include` + select.
- `src/dbt/kipptaf/models/fldoe/intermediate/int_fldoe__all_assessments.sql` —
  carry `test_date` through.
- Their `properties/*.yml` — document `test_date`.

**Resolver (heart of the change):**

- `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__resolved_section_enrollments.sql`
  — full rewrite.
- `.../intermediate/properties/int_assessments__resolved_section_enrollments.yml`
  — rewrite description, columns (`resolution_type`), uniqueness test, unit
  tests.

**Mart:**

- `src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_enrollment_scoped.sql`
  — drop `student_key`, real state `test_date_key`, INNER join resolver,
  `enrollment_resolution`.
- `.../marts/facts/properties/fct_assessment_scores_enrollment_scoped.yml` —
  remove `student_key`, add `enrollment_resolution`, tighten descriptions.

---

## Phase 0 — CI wiring for the single-PR cross-project workflow

> **Sequencing decision (2026-06-05):** Single-PR with **staged externals** (not
> clone-from-prod). The NJGPA package columns (Task 3) and FLDOE district
> `test_date` (Task 2) are _new_ columns absent from prod, so
> `dbt clone --state target/prod` can't introduce them and
> `dbt_utils.union_relations` intersects the prod schema. Instead: add the
> `target=staging` source-schema branch (Task 0),
> `stage_external_sources --target staging` for the pearson + fldoe GCS
> externals, then **build** the modified district/package models into the
> `zz_stg_<district>_*` schemas so kipptaf resolves the new columns. The
> `stage_external_sources` + district-build commands are **run/confirmed by the
> user** (env-touching) at the Task 9 pause.

### Task 0: Stage the cross-project sources

Per `src/dbt/kipptaf/CLAUDE.md` → "Single-PR cross-project workflow": kipptaf CI
builds only kipptaf and won't auto-populate district staging schemas, so the
district-side edits (FLDOE int, NJGPA upstream) must be reachable via the
`zz_stg_<district>_*` schema branch.

**Files:**

- Modify: `src/dbt/kipptaf/models/sources-kippmiami.yml` (and
  `sources-kippnewark.yml` / `sources-kippcamden.yml` /
  `sources-kipppaterson.yml` if Task 3 edits NJGPA there).

- [ ] **Step 1:** In each affected `sources-kipp*.yml`, confirm the
      `target=staging` schema branch routes the source schema to
      `zz_stg_<district>_<source>` (the region source-schema pattern). If the
      file already uses the standard inline-Jinja region pattern, no edit is
      needed yet — note which sources Task 3 will touch and revisit.

- [ ] **Step 2:** Defer the clone-seeding command to Task 9 (after the district
      models are edited), since clone seeds from prod + the branch's compiled
      models. Record here that the clone command will be:

```bash
uv --directory /workspaces/teamster/.worktrees/cbini/refactor/claude-assessment-scores-enrollment-scoped run dbt clone \
  --target staging --state target/prod \
  --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-assessment-scores-enrollment-scoped/src/dbt/kippmiami
# repeat per affected district project (kippnewark/kippcamden/kipppaterson) if NJGPA touches them
```

- [ ] **Step 3: Commit** (no-op if no file change yet — otherwise):

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-assessment-scores-enrollment-scoped add -u
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-assessment-scores-enrollment-scoped commit -m "chore(dbt): stage cross-project sources for assessment test_date threading"
```

---

## Phase 1 — Thread `test_date` from state sources

### Task 1: kipptaf Pearson staging — derive `test_date` (NJSLA / Science / PARCC)

These three already carry the `unit{1..4}online{start,end}datetime` columns at
kipptaf staging (verified). Derive one DATE.

**Files:**

- Modify: `src/dbt/kipptaf/models/pearson/staging/stg_pearson__njsla.sql`
- Modify:
  `src/dbt/kipptaf/models/pearson/staging/stg_pearson__njsla_science.sql`
- Modify: `src/dbt/kipptaf/models/pearson/staging/stg_pearson__parcc.sql`
- Modify: `.../pearson/staging/properties/*.yml` (add `test_date`)

- [ ] **Step 1: Profile the source datetimes** (confirm format before parsing):

```bash
uv run dbt show --inline "select unit1onlineteststartdatetime, paperattemptcreatedate from {{ ref('stg_pearson__njsla') }} where unit1onlineteststartdatetime is not null limit 5" \
  --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-assessment-scores-enrollment-scoped/src/dbt/kipptaf
```

Expected: ISO-ish datetime strings (e.g. `2024-05-01T09:13:00`). Note the exact
format for the parse in Step 2.

- [ ] **Step 2: Add the `test_date` column** to each model's final `select`
      (adjust the parse function to the observed format;
      `safe.parse_timestamp`/`safe_cast` guards bad values):

```sql
    coalesce(
        date(
            least(
                safe_cast(unit1onlineteststartdatetime as timestamp),
                safe_cast(unit2onlineteststartdatetime as timestamp),
                safe_cast(unit3onlineteststartdatetime as timestamp),
                safe_cast(unit4onlineteststartdatetime as timestamp)
            )
        ),
        safe_cast(paperattemptcreatedate as date)
    ) as test_date,
```

PARCC uses `attemptcreatedate` (not `paperattemptcreatedate`) — use whichever
the model exposes; NJSLA Science has the same unit columns as NJSLA. If a model
lacks `unit4...`, drop that arg.

- [ ] **Step 3: Add `test_date` to each staging `properties/*.yml`** with a
      description (no stats):

```yaml
- name: test_date
  data_type: date
  description: >-
    Date the student took the assessment, derived from the earliest online unit
    start datetime, falling back to the paper attempt create date.
```

- [ ] **Step 4: Build + verify populated:**

```bash
uv run dbt build --select stg_pearson__njsla stg_pearson__njsla_science stg_pearson__parcc \
  --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-assessment-scores-enrollment-scoped/src/dbt/kipptaf
```

Then in BigQuery MCP, against the PR-branch schema, confirm
`countif(test_date is null) / count(*)` is low for online-tested rows.

- [ ] **Step 5: Commit:**

```bash
git -C <worktree> add -u && git -C <worktree> commit -m "feat(dbt): derive test_date on Pearson NJSLA/Science/PARCC staging"
```

### Task 2: FLDOE district int — expose `test_date` (cross-project, kippmiami)

`kippmiami stg_fldoe__{fast,eoc,science}` already parse `date_taken` to `DATE`,
but `kippmiami int_fldoe__all_assessments` doesn't select it.

**Files:**

- Modify:
  `src/dbt/kippmiami/models/fldoe/intermediate/int_fldoe__all_assessments.sql`
- Modify:
  `src/dbt/kippmiami/models/fldoe/intermediate/properties/int_fldoe__all_assessments.yml`
  (add `test_date`)

- [ ] **Step 1:** Read the model's final `select` and the per-test CTEs. Add
      `date_taken as test_date` (the FAST branch is already `DATE`; for
      `eoc`/`science`, confirm the staging cast — `stg_fldoe__eoc/science` carry
      it as STRING, so cast `safe_cast(... as date)` or align with the FAST
      parse) to each unioned branch and the final select.

- [ ] **Step 2:** Add `test_date` to the properties YAML with a description.

- [ ] **Step 3: Build against kippmiami:**

```bash
uv run dbt build --select stg_fldoe__fast stg_fldoe__eoc stg_fldoe__science int_fldoe__all_assessments \
  --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-assessment-scores-enrollment-scoped/src/dbt/kippmiami
```

Expected: PASS; `test_date` populated.

- [ ] **Step 4: Commit:**

```bash
git -C <worktree> add -u && git -C <worktree> commit -m "feat(dbt): expose test_date in kippmiami int_fldoe__all_assessments"
```

### Task 3: NJGPA upstream — stop dropping unit datetimes (cross-project)

kipptaf `stg_pearson__njgpa` does NOT expose the unit datetimes (verified —
present on NJSLA/Science/PARCC but not NJGPA). Find where they're dropped and
restore them.

**Files (one of):**

- `src/dbt/pearson/models/staging/stg_pearson__njgpa.sql` (package, used by
  Newark/Camden)
- `src/dbt/kipppaterson/models/.../int_pearson__njgpa.sql` (Paterson's variant —
  kipptaf unions `source("kipppaterson_pearson", "int_pearson__njgpa")`)

- [ ] **Step 1: Trace the drop point.** Run, for each district source feeding
      kipptaf `stg_pearson__njgpa`:

```bash
uv run dbt show --inline "select column_name from \`teamster-332318\`.\`region-us\`.INFORMATION_SCHEMA.COLUMNS where table_schema='kippcamden_pearson' and table_name='stg_pearson__njgpa' and lower(column_name) like 'unit%datetime'" \
  --project-dir <worktree>/src/dbt/kipptaf
```

Repeat for `kippnewark_pearson` and `kipppaterson_pearson` (table
`int_pearson__njgpa`). Whichever returns zero is the drop point.
`union_relations` takes the column intersection, so if ANY source lacks them,
kipptaf loses them.

- [ ] **Step 2:** In the drop-point model(s), stop excluding
      `unit{1..3}online{start,end}datetime` / `paperattemptcreatedate` (NJGPA
      has units 1–3). If it's a `select * except(...)`, remove them from the
      `except` list; if it's an explicit select, add them.

- [ ] **Step 3:** Add the same `test_date` derivation (Task 1, Step 2 shape,
      units 1–3) to kipptaf `stg_pearson__njgpa.sql` + its properties YAML.

- [ ] **Step 4: Build** the affected district model(s) and kipptaf
      `stg_pearson__njgpa`; verify `test_date` populated.

- [ ] **Step 5: Commit:**

```bash
git -C <worktree> add -u && git -C <worktree> commit -m "feat(dbt): thread NJGPA test_date from unit datetimes"
```

### Task 4: kipptaf state intermediates carry `test_date`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/pearson/intermediate/int_pearson__all_assessments.sql`
- Modify:
  `src/dbt/kipptaf/models/fldoe/intermediate/int_fldoe__all_assessments.sql`
- Modify: both `properties/*.yml`

- [ ] **Step 1 (Pearson):** Add `"test_date"` to the
      `union_relations(... include=[...])` list (line ~12–47), and add
      `u.test_date,` to the `transformations` select (after the other
      pass-throughs).

- [ ] **Step 2 (FLDOE):** Add `fl.test_date,` to the final `select` (it unions
      `source("kippmiami_fldoe", "int_fldoe__all_assessments")`, which now
      carries it after Task 2).

- [ ] **Step 3:** Add `test_date` to both properties YAMLs.

- [ ] **Step 4: Build + verify:**

```bash
uv run dbt build --select int_pearson__all_assessments int_fldoe__all_assessments \
  --project-dir <worktree>/src/dbt/kipptaf
```

Then confirm `test_date` is populated on both (BigQuery, PR-branch schema):
`countif(test_date is null)/count(*)`.

- [ ] **Step 5: Commit:**

```bash
git -C <worktree> add -u && git -C <worktree> commit -m "feat(dbt): carry test_date through kipptaf state assessment intermediates"
```

---

## Phase 2 — Rebuild the resolver

### Task 5: Rewrite `int_assessments__resolved_section_enrollments`

The resolver becomes the single section-resolver for all scores, sourcing
`int_assessments__course_enrollments` (inventory) directly. Output grain: one
row per score (internal:
`student_number + canonical_assessment_id + _dbt_source_project`; state:
`student_number + academic_year + subject_area + administration_period + _dbt_source_project`),
each carrying `student_section_enrollment_key` + `resolution_type`.

**Files:**

- Rewrite:
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__resolved_section_enrollments.sql`

- [ ] **Step 1: Profile the inventory's HR + subject coverage and the year
      offset** (confirm join keys before writing):

```bash
uv run dbt show --inline "select courses_credittype, illuminate_subject_area, illuminate_academic_year, count(*) n from {{ ref('int_assessments__course_enrollments') }} group by 1,2,3 order by n desc limit 20" \
  --project-dir <worktree>/src/dbt/kipptaf
```

Confirm: HR rows present; `illuminate_academic_year = cc_academic_year + 1`;
`illuminate_subject_area` values (`Text Study`, `Mathematics`, `Science`,
`Social Studies`, `Writing`).

- [ ] **Step 2: Write the rewritten model.** Structure (CTEs):
  1. `scores` — UNION of three score sources, normalized to
     `(student_number, _dbt_source_project, academic_year, subject_area, anchor_date, score_grain_key, source_type)`:
     - **internal** from `int_assessments__scaffold` (`is_internal_assessment`
       rows): `subject_area`, `coalesce(date_taken, administered_at)` as
       `anchor_date`, `canonical_assessment_id`, `academic_year`.
     - **state_nj** from `int_pearson__all_assessments`:
       `localstudentidentifier` as `student_number`, `illuminate_subject` as
       `subject_area`, `test_date` as `anchor_date`, `academic_year`,
       `administration_period`.
     - **state_fl** from `int_fldoe__all_assessments`: `student_number`,
       `illuminate_subject`, `test_date` as `anchor_date`, `academic_year`,
       `administration_window` as `administration_period`.
  2. `state_subject_map` — derive `course_subject` from the state `subject_area`
     via an inline `CASE` (Component 2): `Text Study → Text Study`,
     `Mathematics → Mathematics`, `Science → Science`, etc. (internal
     `subject_area` already matches `illuminate_subject_area`, so pass through).
  3. `candidates_subject` — join `scores` to
     `int_assessments__course_enrollments` on
     `student_number = powerschool_student_number`, `_dbt_source_project`,
     `course_subject = illuminate_subject_area`,
     `academic_year = (illuminate_academic_year - 1)`, and
     `anchor_date >= cc_dateenrolled and anchor_date < cc_dateleft` (half-open).
     Stamp `resolution_type = 'subject_section'`.
  4. `candidates_homeroom` — for scores NOT resolved in `candidates_subject`,
     join the inventory on `courses_credittype = 'HR'`, `academic_year`,
     `anchor_date` in window. Stamp `resolution_type = 'homeroom'`.
  5. `all_candidates` — `union all` of the two;
     `dbt_utils.deduplicate(partition_by="<score_grain_key cols>", order_by="resolution_type asc, cc_dateleft desc")`
     so `subject_section` (alphabetically before `homeroom`? — no: 'homeroom' <
     'subject_section', so order by a numeric tier instead). Use an explicit
     `tier` int (1 subject, 2 homeroom) and
     `order_by="tier asc, cc_dateleft desc"`.
  6. final `select` — `powerschool_student_number`, `canonical_assessment_id`
     (null for state), state grain cols, `_dbt_source_project`,
     `cc_source_project`, `resolution_type`, and
     `{{ dbt_utils.generate_surrogate_key(["cc_dcid", "cc_source_project"]) }} as student_section_enrollment_key`.

  Honor `src/dbt/CLAUDE.md`: half-open date interval; no
  `select distinct`/`qualify` for dedup (use `dbt_utils.deduplicate`); no
  `GROUP BY ALL`; derive the `CASE` subject map as a named column in a CTE (not
  inline in `generate_surrogate_key`).

  **Academic-year offset differs by branch — do not use one join expression for
  both.** `int_assessments__scaffold.academic_year` is already
  `academic_year_clean` (the illuminate `+1` year), so the internal branch
  matches `inventory.illuminate_academic_year` **directly**. State
  `academic_year` is the raw year, so the state branch matches
  `inventory.illuminate_academic_year - 1` (equivalently `cc_academic_year`).
  Normalize each `scores` branch to a single `illuminate_academic_year` column
  in CTE 1 (internal: pass through; state: `academic_year + 1`) so CTE 3/4 join
  on one key.

- [ ] **Step 3: Validate one section per score** (`dbt show`, must return zero
      rows):

```bash
uv run dbt show --inline "with r as (select * from {{ ref('int_assessments__resolved_section_enrollments') }}) select count(*) c from (select powerschool_student_number, canonical_assessment_id, academic_year, subject_area, administration_period, _dbt_source_project, count(*) n from r group by 1,2,3,4,5,6 having n>1)" \
  --project-dir <worktree>/src/dbt/kipptaf
```

Expected: `c = 0`.

- [ ] **Step 4: Build:**

```bash
uv run dbt build --select int_assessments__resolved_section_enrollments \
  --project-dir <worktree>/src/dbt/kipptaf
```

- [ ] **Step 5: Commit:**

```bash
git -C <worktree> add -u && git -C <worktree> commit -m "feat(dbt): resolve all scores (internal+state) to one section, tiered subject->homeroom"
```

### Task 6: Rewrite resolver `properties.yml` (description, columns, tests, unit tests)

**Files:**

- Rewrite:
  `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__resolved_section_enrollments.yml`

- [ ] **Step 1:** Update `description` (now all scores, inventory-sourced,
      tiered, date-containment).

- [ ] **Step 2:** Replace the uniqueness test with the new grain:

```yaml
data_tests:
  - dbt_utils.unique_combination_of_columns:
      arguments:
        combination_of_columns:
          - powerschool_student_number
          - canonical_assessment_id
          - academic_year
          - subject_area
          - administration_period
          - _dbt_source_project
```

(NULL-safe: composite includes columns null on one branch — acceptable since the
populated subset differs by branch; if the test miscounts on nulls, switch to
`count(distinct format("%T", ...))` per `src/dbt/CLAUDE.md`.)

- [ ] **Step 3:** Add the `resolution_type` column with
      `accepted_values: [subject_section, homeroom]`. Update `source_column`
      meta on carried columns (no longer scaffold-only).

- [ ] **Step 4: Rewrite the `unit_tests`.** The existing four mock
      `int_assessments__scaffold` + `int_assessments__assessments_canonical`;
      the resolver now reads `int_assessments__course_enrollments` + the score
      sources. Re-mock for the new inputs, preserving the intent of each
      (in-window-over-phantom; single-candidate; tier fallback to homeroom;
      anchor date drives pick). Each `given` mocks
      `int_assessments__course_enrollments` rows (with `courses_credittype`,
      `illuminate_subject_area`, `illuminate_academic_year`, `cc_dateenrolled`,
      `cc_dateleft`, `cc_dcid`, `cc_source_project`,
      `powerschool_student_number`) and a `scores`-source row; `expect` asserts
      the chosen `cc_dcid` + `resolution_type`. Add one test for **homeroom
      fallback** (no subject section → HR picked,
      `resolution_type = 'homeroom'`) and one for **no enrollment → row
      absent**.

- [ ] **Step 5: Run tests:**

```bash
uv run dbt test --select int_assessments__resolved_section_enrollments \
  --project-dir <worktree>/src/dbt/kipptaf
uv run dbt parse --no-partial-parse --project-dir <worktree>/src/dbt/kipptaf   # bind unit-test/description YAML
```

Expected: PASS.

- [ ] **Step 6: Commit:**

```bash
git -C <worktree> add -u && git -C <worktree> commit -m "test(dbt): resolver YAML + unit tests for tiered all-score resolution"
```

---

## Phase 3 — Fact + contract

### Task 7: Rewrite `fct_assessment_scores_enrollment_scoped.sql`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_enrollment_scoped.sql`

- [ ] **Step 1: Internal branch** — replace the LEFT join to the resolver with
      an INNER join (drops internal rows with no resolved section). Keep
      `student_key` derivation removed (see Step 3). Add
      `sr.resolution_type as enrollment_resolution`.

- [ ] **Step 2: State branch** — set `test_date_key` to the real threaded
      `test_date` (replace `cast(null as date) as test_date`); INNER join the
      resolver on the state grain
      (`student_number, academic_year, subject_area, administration_period, _dbt_source_project`);
      drop the `left join dim_students` and the
      `if(ds.lea_student_identifier is not null, ...)` wrapper; add
      `sr.resolution_type as enrollment_resolution`.

- [ ] **Step 3: Remove `student_key`** from BOTH branches' `select` lists.
      Confirm `assessment_score_key` PK hash inputs are unchanged (they hash
      `student_number` + assessment identifiers, not the FK).

- [ ] **Step 4: Build:**

```bash
uv run dbt build --select fct_assessment_scores_enrollment_scoped \
  --project-dir <worktree>/src/dbt/kipptaf
```

Expected: PASS (contract may fail until Task 8 YAML — if so, do Task 8 first
then rebuild).

- [ ] **Step 5: Commit:**

```bash
git -C <worktree> add -u && git -C <worktree> commit -m "feat(dbt): drop student_key, INNER-join resolver, real state test_date_key on assessment fact"
```

### Task 8: Update fact `properties.yml`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_assessment_scores_enrollment_scoped.yml`

- [ ] **Step 1:** Remove the entire `student_key` column block (description,
      `constraints` FK, `relationships` test).

- [ ] **Step 2:** Add `enrollment_resolution`:

```yaml
- name: enrollment_resolution
  data_type: string
  description: >-
    How the section enrollment was resolved: subject_section (the section for
    the assessment's subject, active on the test date) or homeroom (the
    student's HR section, used when no subject section resolved). Filter to
    subject_section for course/section-level rollups.
  data_tests:
    - accepted_values:
        arguments:
          values: [subject_section, homeroom]
```

- [ ] **Step 3:** Tighten descriptions: `student_section_enrollment_key` (now
      populated for every row; note tier semantics + homeroom coarseness);
      `test_date_key` (now populated for state too).

- [ ] **Step 4: Build + verify contract/tests:**

```bash
uv run dbt build --select fct_assessment_scores_enrollment_scoped \
  --project-dir <worktree>/src/dbt/kipptaf
```

Expected: PASS, including `accepted_values` and `relationships`.

- [ ] **Step 5: Commit:**

```bash
git -C <worktree> add -u && git -C <worktree> commit -m "feat(dbt): fact YAML — remove student_key, add enrollment_resolution"
```

---

## Phase 4 — Cross-project CI seeding, validation, exposure check

### Task 9: Seed district staging + full build

- [ ] **Step 1: Refresh the prod manifest** (for clone `--state`):

```bash
uv run dbt parse --target prod --project-dir <worktree>/src/dbt/kippmiami --target-path target/prod
```

(Repeat for any district touched in Task 3.)

- [ ] **Step 2: Clone-seed** the affected district staging schemas (Task 0, Step
      2 command), per affected district.

- [ ] **Step 3: Full chain build** from the resolver/state intermediates down:

```bash
uv run dbt build --select int_pearson__all_assessments int_fldoe__all_assessments int_assessments__resolved_section_enrollments+ fct_assessment_scores_enrollment_scoped+ \
  --project-dir <worktree>/src/dbt/kipptaf
```

Expected: PASS.

### Task 10: Validate FK population + row-count delta (PR-branch schema)

- [ ] **Step 1: FK population** (per `marts/CLAUDE.md` "Verify FK population,
      not just compilation") — `student_section_enrollment_key` must be ~100%
      non-null:

```sql
select countif(student_section_enrollment_key is null) n_null, count(*) n_total
from `<pr_branch_schema>.fct_assessment_scores_enrollment_scoped`
```

Expected: `n_null = 0`.

- [ ] **Step 2: Resolution mix** sanity:

```sql
select enrollment_resolution, count(*) n
from `<pr_branch_schema>.fct_assessment_scores_enrollment_scoped` group by 1
```

Expected: mostly `subject_section`, a minority `homeroom`; no nulls.

- [ ] **Step 3: Row-count delta** vs prod — new total ≈ prod
      `n_resolved (13.6M) + n_student_no_section (604K)` minus the
      no-section/no-homeroom residual (the 39 + Paterson-style tail). Confirm
      the drop is bounded (single-digit thousands at most), not a large
      unexpected loss.

- [ ] **Step 4: State `test_date_key`** now populated:

```sql
select countif(test_date_key is null) n_null, count(*) n
from `<pr_branch_schema>.fct_assessment_scores_enrollment_scoped`
```

Expected: low null rate (internal always had it; state now populated).

- [ ] **Step 5: Internal section-resolution stability** — the resolver now
      re-resolves internal scores from the inventory directly (previously via
      the scaffold's pre-pick), so internal `student_section_enrollment_key`
      could shift. Compare the PR-branch fact to prod for internal rows and
      confirm the overwhelming majority keep the same section:

```sql
select countif(pr.student_section_enrollment_key = pd.student_section_enrollment_key) n_same,
       count(*) n_compared
from `<pr_branch_schema>.fct_assessment_scores_enrollment_scoped` pr
join `teamster-332318.kipptaf_marts.fct_assessment_scores_enrollment_scoped` pd
  using (assessment_score_key)
where pr.enrollment_resolution = 'subject_section'
```

Expected: `n_same / n_compared` ≈ 1.0. Investigate a material drop before merge
— it signals the inventory-direct join diverges from the prior scaffold pick.

### Task 11: Exposure / Cube check

- [ ] **Step 1:** Confirm nothing reads the dropped `student_key`:

```bash
rg -n "student_key" /workspaces/teamster/.worktrees/cbini/refactor/claude-assessment-scores-enrollment-scoped/src/cube/model/
```

Expected: no reference tied to this fact. If any, update the Cube model in this
PR (per `marts/CLAUDE.md` "Exposures are the consumer contract").

- [ ] **Step 2:** Confirm the `cube.yml` exposure `depends_on` still lists the
      fact; no rename occurred, so no change expected.

- [ ] **Step 3: Lint** the touched SQL/YAML from inside the worktree:

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-assessment-scores-enrollment-scoped && .trunk/tools/trunk check --force \
  src/dbt/kipptaf/models/assessments/intermediate/int_assessments__resolved_section_enrollments.sql \
  src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_enrollment_scoped.sql
```

Expected: no issues.

- [ ] **Step 4: Final commit** (if Cube/lint fixes):

```bash
git -C <worktree> add -u && git -C <worktree> commit -m "chore(dbt): cube/lint cleanup for enrollment-scoped assessment fact"
```

---

## Out of scope (tracked separately)

- The 39 truly-unattributable state scores →
  [#4139](https://github.com/TEAMSchools/teamster/issues/4139).
- No-homeroom residual (mostly Paterson AY2024–25) — excluded by design; monitor
  via resolver match-rate, fold into #4139.

## Open implementation decisions (resolve via `dbt show` during execution)

- **Pearson `test_date`**: earliest unit start vs. test completion — plan uses
  earliest unit start (when the kid began); confirm acceptable.
- **State subject `CASE` granularity**: NJGPA maps to ELA _and_ Math — if a
  single score row carries one discipline, map on `discipline`; if it spans
  both, the resolver may produce two subject candidates (dedup tier handles it).
  Verify NJGPA row grain in Step 1 of Task 5.
- **Resolver uniqueness test NULL-safety**: if the composite-column test
  miscounts due to branch-null columns, switch to the `format("%T", ...)`
  distinct-count singular test.
