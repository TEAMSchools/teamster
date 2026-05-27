# #3780 DISTINCT Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `SELECT DISTINCT` / `GROUP BY` collapses in 5 mart models with
correct constructs (annotated DISTINCT for pure projection, redirects to
existing entity-grain models for surveys), and split NJSLA/PARCC/FAST/FSA/EOC
into distinct lineages in `dim_assessments` + `dim_assessment_administrations`.

**Architecture:** Per
`docs/superpowers/specs/2026-05-24-distinct-cleanup-3780-design.md`. No new
intermediates. Assessments side switches from `int_pearson__all_assessments` /
`int_fldoe__all_assessments` (legacy denormalized) to 8 per-staging-table CTEs
each carrying a literal `assessment_type` lineage. Surveys side redirects to
existing entity-grain models (`int_google_forms__form__items`,
`stg_alchemer__survey_question`, `stg_alchemer__survey`,
`stg_google_forms__form`).

**Tech Stack:** dbt 1.11, BigQuery, sqlfluff (BigQuery dialect), trunk-fmt
pre-commit.

**Working directory:**
`/workspaces/teamster/.worktrees/cbini-refactor-claude-distinct-cleanup-3780`.
Branch `cbini/refactor/claude-distinct-cleanup-3780` is linked to issue #3780.

**Verification command (used in every task):**

```bash
VIRTUAL_ENV= uv \
  --directory /workspaces/teamster/.worktrees/cbini-refactor-claude-distinct-cleanup-3780 \
  run dbt build \
  --project-dir src/dbt/kipptaf \
  --select <model>+ \
  --defer --state src/dbt/kipptaf/target/prod
```

---

## Phase 0: Pre-merge BQ shape audit (no commit)

### Task 0.1: Run surveys-side BQ shape audits

**Files:** none (BQ queries only)

- [ ] **Step 1: Run query A (Google Forms questions redirect)** via
      `mcp__bigquery__execute_sql`:

```sql
with
  current as (
    select distinct form_id, item_abbreviation, item_title, question_kind
    from `teamster-332318.kipptaf_google_forms.int_google_forms__form_responses`
    where item_abbreviation is not null and item_title is not null
  ),
  target as (
    select form_id, item_abbreviation, item_title, question_kind
    from `teamster-332318.kipptaf_google_forms.int_google_forms__form__items`
    where item_abbreviation is not null and item_title is not null
  )
select
  (select count(*) from current) as n_current,
  (select count(*) from target) as n_target,
  (select count(*) from current except distinct select * from target) as n_current_only,
  (select count(*) from target except distinct select * from current) as n_target_only,
```

Save the 4-tuple to a scratch note for the PR body.

- [ ] **Step 2: Run query B (Alchemer questions)** — same shape, sources from
      spec section "Phase 0 → B".

- [ ] **Step 3: Run query C (Google Forms surveys)** — spec section "Phase 0 →
      C".

- [ ] **Step 4: Run query D (Alchemer surveys)**. First resolve `<title_col>`:

```sql
select column_name
from `teamster-332318.kipptaf_alchemer.INFORMATION_SCHEMA.COLUMNS`
where table_name = 'stg_alchemer__survey'
  and lower(column_name) like '%title%'
```

Then substitute in spec query D and run.

- [ ] **Step 5: Run query E (Google Forms bridge pairs)** — spec section "Phase
      0 → E".

- [ ] **Step 6: Run query F (Alchemer bridge pairs)** — spec section "Phase 0 →
      F".

- [ ] **Step 7: Run query G (Manager-pairs redirect equivalence)**:

```sql
with
  current as (
    select distinct survey_id, question_shortname
    from `teamster-332318.kipptaf_surveys.int_surveys__manager_survey_details`
    where survey_id = 'historic_alchemer_Manager_survey'
      and question_shortname is not null
  ),
  target as (
    select
      'historic_alchemer_Manager_survey' as survey_id,
      item_abbreviation as question_shortname,
    from `teamster-332318.kipptaf_google_forms.int_google_forms__form__items`
    where form_id = '1cvp9RnYxbn-WGLXsYSupbEl2KhVhWKcOFbHR2CgUBH0'
      and item_abbreviation is not null
  )
select
  (select count(*) from current) as n_current,
  (select count(*) from target) as n_target,
  (select count(*) from current except distinct select * from target) as n_current_only,
  (select count(*) from target except distinct select * from current) as n_target_only,
```

- [ ] **Step 8: Apply decision rules.** For queries A–F, classify each per spec
      "Phase-0 decision rules". For query G, **`n_current_only` must be 0** —
      otherwise STOP and escalate manager_pairs to a new intermediate before
      Task 2.3.

- [ ] **Step 9: Append all 7 results + classifications to
      `.claude/scratch/phase0-results.md`** for the PR body. Format each as:

```text
Query A (gforms questions): n_current=X, n_target=Y, n_current_only=A, n_target_only=B — verdict: <safe / escalate>
```

### Task 0.2: Compute expected assessments row-count deltas

**Files:** none (BQ queries only)

- [ ] **Step 1: Compute `dim_assessments` NJ delta**:

```sql
select
  (
    select count(distinct (testcode, src)) from (
      select 'parcc' as src, testcode from `teamster-332318.kipptaf_pearson.stg_pearson__parcc` where testscalescore is not null
      union all select 'njsla', testcode from `teamster-332318.kipptaf_pearson.stg_pearson__njsla` where testscalescore is not null
      union all select 'njsla_science', testcode from `teamster-332318.kipptaf_pearson.stg_pearson__njsla_science` where testscalescore is not null
      union all select 'njgpa', testcode from `teamster-332318.kipptaf_pearson.stg_pearson__njgpa` where testscalescore is not null
    )
  ) - (
    select count(distinct testcode)
    from `teamster-332318.kipptaf_pearson.int_pearson__all_assessments`
    where testscalescore is not null
  ) as nj_added_rows
```

- [ ] **Step 2: Compute `dim_assessments` FL delta**:

```sql
select
  (
    select count(distinct (test_code, src)) from (
      select 'fast' as src, test_code from `teamster-332318.kippmiami_fldoe.stg_fldoe__fast` where scale_score is not null
      union all select 'fsa', test_code from `teamster-332318.kippmiami_fldoe.stg_fldoe__fsa` where scale_score is not null
      union all select 'eoc', test_code from `teamster-332318.kippmiami_fldoe.stg_fldoe__eoc` where scale_score is not null
      union all select 'science', test_code from `teamster-332318.kippmiami_fldoe.stg_fldoe__science` where scale_score is not null
    )
  ) - (
    select count(distinct test_code)
    from `teamster-332318.kipptaf_fldoe.int_fldoe__all_assessments`
    where scale_score is not null
  ) as fl_added_rows
```

- [ ] **Step 3: Compute `dim_assessment_administrations` deltas** with the
      analogous query but including the admin partition columns
      (`administered_date is null` on state branches, `academic_year`, `region`,
      `administration_period`). Use:

```sql
with current as (
  select count(distinct format('%T|%T|%T|%T', module_code, academic_year, region, administration_period)) as n
  from (
    select
      case testcode when 'SC05' then 'SCI05' when 'SC08' then 'SCI08' when 'SC11' then 'SCI11' else testcode end as module_code,
      academic_year,
      initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_')) as region,
      if(period = 'FallBlock', 'Fall', period) as administration_period,
    from `teamster-332318.kipptaf_pearson.int_pearson__all_assessments`
    where testscalescore is not null
  )
),
new_rows as (
  select count(distinct format('%T|%T|%T|%T|%T', module_code, src, academic_year, region, administration_period)) as n
  from (
    select 'parcc' as src,
      case testcode when 'SC05' then 'SCI05' when 'SC08' then 'SCI08' when 'SC11' then 'SCI11' else testcode end as module_code,
      academic_year,
      initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_')) as region,
      if(period = 'FallBlock', 'Fall', period) as administration_period,
    from `teamster-332318.kipptaf_pearson.stg_pearson__parcc` where testscalescore is not null
    union all
    -- repeat for njsla, njsla_science, njgpa
    select 'njsla',
      case testcode when 'SC05' then 'SCI05' when 'SC08' then 'SCI08' when 'SC11' then 'SCI11' else testcode end,
      academic_year,
      initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_')),
      if(period = 'FallBlock', 'Fall', period),
    from `teamster-332318.kipptaf_pearson.stg_pearson__njsla` where testscalescore is not null
    union all
    select 'njsla_science',
      case testcode when 'SC05' then 'SCI05' when 'SC08' then 'SCI08' when 'SC11' then 'SCI11' else testcode end,
      academic_year,
      initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_')),
      if(period = 'FallBlock', 'Fall', period),
    from `teamster-332318.kipptaf_pearson.stg_pearson__njsla_science` where testscalescore is not null
    union all
    select 'njgpa',
      case testcode when 'SC05' then 'SCI05' when 'SC08' then 'SCI08' when 'SC11' then 'SCI11' else testcode end,
      academic_year,
      initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_')),
      if(period = 'FallBlock', 'Fall', period),
    from `teamster-332318.kipptaf_pearson.stg_pearson__njgpa` where testscalescore is not null
  )
)
select (select n from new_rows) - (select n from current) as nj_admin_added_rows
```

Repeat the analogous query for FL (using FLDOE staging tables +
`administration_window` for `administration_period`, and no SC code remapping).

- [ ] **Step 4: Append all 4 expected deltas to
      `.claude/scratch/phase0-results.md`**:

```text
dim_assessments expected delta: NJ +X, FL +Y, total +Z
dim_assessment_administrations expected delta: NJ +A, FL +B, total +C
```

### Task 0.3: Grep cube for state_nj / state_fl literals

**Files:** none (read-only grep)

- [ ] **Step 1: Search cube models for affected literals:**

```bash
grep -rnE "'state_nj'|'state_fl'|state_nj[^_a-z]|state_fl[^_a-z]" /workspaces/teamster/.worktrees/cbini-refactor-claude-distinct-cleanup-3780/src/cube/model/
```

- [ ] **Step 2: Append results to `.claude/scratch/phase0-results.md`**:

```text
Cube literal matches: <none / list of file:line>
```

If any matches: plan Task 3 to apply `LIKE 'state_nj_%'` swaps to each. If no
matches: Task 3 will be skipped.

---

## Commit 1: Assessments mart rewrite

### Task 1.1: Rewrite `dim_assessments` state CTEs

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_assessments.sql:1-216`
  (replace state_nj + state_fl CTEs with 8 per-staging-table CTEs; remove stale
  illuminate comment; annotate remaining DISTINCTs)

- [ ] **Step 1: Read the current file** to confirm line numbers haven't drifted:

```bash
sed -n '1,40p' /workspaces/teamster/.worktrees/cbini-refactor-claude-distinct-cleanup-3780/src/dbt/kipptaf/models/marts/dimensions/dim_assessments.sql
```

- [ ] **Step 2: Remove the stale comment block above `illuminate_assessments`
      CTE (lines 1-11 of the with-block).** The CTE has no DISTINCT; the comment
      misleads. Replace the entire comment block (lines starting from
      `-- DISTINCT projects from response grain (one row per student) to`
      through `-- via this dim's assessment_key.`) with:

```sql
-- Member-grain: one row per actual Illuminate assessment_id. Bridge
-- table `bridge_assessment_administration_members` maps each
-- canonical-grain `dim_assessment_administrations` row to its member(s)
-- via this dim's `assessment_key`.
```

The "DISTINCT projects..." prose goes; the bridge-relationship prose stays.

- [ ] **Step 3: Replace the existing `state_nj` CTE (lines 41-79) with 4 CTEs,
      one per Pearson staging table.** Canonical template (use for PARCC; adapt
      the literal and ref for the other 3):

```sql
    -- projection IS the operation, not deduplication
    state_nj_parcc as (
        select distinct
            cast(null as int64) as source_assessment_id,
            cast(null as string) as module_type,

            'state_nj_parcc' as assessment_type,
            false as is_internal_assessment,
            'enrollment' as assessment_scope,

            cast(null as string) as combined_academic_subject,
            cast(null as string) as aligned_academic_subject,
            cast(null as string) as credit_category,
            cast(null as string) as test_type,

            'PARCC' as title,

            discipline as scope,
            test_grade as grade_level,

            if(
                `subject` = 'English Language Arts/Literacy',
                'English Language Arts',
                `subject`
            ) as subject_area,

            case
                testcode
                when 'SC05'
                then 'SCI05'
                when 'SC08'
                then 'SCI08'
                when 'SC11'
                then 'SCI11'
                else testcode
            end as module_code,
        from {{ ref("stg_pearson__parcc") }}
        where testscalescore is not null
    ),
```

Then duplicate three more times, substituting:

| CTE name                 | `assessment_type` literal  | `title` literal   | `ref()`                             |
| ------------------------ | -------------------------- | ----------------- | ----------------------------------- |
| `state_nj_njsla`         | `'state_nj_njsla'`         | `'NJSLA'`         | `ref("stg_pearson__njsla")`         |
| `state_nj_njsla_science` | `'state_nj_njsla_science'` | `'NJSLA Science'` | `ref("stg_pearson__njsla_science")` |
| `state_nj_njgpa`         | `'state_nj_njgpa'`         | `'NJGPA'`         | `ref("stg_pearson__njgpa")`         |

Notes:

- `case testcode when 'SC05' then 'SCI05' ...` stays in every CTE; it's a no-op
  for tables that don't carry SC-prefixed codes.
- `title` is now a constant per CTE — the literal assessment_name for that
  program.

- [ ] **Step 4: Replace the existing `state_fl` CTE (lines 81-108) with 4 CTEs,
      one per FLDOE staging table.** Canonical template:

```sql
    -- projection IS the operation, not deduplication
    state_fl_fast as (
        select distinct
            cast(null as int64) as source_assessment_id,
            cast(null as string) as module_type,

            'state_fl_fast' as assessment_type,
            false as is_internal_assessment,
            'enrollment' as assessment_scope,

            cast(null as string) as combined_academic_subject,
            cast(null as string) as aligned_academic_subject,
            cast(null as string) as credit_category,
            cast(null as string) as test_type,

            'FAST' as title,

            assessment_subject as subject_area,
            discipline as scope,
            test_code as module_code,

            cast(assessment_grade as int) as grade_level,
        from {{ ref("stg_fldoe__fast") }}
        where scale_score is not null
    ),
```

Duplicate three more times for `state_fl_fsa` / `state_fl_eoc` /
`state_fl_science`:

| CTE name           | `assessment_type`    | `title`     | `ref()`                     |
| ------------------ | -------------------- | ----------- | --------------------------- |
| `state_fl_fsa`     | `'state_fl_fsa'`     | `'FSA'`     | `ref("stg_fldoe__fsa")`     |
| `state_fl_eoc`     | `'state_fl_eoc'`     | `'EOC'`     | `ref("stg_fldoe__eoc")`     |
| `state_fl_science` | `'state_fl_science'` | `'Science'` | `ref("stg_fldoe__science")` |

- [ ] **Step 5: Annotate `college_assessments` CTE.** Replace its existing
      leading comment block:

```sql
    -- DISTINCT projects from response grain to definition grain (see
    -- illuminate_assessments comment above).
```

with:

```sql
    -- projection IS the operation, not deduplication
```

- [ ] **Step 6: Annotate `practice_assessments` CTE.** Its current "One row per
      (scope, subject_area) — matching Official college's…" comment is
      informative and should stay; ADD the projection annotation as a separate
      line directly above the `select distinct`:

```sql
    -- projection IS the operation, not deduplication
    select distinct
```

- [ ] **Step 7: Annotate `ap_assessments` CTE.** Replace its existing comment
      block (also "DISTINCT projects from response grain to definition grain")
      with:

```sql
    -- projection IS the operation, not deduplication
```

- [ ] **Step 8: Update the final UNION ALL block (around line 198).** Replace
      the 6-branch union with a 12-branch union covering:
      `illuminate_assessments`, `state_nj_parcc`, `state_nj_njsla`,
      `state_nj_njsla_science`, `state_nj_njgpa`, `state_fl_fast`,
      `state_fl_fsa`, `state_fl_eoc`, `state_fl_science`, `college_assessments`,
      `practice_assessments`, `ap_assessments`. Each branch is
      `select {{ union_cols }}, from <cte_name>` followed by `union all` (except
      the last).

- [ ] **Step 9: Leave the downstream `dbt_utils.deduplicate` (`all_assessments`)
      untouched.** Its partition_by
      `assessment_type, source_assessment_id, module_code, test_type` and
      order_by `title` continue to deduplicate any cross-branch collisions
      correctly under the new type-string scheme.

- [ ] **Step 10: Build dim_assessments and verify row count:**

```bash
VIRTUAL_ENV= uv \
  --directory /workspaces/teamster/.worktrees/cbini-refactor-claude-distinct-cleanup-3780 \
  run dbt build \
  --project-dir src/dbt/kipptaf \
  --select dim_assessments \
  --defer --state src/dbt/kipptaf/target/prod
```

Expected: build succeeds, all tests pass. If unique test on `assessment_key`
fails, the new `assessment_type` literals are not splitting the hashes as
expected — recheck Step 3 / Step 4 literals.

- [ ] **Step 11: Verify row-count delta matches Phase 0 expectation.** Find the
      PR-branch schema from the build output (printed in
      `Create profile from connection BigQuery (override schema to '...')` step,
      or by querying `INFORMATION_SCHEMA.SCHEMATA`). Then:

```sql
select
  (select count(*) from `teamster-332318.<pr_schema>.dim_assessments`) as n_pr,
  (select count(*) from `teamster-332318.kipptaf.dim_assessments`) as n_prod,
```

`n_pr - n_prod` must equal the sum of `nj_added_rows + fl_added_rows` from Phase
0 Task 0.2. If not, recheck `assessment_type` composition.

- [ ] **Step 12: Verify lineage taxonomy:**

```sql
select assessment_type, count(*) as n
from `teamster-332318.<pr_schema>.dim_assessments`
where assessment_type like 'state_%'
group by 1
order by 1
```

Must return exactly these 8 values (and nothing else): `state_fl_eoc`,
`state_fl_fast`, `state_fl_fsa`, `state_fl_science`, `state_nj_njgpa`,
`state_nj_njsla`, `state_nj_njsla_science`, `state_nj_parcc`.

### Task 1.2: Rewrite `dim_assessment_administrations` state CTEs

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/dim_assessment_administrations.sql:51-117`
  (replace state_nj_administrations + state_fl_administrations; annotate other
  DISTINCTs)

- [ ] **Step 1: Replace `state_nj_administrations` (lines 51-91) with 4 CTEs.**
      Canonical template (PARCC):

```sql
    -- projection IS the operation, not deduplication
    -- State NJ PARCC: one administration per (testcode, period, academic_year, region).
    state_nj_parcc_administrations as (
        select distinct
            'state_nj_parcc' as assessment_type,
            'PARCC' as title,

            if(
                `subject` = 'English Language Arts/Literacy',
                'English Language Arts',
                `subject`
            ) as subject_area,

            discipline as scope,

            case
                testcode
                when 'SC05'
                then 'SCI05'
                when 'SC08'
                then 'SCI08'
                when 'SC11'
                then 'SCI11'
                else testcode
            end as module_code,

            test_grade as grade_level,

            cast(null as date) as administered_date,
            academic_year,

            initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_')) as region,

            cast(null as int64) as source_assessment_id,

            if(`period` = 'FallBlock', 'Fall', `period`) as administration_period,

            cast(null as string) as test_type,
        from {{ ref("stg_pearson__parcc") }}
        where testscalescore is not null
    ),
```

Duplicate for `state_nj_njsla` / `state_nj_njsla_science` / `state_nj_njgpa`
with the same substitution table from Task 1.1 Step 3 (assessment_type + title +
ref() change; everything else identical).

**Important:** `assessment_type` literal here is `'state_nj_parcc'`
(lineage-split), NOT the pre-existing `'state'` literal in the current file.
This change aligns the admin's hash with the dim's hash composition for the same
assessment.

- [ ] **Step 2: Replace `state_fl_administrations` (lines 95-117) with 4 CTEs.**
      Canonical template (FAST):

```sql
    -- projection IS the operation, not deduplication
    -- State FL FAST: one administration per (test_code, administration_window, academic_year, region).
    state_fl_fast_administrations as (
        select distinct
            'state_fl_fast' as assessment_type,
            'FAST' as title,
            assessment_subject as subject_area,
            discipline as scope,
            test_code as module_code,

            cast(assessment_grade as int) as grade_level,

            cast(null as date) as administered_date,
            academic_year,

            initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_')) as region,

            cast(null as int64) as source_assessment_id,

            administration_window as administration_period,

            cast(null as string) as test_type,
        from {{ ref("stg_fldoe__fast") }}
        where scale_score is not null
    ),
```

Duplicate for `state_fl_fsa` / `state_fl_eoc` / `state_fl_science` with the
substitution table from Task 1.1 Step 4.

- [ ] **Step 3: Annotate the surviving DISTINCT CTEs.** For each of
      `college_administrations`, `ap_administrations` (lines ~122 and ~174),
      prepend the standard annotation directly above its `select distinct`:

```sql
    -- projection IS the operation, not deduplication
```

`practice_administrations` uses `select` + `group by` for
`any_value(subject_area)` resolution — that's canonical-attribute resolution,
not pure projection. Leave it as-is; do NOT add the annotation. (The `any_value`
call qualifies as `dbt_utils.deduplicate`-equivalent semantics; the existing
block comment explains the choice.)

- [ ] **Step 4: Update the final UNION ALL block.** Replace the 6-branch union
      with a 14-branch union: `illuminate_administrations` + 4 NJ + 4 FL +
      `college_administrations` + `practice_administrations` +
      `ap_administrations`.

- [ ] **Step 5: Build and verify:**

```bash
VIRTUAL_ENV= uv \
  --directory /workspaces/teamster/.worktrees/cbini-refactor-claude-distinct-cleanup-3780 \
  run dbt build \
  --project-dir src/dbt/kipptaf \
  --select dim_assessment_administrations \
  --defer --state src/dbt/kipptaf/target/prod
```

Expected: build succeeds, unique test on `assessment_administration_key` passes.

- [ ] **Step 6: Verify row-count delta** matches the expected admin delta from
      Phase 0 Task 0.2 Step 3.

- [ ] **Step 7: Verify lineage taxonomy** on the admin dim:

```sql
select assessment_type, count(*) as n
from `teamster-332318.<pr_schema>.dim_assessment_administrations`
where assessment_type like 'state_%'
group by 1
order by 1
```

Must return the same 8 lineage values as Task 1.1 Step 12.

### Task 1.3: Commit assessments changes

- [ ] **Step 1: Stage modified files:**

```bash
cd /workspaces/teamster/.worktrees/cbini-refactor-claude-distinct-cleanup-3780
git add src/dbt/kipptaf/models/marts/dimensions/dim_assessments.sql \
        src/dbt/kipptaf/models/marts/dimensions/dim_assessment_administrations.sql
```

- [ ] **Step 2: Commit** (use HEREDOC to preserve formatting):

```bash
git commit -m "$(cat <<'EOF'
refactor(dbt): split state assessment lineages in dim_assessments + admin

Replaces state_nj / state_fl CTEs in dim_assessments and
dim_assessment_administrations with 8 per-staging-table CTEs each carrying
a literal assessment_type that encodes program lineage (parcc, njsla,
njsla_science, njgpa, fast, fsa, eoc, science). Drops the
int_pearson__all_assessments and int_fldoe__all_assessments mart
dependencies in favor of staging-direct reads.

Annotates surviving pure-projection DISTINCTs per the new
src/dbt/CLAUDE.md rule clarification. Removes stale "DISTINCT projects..."
comment block above dim_assessments.illuminate_assessments (the CTE has
no DISTINCT).

Refs #3780

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Commit 2: Surveys redirects

### Task 2.1: Rewrite `dim_survey_questions.sql`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/dim_survey_questions.sql:1-75`
  (redirect gforms + alchemer; drop manager_questions)

- [ ] **Step 1: Replace `google_forms_questions` CTE (lines 2-10).** Current:

```sql
    google_forms_questions as (
        -- DISTINCT projects from response grain to question grain.
        select distinct
            fr.item_abbreviation as question_shortname,
            fr.item_title as question_text,
            fr.question_kind as question_type,
        from {{ ref("int_google_forms__form_responses") }} as fr
        where fr.item_abbreviation is not null and fr.item_title is not null
    ),
```

Replace with:

```sql
    google_forms_questions as (
        select
            item_abbreviation as question_shortname,
            item_title as question_text,
            question_kind as question_type,
        from {{ ref("int_google_forms__form__items") }}
        where item_abbreviation is not null and item_title is not null
    ),
```

- [ ] **Step 2: Replace `alchemer_questions` CTE (lines 21-31).** Current:

```sql
    alchemer_questions as (
        -- DISTINCT projects from response grain to question grain.
        -- Sources Alchemer + Google Forms staff/student survey questions that
        -- feed fct_survey_responses.general_responses.
        select distinct
            sr.question_shortname,
            sr.question_title as question_text,
            cast(null as string) as question_type,
        from {{ ref("int_surveys__survey_responses") }} as sr
        where sr.question_shortname is not null
    ),
```

Replace with:

```sql
    alchemer_questions as (
        select
            shortname as question_shortname,
            title_english as question_text,
            cast(null as string) as question_type,
        from {{ ref("stg_alchemer__survey_question") }}
        where shortname is not null
    ),
```

- [ ] **Step 3: Delete `manager_questions` CTE (lines 33-41) AND its UNION ALL
      branch (in `all_questions` CTE, lines ~52-55).** After deletion,
      `all_questions` must be:

```sql
    -- trunk-ignore(sqlfluff/ST03): referenced by string in dbt_utils.deduplicate
    all_questions as (
        select *,
        from google_forms_questions
        union all
        select *,
        from scd_questions
        union all
        select *,
        from alchemer_questions
    ),
```

- [ ] **Step 4: Leave `scd_questions` CTE and the downstream
      `dbt_utils.deduplicate` untouched.**

- [ ] **Step 5: Build and verify:**

```bash
VIRTUAL_ENV= uv \
  --directory /workspaces/teamster/.worktrees/cbini-refactor-claude-distinct-cleanup-3780 \
  run dbt build \
  --project-dir src/dbt/kipptaf \
  --select dim_survey_questions \
  --defer --state src/dbt/kipptaf/target/prod
```

Expected: build succeeds; unique on `survey_question_key` passes.

- [ ] **Step 6: Verify delta** matches sum of Phase 0 queries A and B
      (`n_target - n_current` per query, summed, signed). Document the actual
      delta vs expected in `.claude/scratch/phase0-results.md`.

### Task 2.2: Rewrite `dim_surveys.sql`

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_surveys.sql:1-19`
  (redirect gforms + alchemer)

- [ ] **Step 1: Replace `google_forms_surveys` CTE (lines 2-8).** Current:

```sql
    google_forms_surveys as (
        -- DISTINCT projects from response grain to survey grain.
        select distinct
            form_id as survey_id, info_title as survey_name, 'Google Forms' as platform,
        from {{ ref("int_google_forms__form_responses") }}
        where form_id is not null
    ),
```

Replace with:

```sql
    google_forms_surveys as (
        select
            form_id as survey_id, info_title as survey_name, 'Google Forms' as platform,
        from {{ ref("stg_google_forms__form") }}
        where form_id is not null
    ),
```

- [ ] **Step 2: Replace `alchemer_surveys` CTE (lines 10-19).** First, run a
      quick column check to find the title column on `stg_alchemer__survey` (if
      Phase 0 Task 0.1 Step 4 didn't already capture it):

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster/.worktrees/cbini-refactor-claude-distinct-cleanup-3780 \
  run dbt show --project-dir src/dbt/kipptaf \
  --inline "select column_name from \`teamster-332318.kipptaf_alchemer.INFORMATION_SCHEMA.COLUMNS\` where table_name = 'stg_alchemer__survey' and lower(column_name) like '%title%'"
```

Then replace the current alchemer_surveys:

```sql
    alchemer_surveys as (
        -- DISTINCT projects from response grain to survey grain.
        select distinct
            safe_cast(survey_id as string) as survey_id,
            survey_title as survey_name,

            'Alchemer' as platform,
        from {{ source("alchemer", "base_alchemer__survey_results") }}
        where survey_id is not null
    ),
```

with (substitute `<title_col>` with whatever Step 2 returned — likely
`title_english` since `stg_alchemer__survey_question` uses that name):

```sql
    alchemer_surveys as (
        select
            safe_cast(id as string) as survey_id,
            <title_col> as survey_name,

            'Alchemer' as platform,
        from {{ ref("stg_alchemer__survey") }}
        where id is not null
    ),
```

- [ ] **Step 3: Leave `archive_manager`, `archive_support`, `powerschool_family`
      CTEs untouched** — they synthesize survey_keys for legacy data with
      downstream filter dependencies.

- [ ] **Step 4: Build and verify:**

```bash
VIRTUAL_ENV= uv \
  --directory /workspaces/teamster/.worktrees/cbini-refactor-claude-distinct-cleanup-3780 \
  run dbt build \
  --project-dir src/dbt/kipptaf \
  --select dim_surveys \
  --defer --state src/dbt/kipptaf/target/prod
```

- [ ] **Step 5: Verify delta** matches sum of Phase 0 queries C and D.

### Task 2.3: Rewrite `bridge_survey_questions.sql`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/bridges/bridge_survey_questions.sql:1-79`
  (redirect gforms, alchemer, manager)

**Precondition:** Phase 0 query G (Task 0.1 Step 7) must have returned
`n_current_only = 0`. If not, STOP and escalate manager_pairs to a new int per
spec.

- [ ] **Step 1: Replace `google_forms_pairs` CTE (lines 2-10).** Current:

```sql
    google_forms_pairs as (
        -- DISTINCT projects from response grain to (survey, question) pair grain.
        select distinct
            fr.form_id as survey_id,
            fr.item_abbreviation as question_shortname,
            fr.question_required as is_required,
        from {{ ref("int_google_forms__form_responses") }} as fr
        where fr.form_id is not null and fr.item_abbreviation is not null
    ),
```

Replace with:

```sql
    google_forms_pairs as (
        select
            form_id as survey_id,
            item_abbreviation as question_shortname,
            question_required as is_required,
        from {{ ref("int_google_forms__form__items") }}
        where form_id is not null and item_abbreviation is not null
    ),
```

- [ ] **Step 2: Replace `alchemer_pairs` CTE (lines 21-29).** Current:

```sql
    alchemer_pairs as (
        -- DISTINCT projects from response grain to (survey, question) pair grain.
        -- Covers Alchemer + Google Forms staff/student survey questions feeding
        -- fct_survey_responses.general_responses.
        select distinct
            sr.survey_id, sr.question_shortname, cast(null as bool) as is_required,
        from {{ ref("int_surveys__survey_responses") }} as sr
        where sr.survey_id is not null and sr.question_shortname is not null
    ),
```

Replace with:

```sql
    alchemer_pairs as (
        select
            safe_cast(survey_id as string) as survey_id,
            shortname as question_shortname,
            cast(null as bool) as is_required,
        from {{ ref("stg_alchemer__survey_question") }}
        where shortname is not null
    ),
```

- [ ] **Step 3: Replace `manager_pairs` CTE (lines 31-37) — redirect, not
      drop.** Current:

```sql
    manager_pairs as (
        -- DISTINCT projects from response grain to (survey, question) pair grain.
        select distinct
            ms.survey_id, ms.question_shortname, cast(null as bool) as is_required,
        from {{ ref("int_surveys__manager_survey_details") }} as ms
        where ms.survey_id is not null and ms.question_shortname is not null
    ),
```

Replace with:

```sql
    manager_pairs as (
        -- Synthesizes (survey_id, question_shortname) pairs for the
        -- historic Manager Survey archive, whose original Alchemer
        -- survey_ids were not preserved. Live Manager Survey pairs flow
        -- through google_forms_pairs above (same form_id).
        select
            'historic_alchemer_Manager_survey' as survey_id,
            item_abbreviation as question_shortname,
            cast(null as bool) as is_required,
        from {{ ref("int_google_forms__form__items") }}
        where form_id = '1cvp9RnYxbn-WGLXsYSupbEl2KhVhWKcOFbHR2CgUBH0'
            and item_abbreviation is not null
    ),
```

- [ ] **Step 4: Leave `scd_powerschool_pairs` CTE and the downstream
      `dbt_utils.deduplicate` block untouched.** The dedup partition
      `(survey_id, question_shortname)` continues to handle cross-CTE
      collisions.

- [ ] **Step 5: Build and verify:**

```bash
VIRTUAL_ENV= uv \
  --directory /workspaces/teamster/.worktrees/cbini-refactor-claude-distinct-cleanup-3780 \
  run dbt build \
  --project-dir src/dbt/kipptaf \
  --select bridge_survey_questions \
  --defer --state src/dbt/kipptaf/target/prod
```

- [ ] **Step 6: Verify delta** matches sum of Phase 0 queries E, F, G.

### Task 2.4: Commit surveys changes

- [ ] **Step 1: Stage modified files:**

```bash
cd /workspaces/teamster/.worktrees/cbini-refactor-claude-distinct-cleanup-3780
git add src/dbt/kipptaf/models/marts/dimensions/dim_survey_questions.sql \
        src/dbt/kipptaf/models/marts/dimensions/dim_surveys.sql \
        src/dbt/kipptaf/models/marts/bridges/bridge_survey_questions.sql
```

- [ ] **Step 2: Commit:**

```bash
git commit -m "$(cat <<'EOF'
refactor(dbt): redirect surveys marts to entity-grain upstreams

dim_survey_questions, dim_surveys, and bridge_survey_questions now read
from existing entity-grain models (int_google_forms__form__items,
stg_alchemer__survey_question, stg_alchemer__survey,
stg_google_forms__form) instead of collapsing response-grain models with
SELECT DISTINCT. manager_questions CTE removed as redundant; manager_pairs
redirected to derive historic Manager Survey pairs from the same Google
Form's items.

Refs #3780

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Commit 3: Cube migration (conditional)

### Task 3.1: Apply cube literal swaps (only if Phase 0 Task 0.3 surfaced matches)

**Precondition:** `.claude/scratch/phase0-results.md` lists one or more
`src/cube/model/*` matches. If none, **skip this entire task** and proceed to
Task 4.

**Files:** the cube model files identified in Task 0.3.

- [ ] **Step 1: For each match, determine the correct rewrite per its semantic
      context:**
  - Exact-match filter expecting all NJ state programs:
    `assessment_type = 'state_nj'` → `assessment_type LIKE 'state_nj_%'`
  - Same for `'state_fl'` → `LIKE 'state_fl_%'`
  - Filter that meant one specific program (rare; identify by surrounding
    label/title): substitute the specific lineage literal (e.g.
    `assessment_type = 'state_nj_njsla'`)

- [ ] **Step 2: Edit each cube file** with the appropriate swap.

- [ ] **Step 3: Validate cube model with the local cube dev process** per
      `src/cube/CLAUDE.md`. (If no local cube validation is available, defer to
      Cube CI on PR.)

- [ ] **Step 4: Stage and commit:**

```bash
cd /workspaces/teamster/.worktrees/cbini-refactor-claude-distinct-cleanup-3780
git add src/cube/model/
git commit -m "$(cat <<'EOF'
refactor(cube): migrate state_nj/state_fl filters for #3780 lineage split

Updates Cube model filters that referenced the pre-split assessment_type
literals 'state_nj' / 'state_fl' to use LIKE 'state_nj_%' / LIKE
'state_fl_%' patterns (or specific lineage literals where the filter
targeted one program).

Refs #3780

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Pre-merge: push, CI triage, PR

### Task 4.1: Push and watch CI

- [ ] **Step 1: Push the branch:**

```bash
cd /workspaces/teamster/.worktrees/cbini-refactor-claude-distinct-cleanup-3780
git push
```

- [ ] **Step 2: Wait for dbt Cloud CI to finish.** Use
      `mcp__github__pull_request_read get_status` against the PR (after Task 4.4
      opens it; if waiting before, poll `mcp__dbt__list_jobs_runs` for the most
      recent run on this branch).

- [ ] **Step 3: Pull marts-model warnings from the CI run:**

```text
mcp__dbt__get_job_run_error(run_id=<latest>, warning_only=true)
```

- [ ] **Step 4: For each warning on a touched mart:**
  - Search open issues by model name + FK target (`mcp__github__search_issues`)
  - Bucket orphans (by region, source, test_type, lineage) in scratch
  - If a new orphan pattern surfaces that isn't covered by an open issue: file a
    follow-up per marts CLAUDE.md "Filing follow-up issues" (project board #4,
    Tier / PR batch / Driver set)

### Task 4.2: Project board scan

- [ ] **Step 1:** Visit `https://github.com/orgs/TEAMSchools/projects/4/views/1`
      and scan for incidentally-resolved issues. Candidates: NJSLA-vs-PARCC
      reporting splits, lineage-aware assessment dashboards, EOC reporting
      requests, FL Science reporting, manager-pairs bridge issues.

- [ ] **Step 2: For each incidentally resolved: close in the PR** by referencing
      `Closes #N` in the PR body (Task 4.4).

### Task 4.3: File pre-existing follow-up

- [ ] **Step 1: File the `fct_assessment_scores_enrollment_scoped` admin-key
      hash mismatch issue** via `mcp__github__issue_write`:
  - Title:
    `fct_assessment_scores_enrollment_scoped state branch admin-key hash mismatch with dim_assessment_administrations`
  - Body: Describe the literal `'state'` (fact) vs `'state_nj_*'` /
    `'state_fl_*'` (dim) mismatch. Reference current line numbers in the fact
    for the hash inputs.
  - Labels: `dbt`, `bug`
  - Surfaced during #3780 spec investigation

- [ ] **Step 2: Add to project board #4 with `Tier`, `PR batch`, `Driver` set**
      per `src/dbt/kipptaf/models/marts/CLAUDE.md` filing convention. Prefix
      `gh project item-add` with `GITHUB_TOKEN=` to use the OAuth scope.

### Task 4.4: Open PR

- [ ] **Step 1: Prepare PR body** from `.github/pull_request_template.md` plus
      the Phase 0 results. Body must include:
  - Brief summary (lineage split + surveys redirects + DISTINCT annotations)
  - Phase 0 results table (all 7 queries + 4 expected-delta computations)
  - Pre-merge checklist results (R1-R10 scan = no rename / no new column; CI
    warning triage outcome; project board scan; pre-existing-issue follow-up
    filed)
  - Closes / Refs lines for #3780 and any incidentally-resolved issues from Task
    4.2
  - `Closes #3780`

- [ ] **Step 2: Open PR:**

```bash
gh pr create --title "refactor(dbt): #3780 distinct cleanup + state assessment lineage split" --body "$(cat <<'EOF'
## Summary

- Splits NJ and FL state assessments into per-program lineages
  (parcc / njsla / njsla_science / njgpa; fast / fsa / eoc / science)
  on dim_assessments and dim_assessment_administrations.
- Replaces SELECT DISTINCT in surveys marts with redirects to existing
  entity-grain models (int_google_forms__form__items,
  stg_alchemer__survey_question, etc.).
- Annotates surviving pure-projection DISTINCTs per the new
  src/dbt/CLAUDE.md rule (already in branch).

## Phase 0 audit results

<paste from .claude/scratch/phase0-results.md>

## Pre-merge checklist

- R1–R10 column rubric: no new columns, no renames — N/A
- Diamond paths: no new FKs — N/A
- CI warnings: <triage outcome>
- Project board scan: <incidentally-resolved list or "none">
- Pre-existing fct_assessment_scores admin-key hash mismatch: filed as
  #<num>

## Test plan

- [ ] Phase 0 BQ queries A-G run and documented
- [ ] dim_assessments builds, lineage spot-check returns exactly 8 state_* values
- [ ] dim_assessment_administrations builds, same lineage taxonomy
- [ ] dim_survey_questions, dim_surveys, bridge_survey_questions build
- [ ] Row-count deltas match Phase 0 expectations
- [ ] Cube CI green (or N/A if no cube changes)

Closes #3780

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Verify PR body** by reading it back via
      `mcp__github__pull_request_read`. Confirm no `env` token leaked into the
      body (would trigger the path hook).

---

## Self-Review Checklist (executed after plan is written)

- [x] Every spec section / requirement has a task implementing it
- [x] No placeholders (TBD/TODO/etc.) in the plan
- [x] Type/name consistency: `assessment_type` literals match across
      dim*assessments and dim_assessment_administrations (both use
      `state_nj*<lineage>`/`state*fl*<lineage>`)
- [x] File paths are absolute (worktree-rooted)
- [x] Each commit boundary has a stage-and-commit task
- [x] Phase 0 query G acts as the gate for the manager_pairs redirect in Task
      2.3
