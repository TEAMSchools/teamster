# `student_section_enrollment_key` on `fct_assessment_scores_enrollment_scoped` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a nullable `student_section_enrollment_key` FK to
`fct_assessment_scores_enrollment_scoped`, resolved to the section the student
was enrolled in on the date the assessment was given.

**Architecture:** Surface the enrollment-window dates the scaffold already
computes, then resolve one section per `(student, canonical assessment, source)`
in a `section_resolver` CTE inside the fact (window-containment tiebreak on
`coalesce(date_taken, canonical administration date)`), and hash it identically
to `dim_student_section_enrollments` / the enrollment bridge. Canonical-grain
interim solution; atomic-grain alternative tracked in
[#4107](https://github.com/TEAMSchools/teamster/issues/4107).

**Tech Stack:** dbt (BigQuery), `dbt_utils.generate_surrogate_key`,
`dbt_utils.deduplicate`. Spec:
[docs/superpowers/specs/2026-06-03-fct-assessment-scores-section-enrollment-fk-design.md](2026-06-03-fct-assessment-scores-section-enrollment-fk-design.md).

**Working dir:** all commands assume cwd is the worktree root
`/workspaces/teamster/.worktrees/cbini/feat/claude-assessment-section-enrollment-fk`.

---

## File structure

| File                                                                                        | Responsibility                                                   | Change                                                 |
| ------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- | ------------------------------------------------------ |
| `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__scaffold.sql`             | Expected-to-take grain; source of `cc_dcid` + enrollment windows | Modify — project `cc_dateenrolled`, `cc_dateleft`      |
| `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__scaffold.yml`  | Scaffold column docs                                             | Modify — document the two new columns                  |
| `src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_enrollment_scoped.sql`            | Enrollment-scoped scores fact                                    | Modify — add resolver CTE + FK column                  |
| `src/dbt/kipptaf/models/marts/facts/properties/fct_assessment_scores_enrollment_scoped.yml` | Fact contract + tests                                            | Modify — add column, FK constraint, relationships test |

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

In the `/* K-8 replacement curriculum */` branch, after
`cast(null as string) as cc_source_project,` add:

```sql
    cast(null as int64) as cc_dcid,
    cast(null as string) as cc_source_project,
    cast(null as date) as cc_dateenrolled,
    cast(null as date) as cc_dateleft,
```

- [ ] **Step 3: Emit NULLs in the all-other-assessments branch**

In the `/* all other assessments */` branch, apply the identical change as Step
2 (after `cast(null as string) as cc_source_project,`):

```sql
    cast(null as int64) as cc_dcid,
    cast(null as string) as cc_source_project,
    cast(null as date) as cc_dateenrolled,
    cast(null as date) as cc_dateleft,
```

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

Run:

```bash
uv run dbt deps --project-dir src/dbt/kipptaf
uv run dbt build --select int_assessments__scaffold \
  --project-dir src/dbt/kipptaf --target dev \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: build PASS; the `dbt_utils.unique_combination_of_columns` test on
`(illuminate_student_id, assessment_id)` PASSES (unchanged).

- [ ] **Step 6: Verify the columns populate as expected**

Run (BigQuery; replace `zz_cbini_` with your dev schema prefix if different):

```sql
select
  countif(cc_dateenrolled is not null) as n_enrolled_set,
  countif(is_internal_assessment and not is_replacement
          and cc_dcid is not null) as n_internal_resolvable,
from `teamster-332318.zz_cbini_kipptaf_assessments.int_assessments__scaffold`
```

Expected: `n_enrolled_set` equals `n_internal_resolvable` (dates populated for
exactly the internal-resolvable rows, NULL elsewhere).

- [ ] **Step 7: Commit**

```bash
git add src/dbt/kipptaf/models/assessments/intermediate/int_assessments__scaffold.sql \
        src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__scaffold.yml
git commit -m "feat(dbt): surface cc_dateenrolled/cc_dateleft on int_assessments__scaffold (#4089)"
```

---

## Task 2: Add the section resolver and FK to the fact

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_enrollment_scoped.sql`

- [ ] **Step 1: Add the resolver CTEs to the `with` block**

`state_union` is currently the last CTE (no trailing comma — the final `select`
follows it directly). **First add a comma after `state_union`'s closing `)`**,
then append these CTEs between it and the `/* internal assessments */` select.
The new last CTE (`section_resolver`) takes no trailing comma. Note the
`trunk-ignore` on `section_ranked` — it is referenced only via
`dbt_utils.deduplicate`, which trips sqlfluff ST03.

```sql
    -- Resolves one section enrollment per (student, canonical assessment) for
    -- internal scored assessments, mirroring the scope of
    -- bridge_assessment_expectations_enrollment_scoped. When a student maps to
    -- more than one section for the same canonical assessment, pick the section
    -- active on the date the test was given (coalesce of the earliest member
    -- date_taken and the canonical administration date). Window-containment also
    -- drops cross-year phantom enrollments from the #3801 canonicalization
    -- defect, since their windows do not contain the real anchor date.
    section_candidates as (
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

    section_anchored as (
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
        from section_candidates
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    section_ranked as (
        select
            *,
            coalesce(
                anchor_date between cc_dateenrolled and cc_dateleft, false
            ) as is_anchor_in_window,
        from section_anchored
    ),

    section_resolver as (
        {{
            dbt_utils.deduplicate(
                relation="section_ranked",
                partition_by="powerschool_student_number, canonical_assessment_id, _dbt_source_project",
                order_by="is_anchor_in_window desc, cc_dateleft desc",
            )
        }}
    )
```

- [ ] **Step 2: Join the resolver and emit the FK in the internal branch**

In the `/* internal assessments */` SELECT, add the FK column immediately after
the `student_key` column:

```sql
    {{ dbt_utils.generate_surrogate_key(["ia.student_number"]) }} as student_key,

    if(
        sr.cc_dcid is not null,
        {{ dbt_utils.generate_surrogate_key(["sr.cc_dcid", "sr.cc_source_project"]) }},
        cast(null as string)
    ) as student_section_enrollment_key,
```

Then add the LEFT JOIN immediately after `from internal_assessments as ia`:

```sql
from internal_assessments as ia
left join
    section_resolver as sr
    on ia.student_number = sr.powerschool_student_number
    and ia.assessment_id = sr.canonical_assessment_id
    and ia._dbt_source_project = sr._dbt_source_project
```

- [ ] **Step 3: Emit NULL for the FK in the state branch**

In the `/* state assessments */` SELECT, add immediately after the `student_key`
`if(...) as student_key,` block (before `su.test_date as test_date_key,`):

```sql
    cast(null as string) as student_section_enrollment_key,
```

- [ ] **Step 4: Compile to verify SQL is valid**

Run:

```bash
uv run dbt compile --select fct_assessment_scores_enrollment_scoped \
  --project-dir src/dbt/kipptaf --target dev \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: compiles with no Jinja/`ref()`/macro error (confirms the
`dbt_utils.deduplicate` call and the new CTEs render). Column existence is NOT
checked at compile — BigQuery validates `sr.*` and the new scaffold columns at
`dbt build` in Task 3, Step 3.

---

## Task 3: Add the column to the fact contract and tests

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_assessment_scores_enrollment_scoped.yml`

- [ ] **Step 1: Add the column entry with FK constraint and relationships test**

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

- [ ] **Step 2: Update the model description**

Replace the model `description` with one that names the new FK:

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

- [ ] **Step 3: Build the fact in dev and run its tests**

Run:

```bash
uv run dbt build --select int_assessments__scaffold fct_assessment_scores_enrollment_scoped \
  --project-dir src/dbt/kipptaf --target dev \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: build PASS. The `assessment_score_key` `unique` + `not_null` tests
PASS (no fan-out from the resolver join), and the new
`student_section_enrollment_key` `relationships` test PASSES (every populated FK
resolves to `dim_student_section_enrollments`).

- [ ] **Step 4: Commit**

```bash
git add src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_enrollment_scoped.sql \
        src/dbt/kipptaf/models/marts/facts/properties/fct_assessment_scores_enrollment_scoped.yml
git commit -m "feat(dbt): add student_section_enrollment_key to fct_assessment_scores_enrollment_scoped (#4089)"
```

---

## Task 4: Validate behavior and coverage

All queries are aggregate / invariant — no student identifiers in output. Run
against your dev schema (replace `zz_cbini_` if your prefix differs).

- [ ] **Step 1: Coverage — the FK populates for internal-resolvable rows only**

```sql
select
  count(*) as n_total,
  countif(student_section_enrollment_key is not null) as n_populated,
from `teamster-332318.zz_cbini_kipptaf_marts.fct_assessment_scores_enrollment_scoped`
```

Expected: `n_populated > 0` and `n_populated < n_total` (state/replacement rows
remain NULL). Treat `n_populated = 0` as a broken join — investigate before
proceeding.

- [ ] **Step 2: Grain — no fan-out from the resolver join**

```sql
select count(*) - count(distinct assessment_score_key) as n_dupes,
from `teamster-332318.zz_cbini_kipptaf_marts.fct_assessment_scores_enrollment_scoped`
```

Expected: `n_dupes = 0`.

- [ ] **Step 3: Tiebreak correctness — picked section is window-valid when one
      exists**

Replicate the resolver over the dev scaffold and confirm that whenever a
candidate whose window contains the anchor exists, the picked candidate is that
one (i.e. #3801 cross-year phantoms are never picked over a real in-window
section):

```sql
with cands as (
  select
    powerschool_student_number, canonical_assessment_id, _dbt_source_project,
    cc_dateenrolled, cc_dateleft, date_taken,
    c.administered_date as canonical_administered_date,
  from `teamster-332318.zz_cbini_kipptaf_assessments.int_assessments__scaffold` as sc
  inner join `teamster-332318.kipptaf_assessments.int_assessments__assessments_canonical` as c
    using (canonical_assessment_id)
  where sc.is_internal_assessment and not sc.is_replacement
    and sc.cc_dcid is not null and sc.cc_source_project is not null
),
anchored as (
  select *,
    coalesce(min(date_taken) over (
      partition by powerschool_student_number, canonical_assessment_id, _dbt_source_project
    ), canonical_administered_date) as anchor_date,
  from cands
),
ranked as (
  select *,
    coalesce(anchor_date between cc_dateenrolled and cc_dateleft, false) as in_window,
    row_number() over (
      partition by powerschool_student_number, canonical_assessment_id, _dbt_source_project
      order by coalesce(anchor_date between cc_dateenrolled and cc_dateleft, false) desc,
               cc_dateleft desc
    ) as rn,
    max(cast(coalesce(anchor_date between cc_dateenrolled and cc_dateleft, false) as int64)) over (
      partition by powerschool_student_number, canonical_assessment_id, _dbt_source_project
    ) as any_in_window,
  from anchored
)
select countif(rn = 1 and any_in_window = 1 and not in_window) as n_bad_picks,
from ranked
```

Expected: `n_bad_picks = 0` (whenever an in-window section exists, it is the one
picked).

- [ ] **Step 4: Run the trunk linters on the changed files**

Run from inside the worktree:

```bash
/workspaces/teamster/.trunk/tools/trunk check --force \
  src/dbt/kipptaf/models/assessments/intermediate/int_assessments__scaffold.sql \
  src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_enrollment_scoped.sql \
  src/dbt/kipptaf/models/marts/facts/properties/fct_assessment_scores_enrollment_scoped.yml \
  src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__scaffold.yml
```

Expected: no issues. If sqlfluff ST06 reports column-ordering in either SQL
file, reorder per the message and re-run; amend the relevant commit.

---

## Task 5: Finalize

- [ ] **Step 1: Confirm clean tree and review the diff**

```bash
git status -sb
git log --oneline origin/main..HEAD
git diff origin/main..HEAD -- src/dbt/kipptaf/models
```

Expected: three commits (spec already committed earlier on this branch, plus the
two feat commits), working tree clean, diff limited to the four files above.

- [ ] **Step 2: Hand off for PR**

Use the `superpowers:finishing-a-development-branch` flow. The verification gate
is the dev `dbt build` from Task 3 (PASS) plus the Task 4 validation queries. PR
body uses `.github/pull_request_template.md`; reference `Closes #4089`. The Cube
follow-up (cube `sql:` SELECT, bridge join fix, section/teacher dims) is out of
scope and gated on this column materializing — note it in the PR as a follow-up,
carrying the diamond constraint from the spec (join `dim_students` via
`student_key` only; do not traverse the enrollment→student edge).

> **Pushing is not in this plan.** `git push origin main` is blocked, and CI
> fires on push — coordinate the push/PR with the user per repo conventions.

---

## Notes for the implementer

- **Hash must match the dim/bridge.** `student_section_enrollment_key` hashes
  `[cc_dcid, cc_source_project]` — `cc_source_project` is the course-enrollment
  source project, NOT the region-derived `_dbt_source_project`. The enrollment
  bridge uses the same composition, so a populated FK that fails the
  relationships test means the hash inputs drifted — recheck Step 2 of Task 2.
- **Why `dbt_utils.deduplicate`, not `qualify row_number() = 1`.** Repo
  convention (`src/dbt/CLAUDE.md`) forbids manual `qualify`/`distinct` dedupe;
  `deduplicate`'s `partition_by` matches the downstream join key so the collapse
  cannot fan out the fact.
- **Worktree command caveats** (`src/dbt/CLAUDE.md`): always pass
  `--project-dir src/dbt/kipptaf`; `--state` must be the absolute main-repo path
  `/workspaces/teamster/src/dbt/kipptaf/target/prod` (the worktree has no
  `target/prod`).
