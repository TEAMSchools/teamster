# `student_section_enrollment_key` on `fct_assessment_scores_enrollment_scoped` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a nullable `student_section_enrollment_key` FK to
`fct_assessment_scores_enrollment_scoped`, resolved to the section the student
was enrolled in on the date the assessment was given.

**Architecture:** Surface the enrollment-window dates the scaffold already
computes; resolve one section per `(student, canonical assessment, source)` in a
new, unit-tested intermediate `int_assessments__resolved_section_enrollments`
(window-containment tiebreak on
`coalesce(date_taken, canonical administration date)`); the fact LEFT JOINs it
and selects the key. Canonical-grain interim solution; atomic-grain alternative
tracked in [#4107](https://github.com/TEAMSchools/teamster/issues/4107).

**Tech Stack:** dbt (BigQuery), `dbt_utils.generate_surrogate_key`,
`dbt_utils.deduplicate`, dbt unit tests. Spec:
[docs/superpowers/specs/2026-06-03-fct-assessment-scores-section-enrollment-fk-design.md](2026-06-03-fct-assessment-scores-section-enrollment-fk-design.md).

**Working dir:** all commands assume cwd is the worktree root
`/workspaces/teamster/.worktrees/cbini/feat/claude-assessment-section-enrollment-fk`.

---

## File structure

| File                                                                                                           | Responsibility                                                     | Change                                                 |
| -------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------ |
| `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__scaffold.sql`                                | Expected-to-take grain; source of `cc_dcid` + enrollment windows   | Modify — project `cc_dateenrolled`, `cc_dateleft`      |
| `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__scaffold.yml`                     | Scaffold column docs                                               | Modify — document the two new columns                  |
| `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__resolved_section_enrollments.sql`            | One section enrollment per (student, canonical assessment, source) | **Create**                                             |
| `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__resolved_section_enrollments.yml` | Resolver grain test + unit tests                                   | **Create**                                             |
| `src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_enrollment_scoped.sql`                               | Enrollment-scoped scores fact                                      | Modify — LEFT JOIN resolver + select FK                |
| `src/dbt/kipptaf/models/marts/facts/properties/fct_assessment_scores_enrollment_scoped.yml`                    | Fact contract + tests                                              | Modify — add column, FK constraint, relationships test |

---

## Task 1: Surface enrollment-window dates on the scaffold

The scaffold's `internal_assessments` CTE already selects `ce.cc_dateenrolled`
and `ce.cc_dateleft` (K-8 and HS branches) and `deduplicate` preserves them —
they are simply not projected in the final SELECT. Project them; the three
non-enrollment UNION branches emit `cast(null as date)`.

**Files:**

- Modify:
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__scaffold.sql`
- Modify:
  `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__scaffold.yml`

- [ ] **Step 1: Project the dates in the internal (deduplicate) branch**

In the final SELECT's first branch (`from deduplicate as ia`), add the two
columns immediately after `ia.cc_source_project,`:

```sql
    ia.cc_dcid,
    ia.cc_source_project,
    ia.cc_dateenrolled,
    ia.cc_dateleft,
```

- [ ] **Step 2: Emit NULLs in the K-8 replacement branch**

In the `/* K-8 replacement curriculum */` branch, replace the
`cast(null ...) as cc_dcid` / `cc_source_project` pair with the four-line block:

```sql
    cast(null as int64) as cc_dcid,
    cast(null as string) as cc_source_project,
    cast(null as date) as cc_dateenrolled,
    cast(null as date) as cc_dateleft,
```

- [ ] **Step 3: Emit NULLs in the all-other-assessments branch**

In the `/* all other assessments */` branch, apply the identical change as
Step 2.

- [ ] **Step 4: Document the columns in the scaffold yml**

Add to the `columns:` list of `int_assessments__scaffold` (placement is not
contract-enforced for an intermediate; put them with the other `cc_` columns):

```yaml
- name: cc_dateenrolled
  data_type: date
  description: >-
    Date the student enrolled in the matched PowerSchool course section.
    Populated only for the internal-assessment branch
    (is_internal_assessment=true and is_replacement=false); null for K-8
    replacement curriculum and external-assessment rows.
  config:
    meta:
      source_column: int_assessments__course_enrollments.cc_dateenrolled
- name: cc_dateleft
  data_type: date
  description: >-
    Date the student left the matched PowerSchool course section. Populated only
    for the internal-assessment branch (is_internal_assessment=true and
    is_replacement=false); null for K-8 replacement curriculum and
    external-assessment rows.
  config:
    meta:
      source_column: int_assessments__course_enrollments.cc_dateleft
```

- [ ] **Step 5: Install deps (fresh worktree) and build the scaffold in dev**

```bash
uv run dbt deps --project-dir src/dbt/kipptaf
uv run dbt build --select int_assessments__scaffold \
  --project-dir src/dbt/kipptaf --target dev \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: build PASS; the `unique_combination_of_columns` test on
`(illuminate_student_id, assessment_id)` PASSES (unchanged).

- [ ] **Step 6: Verify the columns populate as expected**

Run (replace `zz_cbini_` with your dev schema prefix if different):

```sql
select
  countif(cc_dateenrolled is not null) as n_enrolled_set,
  countif(is_internal_assessment and not is_replacement
          and cc_dcid is not null) as n_internal_resolvable,
from `teamster-332318.zz_cbini_kipptaf_assessments.int_assessments__scaffold`
```

Expected: `n_enrolled_set` equals `n_internal_resolvable`.

- [ ] **Step 7: Commit**

```bash
git add src/dbt/kipptaf/models/assessments/intermediate/int_assessments__scaffold.sql \
        src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__scaffold.yml
git commit -m "feat(dbt): surface cc_dateenrolled/cc_dateleft on int_assessments__scaffold (#4089)"
```

---

## Task 2: Create the resolver intermediate (with a deliberately-incomplete tiebreak)

Create the model with the full CTE structure but a **recency-only** dedupe order
(`cc_dateleft desc`) — the same "latest wins" rule we rejected. Task 3's unit
test will prove it picks the #3801 phantom, then we fix the order. The
`is_anchor_in_window` column is computed now but not yet used in the ordering,
so the red→green change in Task 3 is a one-line edit to the `order_by`.

**Files:**

- Create:
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__resolved_section_enrollments.sql`
- Create:
  `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__resolved_section_enrollments.yml`

- [ ] **Step 1: Create the model SQL**

```sql
with
    candidates as (
        select
            sc.powerschool_student_number,
            sc.canonical_assessment_id,
            sc._dbt_source_project,
            sc.cc_dcid,
            sc.cc_source_project,
            sc.cc_dateenrolled,
            sc.cc_dateleft,
            sc.date_taken,

            c.administered_date as canonical_administered_date,
        from {{ ref("int_assessments__scaffold") }} as sc
        inner join
            {{ ref("int_assessments__assessments_canonical") }} as c
            on sc.canonical_assessment_id = c.canonical_assessment_id
        where
            sc.is_internal_assessment
            and not sc.is_replacement
            and sc.cc_dcid is not null
            and sc.cc_source_project is not null
    ),

    anchored as (
        select
            *,
            coalesce(
                min(date_taken) over (
                    partition by
                        powerschool_student_number,
                        canonical_assessment_id,
                        _dbt_source_project
                ),
                canonical_administered_date
            ) as anchor_date,
        from candidates
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    ranked as (
        select
            *,
            coalesce(
                anchor_date between cc_dateenrolled and cc_dateleft, false
            ) as is_anchor_in_window,
        from anchored
    ),

    resolved as (
        {{
            dbt_utils.deduplicate(
                relation="ranked",
                partition_by="powerschool_student_number, canonical_assessment_id, _dbt_source_project",
                order_by="cc_dateleft desc",
            )
        }}
    )

select
    powerschool_student_number,
    canonical_assessment_id,
    cc_dcid,

    _dbt_source_project,
    cc_source_project,

    {{ dbt_utils.generate_surrogate_key(["cc_dcid", "cc_source_project"]) }}
    as student_section_enrollment_key,
from resolved
```

- [ ] **Step 2: Create the properties yml (grain test only — unit tests added in
      Task 3)**

```yaml
models:
  - name: int_assessments__resolved_section_enrollments
    description: >-
      Resolves one PowerSchool course-section enrollment per (student, canonical
      assessment) for internal scored assessments, mirroring the scope of
      bridge_assessment_expectations_enrollment_scoped. When a student maps to
      more than one section for a canonical assessment, the section active on
      the date the test was given (coalesce of the earliest member date_taken
      and the canonical administration date) is selected; this also excludes
      cross-year phantom enrollments from the #3801 canonicalization defect.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - powerschool_student_number
              - canonical_assessment_id
              - _dbt_source_project
    columns:
      - name: powerschool_student_number
        data_type: int64
      - name: canonical_assessment_id
        data_type: int64
      - name: cc_dcid
        data_type: int64
      - name: _dbt_source_project
        data_type: string
      - name: cc_source_project
        data_type: string
      - name: student_section_enrollment_key
        data_type: string
        description: >-
          Surrogate key (cc_dcid + cc_source_project), matching
          dim_student_section_enrollments.student_section_enrollment_key.
```

- [ ] **Step 3: Confirm it compiles**

```bash
uv run dbt compile --select int_assessments__resolved_section_enrollments \
  --project-dir src/dbt/kipptaf --target dev \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: compiles with no Jinja/macro error. (Do not commit yet — the tiebreak
is intentionally wrong; Task 3 fixes and commits it.)

---

## Task 3: Unit-test the resolver (red → green) and lock the grain

**Files:**

- Modify:
  `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__resolved_section_enrollments.yml`
- Modify:
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__resolved_section_enrollments.sql`

- [ ] **Step 1: Add the phantom-exclusion unit test (the discriminating case)**

Append to the resolver's properties yml (top-level `unit_tests:` key, sibling of
`models:`):

```yaml
unit_tests:
  - name: test_resolved_section_picks_in_window_over_phantom
    description: >
      Two candidate sections for one canonical assessment (a #3801 cross-year
      case): the section whose enrollment window contains the anchor date is
      picked, not the more-recent out-of-window phantom.
    model: int_assessments__resolved_section_enrollments
    given:
      - input: ref('int_assessments__scaffold')
        rows:
          - {
              powerschool_student_number: 1,
              canonical_assessment_id: 100,
              _dbt_source_project: "kippnewark",
              cc_dcid: 111,
              cc_source_project: "kippnewark",
              cc_dateenrolled: "2017-09-01",
              cc_dateleft: "2018-06-15",
              date_taken: "2018-03-09",
              is_internal_assessment: true,
              is_replacement: false,
            }
          - {
              powerschool_student_number: 1,
              canonical_assessment_id: 100,
              _dbt_source_project: "kippnewark",
              cc_dcid: 222,
              cc_source_project: "kippnewark",
              cc_dateenrolled: "2018-08-23",
              cc_dateleft: "2019-06-29",
              date_taken: null,
              is_internal_assessment: true,
              is_replacement: false,
            }
      - input: ref('int_assessments__assessments_canonical')
        rows:
          - { canonical_assessment_id: 100, administered_date: "2018-03-04" }
    expect:
      rows:
        - {
            powerschool_student_number: 1,
            canonical_assessment_id: 100,
            cc_dcid: 111,
          }
```

- [ ] **Step 2: Run the unit test — expect RED**

```bash
uv run dbt build --select int_assessments__resolved_section_enrollments \
  --project-dir src/dbt/kipptaf --target dev \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: FAIL. The recency-only order picks `cc_dcid: 222` (later `cc_dateleft`
= the 2019 phantom); the data diff shows `cc_dcid 222→111`.

- [ ] **Step 3: Fix the tiebreak — use window-containment first**

In the model SQL, change the `dbt_utils.deduplicate` `order_by` argument from:

```sql
                order_by="cc_dateleft desc",
```

to:

```sql
                order_by="is_anchor_in_window desc, cc_dateleft desc",
```

- [ ] **Step 4: Run the unit test — expect GREEN**

```bash
uv run dbt build --select int_assessments__resolved_section_enrollments \
  --project-dir src/dbt/kipptaf --target dev \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: PASS (picks `cc_dcid: 111`, the in-window 2018 section).

- [ ] **Step 5: Add the remaining scenario unit tests**

Append these three `unit_tests` entries beneath the first:

```yaml
- name: test_resolved_section_single_candidate_always_resolves
  description: >
    With only one candidate section, it is selected even if the anchor date
    falls outside its enrollment window.
  model: int_assessments__resolved_section_enrollments
  given:
    - input: ref('int_assessments__scaffold')
      rows:
        - {
            powerschool_student_number: 2,
            canonical_assessment_id: 200,
            _dbt_source_project: "kippmiami",
            cc_dcid: 333,
            cc_source_project: "kippmiami",
            cc_dateenrolled: "2025-09-01",
            cc_dateleft: "2026-06-15",
            date_taken: null,
            is_internal_assessment: true,
            is_replacement: false,
          }
    - input: ref('int_assessments__assessments_canonical')
      rows:
        - { canonical_assessment_id: 200, administered_date: "2099-01-01" }
  expect:
    rows:
      - {
          powerschool_student_number: 2,
          canonical_assessment_id: 200,
          cc_dcid: 333,
        }

- name: test_resolved_section_none_in_window_falls_back_to_latest
  description: >
    When no candidate window contains the anchor, the most recently ended
    enrollment (latest cc_dateleft) is selected.
  model: int_assessments__resolved_section_enrollments
  given:
    - input: ref('int_assessments__scaffold')
      rows:
        - {
            powerschool_student_number: 3,
            canonical_assessment_id: 300,
            _dbt_source_project: "kippcamden",
            cc_dcid: 444,
            cc_source_project: "kippcamden",
            cc_dateenrolled: "2020-09-01",
            cc_dateleft: "2021-06-15",
            date_taken: null,
            is_internal_assessment: true,
            is_replacement: false,
          }
        - {
            powerschool_student_number: 3,
            canonical_assessment_id: 300,
            _dbt_source_project: "kippcamden",
            cc_dcid: 555,
            cc_source_project: "kippcamden",
            cc_dateenrolled: "2021-09-01",
            cc_dateleft: "2022-06-15",
            date_taken: null,
            is_internal_assessment: true,
            is_replacement: false,
          }
    - input: ref('int_assessments__assessments_canonical')
      rows:
        - { canonical_assessment_id: 300, administered_date: "2030-01-01" }
  expect:
    rows:
      - {
          powerschool_student_number: 3,
          canonical_assessment_id: 300,
          cc_dcid: 555,
        }

- name: test_resolved_section_anchor_falls_back_to_admin_date
  description: >
    With no recorded date_taken, the anchor falls back to the canonical
    administration date; the section whose window contains that date is selected
    (not the more-recent out-of-window section).
  model: int_assessments__resolved_section_enrollments
  given:
    - input: ref('int_assessments__scaffold')
      rows:
        - {
            powerschool_student_number: 4,
            canonical_assessment_id: 400,
            _dbt_source_project: "kippnewark",
            cc_dcid: 666,
            cc_source_project: "kippnewark",
            cc_dateenrolled: "2024-09-01",
            cc_dateleft: "2025-06-15",
            date_taken: null,
            is_internal_assessment: true,
            is_replacement: false,
          }
        - {
            powerschool_student_number: 4,
            canonical_assessment_id: 400,
            _dbt_source_project: "kippnewark",
            cc_dcid: 777,
            cc_source_project: "kippnewark",
            cc_dateenrolled: "2025-09-01",
            cc_dateleft: "2026-06-15",
            date_taken: null,
            is_internal_assessment: true,
            is_replacement: false,
          }
    - input: ref('int_assessments__assessments_canonical')
      rows:
        - { canonical_assessment_id: 400, administered_date: "2024-11-01" }
  expect:
    rows:
      - {
          powerschool_student_number: 4,
          canonical_assessment_id: 400,
          cc_dcid: 666,
        }
```

- [ ] **Step 6: Run all unit tests + the grain test — expect GREEN**

```bash
uv run dbt build --select int_assessments__resolved_section_enrollments \
  --project-dir src/dbt/kipptaf --target dev \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: PASS — all four unit tests and the `unique_combination_of_columns`
grain test pass.

- [ ] **Step 7: Commit**

```bash
git add src/dbt/kipptaf/models/assessments/intermediate/int_assessments__resolved_section_enrollments.sql \
        src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__resolved_section_enrollments.yml
git commit -m "feat(dbt): add int_assessments__resolved_section_enrollments resolver + unit tests (#4089)"
```

---

## Task 4: Join the resolver into the fact and add the FK column

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_enrollment_scoped.sql`
- Modify:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_assessment_scores_enrollment_scoped.yml`

- [ ] **Step 1: Add the FK column + LEFT JOIN in the internal branch**

In the `/* internal assessments */` SELECT, add the column immediately after the
`student_key` line:

```sql
    {{ dbt_utils.generate_surrogate_key(["ia.student_number"]) }} as student_key,

    sr.student_section_enrollment_key,
```

Then add the LEFT JOIN immediately after `from internal_assessments as ia`:

```sql
from internal_assessments as ia
left join
    {{ ref("int_assessments__resolved_section_enrollments") }} as sr
    on ia.student_number = sr.powerschool_student_number
    and ia.assessment_id = sr.canonical_assessment_id
    and ia._dbt_source_project = sr._dbt_source_project
```

- [ ] **Step 2: Emit NULL for the FK in the state branch**

In the `/* state assessments */` SELECT, add immediately after the `student_key`
`if(...) as student_key,` block (before `su.test_date as test_date_key,`):

```sql
    cast(null as string) as student_section_enrollment_key,
```

- [ ] **Step 3: Add the column to the fact yml**

Insert immediately after the `student_key` column block (before
`test_date_key`):

```yaml
- name: student_section_enrollment_key
  data_type: string
  description: >-
    FK to dim_student_section_enrollments. The student's section enrollment for
    the assessment's subject, resolved to the section active on the date the
    assessment was taken (falling back to the administration date). Populated
    only for internal assessments with a resolvable course-section enrollment;
    null for state assessments, replacement curriculum, ES Writing, and
    unresolved internal rows.
  constraints:
    - type: foreign_key
      to: ref('dim_student_section_enrollments')
      to_columns: [student_section_enrollment_key]
      warn_unsupported: false
  data_tests:
    - relationships:
        arguments:
          to: ref('dim_student_section_enrollments')
          field: student_section_enrollment_key
```

- [ ] **Step 4: Update the model description**

Replace the model `description` with:

```yaml
description: >-
  Enrollment-scoped assessment score fact table. One row per student x
  assessment x administration. Covers internal Illuminate assessments and state
  assessments (NJSLA, NJGPA, FAST). Scores are linked to a student (via
  student_key), an assessment administration (via
  assessment_administration_key), and — for internal assessments with a
  resolvable course-section enrollment — to the student's section enrollment
  (via student_section_enrollment_key).
```

- [ ] **Step 5: Build the fact in dev and run its tests**

```bash
uv run dbt build \
  --select int_assessments__resolved_section_enrollments fct_assessment_scores_enrollment_scoped \
  --project-dir src/dbt/kipptaf --target dev \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: build PASS. `assessment_score_key` `unique` + `not_null` PASS (no
fan-out), and the new `student_section_enrollment_key` `relationships` test
PASSES (every populated FK resolves to `dim_student_section_enrollments`).

- [ ] **Step 6: Commit**

```bash
git add src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_enrollment_scoped.sql \
        src/dbt/kipptaf/models/marts/facts/properties/fct_assessment_scores_enrollment_scoped.yml
git commit -m "feat(dbt): add student_section_enrollment_key to fct_assessment_scores_enrollment_scoped (#4089)"
```

---

## Task 5: Validate coverage and grain on real data

Tiebreak correctness is now locked by the unit tests; these queries confirm
real-data coverage and the no-fan-out invariant. Aggregate output only — no
student identifiers. Replace `zz_cbini_` with your dev prefix.

- [ ] **Step 1: Coverage — FK populates for internal-resolvable rows only**

```sql
select
  count(*) as n_total,
  countif(student_section_enrollment_key is not null) as n_populated,
from `teamster-332318.zz_cbini_kipptaf_marts.fct_assessment_scores_enrollment_scoped`
```

Expected: `n_populated > 0` and `n_populated < n_total`. Treat `n_populated = 0`
as a broken join — investigate before proceeding.

- [ ] **Step 2: Grain — no fan-out from the resolver join**

```sql
select count(*) - count(distinct assessment_score_key) as n_dupes,
from `teamster-332318.zz_cbini_kipptaf_marts.fct_assessment_scores_enrollment_scoped`
```

Expected: `n_dupes = 0`.

- [ ] **Step 3: Run the trunk linters on the changed/created files**

Run from inside the worktree:

```bash
/workspaces/teamster/.trunk/tools/trunk check --force \
  src/dbt/kipptaf/models/assessments/intermediate/int_assessments__scaffold.sql \
  src/dbt/kipptaf/models/assessments/intermediate/int_assessments__resolved_section_enrollments.sql \
  src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__resolved_section_enrollments.yml \
  src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_enrollment_scoped.sql \
  src/dbt/kipptaf/models/marts/facts/properties/fct_assessment_scores_enrollment_scoped.yml \
  src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__scaffold.yml
```

Expected: no issues. If sqlfluff ST06 reports column ordering, reorder per the
message and amend the relevant commit.

---

## Task 6: Finalize

- [ ] **Step 1: Confirm clean tree and review the diff**

```bash
git status -sb
git log --oneline origin/main..HEAD
git diff origin/main..HEAD -- src/dbt/kipptaf/models
```

Expected: spec + plan doc commits plus the three feat commits; working tree
clean; diff limited to the six files above.

- [ ] **Step 2: Hand off for PR**

Use the `superpowers:finishing-a-development-branch` flow. Verification gate:
the dev `dbt build` from Tasks 3 and 4 (PASS, incl. the four unit tests) plus
the Task 5 coverage/grain queries. PR body uses
`.github/pull_request_template.md`; reference `Closes #4089`. Note the Cube
follow-up as out of scope and gated on this column materializing, carrying the
diamond constraint from the spec (join `dim_students` via `student_key` only; do
not traverse the enrollment→student edge).

> **Pushing is not in this plan.** `git push origin main` is blocked, and CI
> fires on push — coordinate the push/PR with the user per repo conventions.

---

## Notes for the implementer

- **Hash must match the dim/bridge.** `student_section_enrollment_key` hashes
  `[cc_dcid, cc_source_project]` — `cc_source_project` is the course-enrollment
  source project, NOT the region-derived `_dbt_source_project`. A populated FK
  that fails the relationships test means the hash inputs drifted.
- **Why `dbt_utils.deduplicate`, not `qualify row_number() = 1`.** Repo
  convention (`src/dbt/CLAUDE.md`) forbids manual `qualify`/`distinct` dedupe;
  `deduplicate`'s `partition_by` IS the resolver's grain and the downstream join
  key, so the collapse cannot fan out the fact.
- **Unit-test mechanics** (`dbt:adding-dbt-unit-test`): `dict` format, only the
  columns used; date values quoted as `"YYYY-MM-DD"` strings; `null` for missing
  `date_taken`. Both `ref()` inputs must be listed. The resolver's parents
  (`int_assessments__scaffold` in dev, `int_assessments__assessments_canonical`
  via `--defer`) must exist before unit tests run — Task 1 builds the scaffold.
- **Worktree command caveats** (`src/dbt/CLAUDE.md`): always pass
  `--project-dir src/dbt/kipptaf`; `--state` must be the absolute main-repo path
  `/workspaces/teamster/src/dbt/kipptaf/target/prod` (the worktree has no
  `target/prod`).
- **Resolver name** (`int_assessments__resolved_section_enrollments`) is a
  proposal — rename consistently across the four files + the fact `ref()` if you
  prefer another.
- **Materialization:** the resolver inherits the default intermediate
  materialization (view). If the fact later hits BigQuery view-nesting or
  resource limits, set `config: materialized: table` in the resolver yml.
