# Batch F — Assessment / Survey Catalog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land seven
[PR batch F](https://github.com/orgs/TEAMSchools/projects/4) issues in one PR —
eliminate response-grain `SELECT DISTINCT` workarounds in `dim_assessments` /
`dim_surveys` / `dim_survey_questions` (#3646), dedup three int models at the
originating layer (#3628 / #3629), populate `region` and thread
section-enrollment plumbing through `int_assessments__scaffold` (#3736 / #3640),
replace `dim_student_assessment_expectations` with two grain-clean bridges
(#3640), introduce `dim_assessment_administrations` paralleling
`dim_survey_administrations`, drop R9-violating columns and dedup workarounds
from the assessment / survey facts, and verify the `fct_survey_responses` FK
gaps close (#3766). #3648 comparisons resolves as a spec-doc edit; #3648 targets
is carved out.

**Closes:** #3628, #3629, #3640, #3646, #3736, #3737 (sheet edit), #3766;
partial close of #3648 (comparisons half).

**Architecture:** Three phases. (1) Dedup at originating layer — investigate
each int's duplicate cause (raw source vs. join fan-out), apply
`dbt_utils.deduplicate` with explicit `partition_by` / `order_by`, audit
downstream consumers for row-count parity. (2) Scaffold enhancements — populate
NULL `region` via `int_people__location_crosswalk`; thread `cc_dcid` +
`_dbt_source_relation` through `int_assessments__course_enrollments` and into
the scaffold's internal-assessment branch so the new enrollment-scoped bridge
can hash a `student_section_enrollment_key`. (3) Mart cutover — rewrite three
dims as documented `SELECT DISTINCT` projections from existing response-grain
ints (no new ints), introduce `dim_assessment_administrations`, build the two
new expectation bridges, delete the mislabeled
`dim_student_assessment_expectations`, drop fact dedup workarounds, drop
R9-violating fact columns, switch fact FKs from `assessment_key` to
`assessment_administration_key`, edit the comparisons FK out of the star-schema
spec, verify #3766 relationships tests at 0.

**Tech Stack:** dbt-core 1.11+, BigQuery, dbt_utils. Project:
`src/dbt/kipptaf/`. All commands run from the worktree root via
`uv run dbt <cmd> --project-dir=src/dbt/kipptaf/`.

**Spec:**
[docs/superpowers/specs/2026-04-29-batch-f-assessment-survey-catalog-design.md](../specs/2026-04-29-batch-f-assessment-survey-catalog-design.md).

**Branch:** `cbini/feat/claude-batch-f-assessment-survey-catalog` (already
created in worktree
`.worktrees/cbini/feat/claude-batch-f-assessment-survey-catalog`).

---

## File Map

### Created

- `src/dbt/kipptaf/models/marts/dimensions/dim_assessment_administrations.sql`
- `src/dbt/kipptaf/models/marts/dimensions/properties/dim_assessment_administrations.yml`
- `src/dbt/kipptaf/models/marts/bridges/bridge_assessment_expectations_enrollment_scoped.sql`
- `src/dbt/kipptaf/models/marts/bridges/properties/bridge_assessment_expectations_enrollment_scoped.yml`
- `src/dbt/kipptaf/models/marts/bridges/bridge_assessment_expectations_student_scoped.sql`
- `src/dbt/kipptaf/models/marts/bridges/properties/bridge_assessment_expectations_student_scoped.yml`

### Modified

- `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__response_rollup.sql`
  — dedup at originating layer
- `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__college_assessment.sql`
  — dedup at originating layer
- `src/dbt/kipptaf/models/surveys/intermediate/int_surveys__survey_responses.sql`
  — dedup at originating layer
- `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__scaffold.sql`
  — populate `region`; thread `cc_dcid` + `_dbt_source_relation`
- `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__course_enrollments.sql`
  — expose `cc_dcid` + `_dbt_source_relation`
- `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__course_enrollments.yml`
  — describe new columns
- `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__scaffold.yml`
  — describe new columns
- `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__response_rollup.yml`
  — note dedup applied
- `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__college_assessment.yml`
  — note dedup applied
- `src/dbt/kipptaf/models/surveys/intermediate/properties/int_surveys__survey_responses.yml`
  — note dedup applied
- `src/dbt/kipptaf/models/marts/dimensions/dim_assessments.sql` — drop TODOs,
  add documenting comments
- `src/dbt/kipptaf/models/marts/dimensions/dim_surveys.sql` — drop TODOs, add
  documenting comments
- `src/dbt/kipptaf/models/marts/dimensions/dim_survey_questions.sql` — drop
  TODOs, add documenting comments
- `src/dbt/kipptaf/models/marts/bridges/bridge_survey_questions.sql` — drop
  TODOs, add documenting comments
- `src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_enrollment_scoped.sql`
  — drop dedup workaround; drop R9 columns; switch FK to
  `assessment_administration_key`
- `src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_student_scoped.sql`
  — same
- `src/dbt/kipptaf/models/marts/facts/fct_survey_responses.sql` — drop dedup
  workaround
- `src/dbt/kipptaf/models/marts/facts/properties/fct_assessment_scores_enrollment_scoped.yml`
  — column updates
- `src/dbt/kipptaf/models/marts/facts/properties/fct_assessment_scores_student_scoped.yml`
  — column updates
- `src/dbt/kipptaf/models/marts/facts/properties/fct_survey_responses.yml` —
  promote relationships tests to 0
- `src/dbt/kipptaf/models/exposures/cube.yml` — replace
  `dim_student_assessment_expectations` ref with the two new bridges
- `docs/superpowers/specs/2026-04-15-column-naming-audit.md` — add hash-change
  entries
- existing star-schema spec doc — remove
  `dim_assessment_comparisons → dim_assessments` FK requirement (path discovered
  during Task 17)

### Deleted

- `src/dbt/kipptaf/models/marts/dimensions/dim_student_assessment_expectations.sql`
- `src/dbt/kipptaf/models/marts/dimensions/properties/dim_student_assessment_expectations.yml`

---

## Working conventions

- All `git add` commands name specific files explicitly (no `-A`/`-u`/`.`).
- All commit messages use
  [conventional commits](https://www.conventionalcommits.org/) (`fix(dbt): ...`,
  `refactor(dbt): ...`, `feat(dbt): ...`).
- Trunk format runs as a PostToolUse hook on Edit/Write — do not run `trunk fmt`
  manually.
- Before pushing from the worktree, run
  `/workspaces/teamster/.trunk/tools/trunk check --ci` from the worktree root
  and fix any issues. Trunk git hooks are not installed in worktrees.
- BigQuery MCP (`mcp__bigquery__execute_sql`) for spike queries and audits. dbt
  MCP `mcp__dbt__show` for ad-hoc compiled-SQL inspection. The dbt build / test
  invocations in this plan are `uv run dbt build` / `uv run dbt test` because
  they need to materialize against the dev schema.
- All `uv run dbt …` commands include
  `--target dev --defer --state=src/dbt/kipptaf/target/prod/` unless otherwise
  stated. The prod manifest is refreshed on `git pull`; if stale, regenerate
  with
  `uv run dbt parse --target prod --project-dir src/dbt/kipptaf --target-path target/prod`.
- All Bash commands run from the worktree root:
  `/workspaces/teamster/.worktrees/cbini/feat/claude-batch-f-assessment-survey-catalog`.

---

## Phase 1 — Source dedup

### Task 1 — Dedup `int_assessments__response_rollup`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__response_rollup.sql`
- Modify:
  `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__response_rollup.yml`

- [ ] **Step 1.1: Profile the duplicate rows.** Run via BigQuery MCP:

```sql
WITH dups AS (
  SELECT
    illuminate_student_id,
    assessment_id,
    response_type,
    response_type_id,
    response_type_code,
    COUNT(*) AS n,
  FROM `teamster-332318.kipptaf_assessments.int_assessments__response_rollup`
  GROUP BY 1,2,3,4,5
  HAVING COUNT(*) > 1
)
SELECT
  COUNT(*) AS dup_groups,
  SUM(n) AS dup_rows,
  SUM(n) - COUNT(*) AS extra_rows,
FROM dups;
```

Record `dup_groups`, `dup_rows`, and `extra_rows` in the PR description's audit
table — `extra_rows` is the expected row-count delta after dedup.

- [ ] **Step 1.2: Identify the dedup key columns.** Examine one duplicate
      group's columns to determine which columns differ across rows in the same
      group (those are non-key and the order_by tiebreaker should pick the
      most-recent or highest-confidence row):

```sql
SELECT *
FROM `teamster-332318.kipptaf_assessments.int_assessments__response_rollup`
WHERE (illuminate_student_id, assessment_id, response_type, response_type_id, response_type_code) IN (
  SELECT AS STRUCT illuminate_student_id, assessment_id, response_type, response_type_id, response_type_code
  FROM `teamster-332318.kipptaf_assessments.int_assessments__response_rollup`
  GROUP BY 1,2,3,4,5
  HAVING COUNT(*) > 1
  LIMIT 1
);
```

- If the differing columns are `date_taken` / `points` / `percent_correct`, dups
  come from multiple administrations rolling up incorrectly — the `partition_by`
  should be the natural grain
  `(illuminate_student_id, assessment_id, response_type, response_type_id, response_type_code)`
  and `order_by` should be `date_taken desc, points desc`.
- If differing columns include `region` or `powerschool_school_id`, the upstream
  `int_assessments__scaffold` is fanning out across regions for the same
  student-assessment pair — the dedup key needs to include `region` and
  `powerschool_school_id` so cross-region scores aren't collapsed.

Record the chosen `partition_by` columns in the PR description.

- [ ] **Step 1.3: Apply `dbt_utils.deduplicate` to
      `int_assessments__response_rollup.sql`.** The current model ends with
      `select ... from response_union as ru left join …` and the result has
      duplicates. Wrap the final select in a CTE and add a deduplicate CTE:

```sql
-- existing CTEs above unchanged

    -- trunk-ignore(sqlfluff/ST03): referenced by string in dbt_utils.deduplicate
    enriched as (
        select
            ru.illuminate_student_id,
            ru.powerschool_student_number,
            ru.academic_year,
            ru.scope,
            ru.subject_area,
            ru.discipline,
            ru.module_type,
            ru.module_code,
            ru.region,
            ru.powerschool_school_id,
            ru.is_internal_assessment,
            ru.is_replacement,
            ru.response_type,
            ru.response_type_id,
            ru.response_type_code,
            ru.response_type_description,
            ru.response_type_root_description,
            ru.date_taken,
            ru.points,
            ru.percent_correct,
            ru.title,
            ru.assessment_id,
            ru.administered_at,
            ru.performance_band_set_id,
            ru.n_assessments,
            ru.is_multipart_assessment,
            ru.assessment_ids,

            pbl.label as performance_band_label,
            pbl.label_number as performance_band_label_number,
            pbl.is_mastery,

            rta.name as term_administered,

            rtt.name as term_taken,
        from response_union as ru
        left join
            {{ ref("int_illuminate__performance_band_sets") }} as pbl
            on ru.performance_band_set_id = pbl.performance_band_set_id
            and ru.percent_correct between pbl.minimum_value and pbl.maximum_value
        left join
            {{ ref("stg_google_sheets__reporting__terms") }} as rta
            on ru.administered_at between rta.start_date and rta.end_date
            and ru.powerschool_school_id = rta.school_id
            and rta.type = 'RT'
        left join
            {{ ref("stg_google_sheets__reporting__terms") }} as rtt
            on ru.date_taken between rtt.start_date and rtt.end_date
            and ru.powerschool_school_id = rtt.school_id
            and rtt.type = 'RT'
    )

select * from (
    {{
        dbt_utils.deduplicate(
            relation="enriched",
            partition_by="<columns from Step 1.2>",
            order_by="<order_by from Step 1.2>",
        )
    }}
)
```

Substitute the actual `partition_by` / `order_by` from Step 1.2.

- [ ] **Step 1.4: Add a uniqueness test.** In
      `properties/int_assessments__response_rollup.yml`, add (or update) a
      `data_tests:` block above `columns:`:

```yaml
data_tests:
  - dbt_utils.unique_combination_of_columns:
      arguments:
        combination_of_columns:
          - illuminate_student_id
          - assessment_id
          - response_type
          - response_type_id
          - response_type_code
```

(Substitute the columns from Step 1.2 if different.)

- [ ] **Step 1.5: Build and test the model.**

```bash
uv run dbt build --select int_assessments__response_rollup --target dev --defer --state=src/dbt/kipptaf/target/prod/ --project-dir src/dbt/kipptaf
```

Expected: build succeeds, uniqueness test passes.

- [ ] **Step 1.6: Run the downstream invariance audit.** List direct consumers
      and clone their prod state:

```bash
uv run dbt list --select int_assessments__response_rollup+1 --resource-type model --project-dir src/dbt/kipptaf
```

For each consumer (likely `fct_assessment_scores_enrollment_scoped`,
`dim_assessments`):

```bash
uv run dbt clone --select <consumer> --target dev --state=src/dbt/kipptaf/target/prod/ --project-dir src/dbt/kipptaf
```

Then build the consumer with the change applied and diff:

```sql
-- baseline (prod-cloned table) vs. dev-built table
WITH baseline AS (
  SELECT COUNT(*) AS n,
    TO_HEX(MD5(STRING_AGG(<pk> ORDER BY <pk>))) AS ck
  FROM `teamster-332318.<dev_schema_clone>.<consumer>`
), updated AS (
  SELECT COUNT(*) AS n,
    TO_HEX(MD5(STRING_AGG(<pk> ORDER BY <pk>))) AS ck
  FROM `teamster-332318.<dev_schema_dev>.<consumer>`
)
SELECT 'baseline' AS src, * FROM baseline
UNION ALL SELECT 'updated', * FROM updated;
```

For mart consumers that already apply `dbt_utils.deduplicate()` as a workaround
(`fct_assessment_scores_*`), `n` and `ck` should match — the upstream dedup is
functionally idempotent with the workaround, so the workaround sees no dups to
remove. Record the audit result in the PR description.

- [ ] **Step 1.7: Commit.**

```bash
git add src/dbt/kipptaf/models/assessments/intermediate/int_assessments__response_rollup.sql \
        src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__response_rollup.yml
git commit -m "fix(dbt): dedup int_assessments__response_rollup at originating layer

Closes the row-count drift that fct_assessment_scores_* compensates for
with dbt_utils.deduplicate. The mart workaround is removed in a later
commit once dim_assessments switches to admin-grain.

Refs #3628."
```

### Task 2 — Dedup `int_assessments__college_assessment`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__college_assessment.sql`
- Modify:
  `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__college_assessment.yml`

- [ ] **Step 2.1: Profile the duplicate rows.**

```sql
WITH dups AS (
  SELECT
    student_number,
    score_type,
    test_date,
    rn_highest,
    COUNT(*) AS n,
  FROM `teamster-332318.kipptaf_assessments.int_assessments__college_assessment`
  GROUP BY 1,2,3,4
  HAVING COUNT(*) > 1
)
SELECT COUNT(*) AS dup_groups, SUM(n) AS dup_rows, SUM(n) - COUNT(*) AS extra_rows FROM dups;
```

The existing fact `fct_assessment_scores_student_scoped` deduplicates with
`partition_by="student_number, score_type, test_date, rn_highest"` and
`order_by="scale_score desc"` — the spike result will likely confirm that grain.
If the dedup-key columns are the same, that's the dedup composition for this
int.

- [ ] **Step 2.2: Apply `dbt_utils.deduplicate` to
      `int_assessments__college_assessment.sql`.** The current model ends with a
      complex `select … from score_calcs` final SELECT. Wrap it in a CTE and add
      the deduplicate:

```sql
-- existing CTEs above unchanged through score_calcs

    -- trunk-ignore(sqlfluff/ST03): referenced by string in dbt_utils.deduplicate
    enriched as (
        select
            student_number,
            administration_round,
            academic_year,
            test_date,
            scope,
            subject_area,
            course_discipline,
            score_type,
            scale_score,
            rn_highest,
            salesforce_id,
            is_overall_score,
            is_subject_score,
            running_max_scale_score,
            surrogate_key,
            n_overall_scores,
            n_subject_scores,
            strategy_case,
            max_scale_score,
            previous_total_score_change,
            superscore,
            avg_running_max_superscore,
            sum_running_max_superscore,

            'Official' as test_type,

            format_date('%B', test_date) as test_month,

            if(
                subject_area in ('Composite', 'Combined'), 'Total', subject_area
            ) as aligned_subject_area,

            case
                when
                    score_type in (
                        'act_reading',
                        'sat_ebrw',
                        'psat10_ebrw',
                        'psatnmsqt_ebrw',
                        'psat89_ebrw'
                    )
                then 'EBRW/Reading'
                when subject_area in ('Composite', 'Combined')
                then 'Total'
                else subject_area
            end as aligned_subject,

            round(
                case
                    when scope = 'ACT'
                    then avg_running_max_superscore
                    when scope = 'SAT'
                    then sum_running_max_superscore
                end,
                0
            ) as runnning_superscore,
        from score_calcs
    )

select * from (
    {{
        dbt_utils.deduplicate(
            relation="enriched",
            partition_by="student_number, score_type, test_date, rn_highest",
            order_by="scale_score desc",
        )
    }}
)
```

(If Step 2.1 produced different partition columns, substitute.)

- [ ] **Step 2.3: Add the uniqueness test in YAML.**

```yaml
data_tests:
  - dbt_utils.unique_combination_of_columns:
      arguments:
        combination_of_columns:
          - student_number
          - score_type
          - test_date
          - rn_highest
```

- [ ] **Step 2.4: Build and test.**

```bash
uv run dbt build --select int_assessments__college_assessment --target dev --defer --state=src/dbt/kipptaf/target/prod/ --project-dir src/dbt/kipptaf
```

- [ ] **Step 2.5: Downstream audit.** Same procedure as Step 1.6 for
      `int_assessments__college_assessment+1` consumers.

- [ ] **Step 2.6: Commit.**

```bash
git add src/dbt/kipptaf/models/assessments/intermediate/int_assessments__college_assessment.sql \
        src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__college_assessment.yml
git commit -m "fix(dbt): dedup int_assessments__college_assessment at originating layer

Mirrors the fct_assessment_scores_student_scoped workaround at the
upstream int. Workaround removal lands in a later commit.

Refs #3628."
```

### Task 3 — Dedup `int_surveys__survey_responses`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/surveys/intermediate/int_surveys__survey_responses.sql`
- Modify:
  `src/dbt/kipptaf/models/surveys/intermediate/properties/int_surveys__survey_responses.yml`

- [ ] **Step 3.1: Profile dups in `int_surveys__survey_responses`.**

```sql
WITH dups AS (
  SELECT
    survey_id,
    survey_response_id,
    respondent_employee_number,
    respondent_email,
    question_shortname,
    COUNT(*) AS n,
  FROM `teamster-332318.kipptaf_surveys.int_surveys__survey_responses`
  GROUP BY 1,2,3,4,5
  HAVING COUNT(*) > 1
)
SELECT COUNT(*) AS dup_groups, SUM(n) AS dup_rows, SUM(n) - COUNT(*) AS extra_rows FROM dups;
```

- [ ] **Step 3.2: Find the source of dups.** Read
      [src/dbt/kipptaf/models/surveys/intermediate/int_surveys\_\_survey_responses.sql](../../src/dbt/kipptaf/models/surveys/intermediate/int_surveys__survey_responses.sql)
      — note which CTE produces the duplicates (likely the Alchemer source,
      given the issue title). The fix may be in that staging model (raw source
      dups) or in the int's joins (join fan-out).

- [ ] **Step 3.3: Apply dedup at the originating layer.** If raw source dups,
      fix in `stg_alchemer__*` with a `dbt_utils.deduplicate` ahead of the int.
      If join fan-out, fix the join condition. If neither cleanly applies, dedup
      in `int_surveys__survey_responses` itself with `partition_by` matching the
      dim's grain.

The existing mart `fct_survey_responses` already calls `dbt_utils.deduplicate`
with
`partition_by="survey_id, survey_response_id, respondent_identifier, question_shortname"`
and `order_by="response_text asc"`. Mirror that composition at the int layer if
the dups originate there.

```sql
-- in int_surveys__survey_responses.sql, wrap final select:

    -- trunk-ignore(sqlfluff/ST03): referenced by string in dbt_utils.deduplicate
    enriched as (
        -- ... existing final SELECT body ...
    )

select * from (
    {{
        dbt_utils.deduplicate(
            relation="enriched",
            partition_by="survey_id, survey_response_id, respondent_identifier, question_shortname",
            order_by="response_text asc",
        )
    }}
)
```

- [ ] **Step 3.4: Add the uniqueness test in YAML.**

- [ ] **Step 3.5: Build and audit.** Same pattern as Tasks 1–2.

- [ ] **Step 3.6: Commit.**

```bash
git add src/dbt/kipptaf/models/surveys/intermediate/int_surveys__survey_responses.sql \
        src/dbt/kipptaf/models/surveys/intermediate/properties/int_surveys__survey_responses.yml
git commit -m "fix(dbt): dedup int_surveys__survey_responses at originating layer

Refs #3629."
```

---

## Phase 2 — Scaffold enhancements

### Task 4 — Populate `region` in `int_assessments__scaffold`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__scaffold.sql`
- Modify:
  `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__scaffold.yml`

- [ ] **Step 4.1: Confirm scaffold consumers don't read `region IS NULL` as a
      flag.**

```bash
grep -rn "int_assessments__scaffold\|region is null\|region IS NULL" src/dbt/kipptaf/models/ --include="*.sql"
```

For any matches that filter on `region IS NULL`, document the consumer and
decide whether the new populated value preserves intended semantics. Record
findings in the PR description.

- [ ] **Step 4.2: Read the current scaffold file** to understand the three
      branches (internal, K-8 replacement, all-other-assessments). Two branches
      currently emit `null as region`. Both have `powerschool_school_id` set on
      every row.

- [ ] **Step 4.3: Add a region-resolution CTE.** At the top of
      `int_assessments__scaffold.sql`, after the existing
      `assessment_region_scaffold` CTE, add:

```sql
    -- trunk-ignore(sqlfluff/ST03): referenced from K-8 replacement and external branches
    school_to_region as (
        select distinct
            location_powerschool_school_id as powerschool_school_id,
            initcap(
                regexp_extract(
                    location_dagster_code_location, r'kipp(\w+)_'
                )
            ) as region,
        from {{ ref("int_people__location_crosswalk") }}
    ),
```

(`region` derived from `location_dagster_code_location` matches the existing
scaffold's region values.)

- [ ] **Step 4.4: Replace `null as region` in the K-8-replacement branch.** Find
      the `/* K-8 replacement curriculum */` SELECT in
      `int_assessments__scaffold.sql`. Replace `null as region` with a left join
      lookup. The branch becomes:

```sql
/* K-8 replacement curriculum */
select
    sa.student_id as illuminate_student_id,

    s.local_student_id as powerschool_student_number,

    a.assessment_id,
    a.title,
    a.subject_area,
    a.academic_year_clean as academic_year,
    a.administered_at,
    a.performance_band_set_id,

    ssa.site_id as powerschool_school_id,

    str.region,

    null as grade_level_id,

    a.scope,
    a.module_type,
    a.module_code,

    null as discipline,

    sa.student_assessment_id,
    sa.date_taken,

    true as is_internal_assessment,
    true as is_replacement,

    cast(null as int64) as cc_dcid,
    cast(null as string) as cc_source_relation,
from {{ ref("int_assessments__assessments") }} as a
inner join
    {{ ref("stg_illuminate__dna_assessments__students_assessments") }} as sa
    on a.assessment_id = sa.assessment_id
inner join
    {{ ref("stg_illuminate__public__students") }} as s on sa.student_id = s.student_id
inner join
    {{ ref("int_illuminate__student_session_aff") }} as ssa
    on sa.student_id = ssa.student_id
    and a.academic_year = ssa.academic_year
    and a.illuminate_grade_level_id != ssa.grade_level_id
    and ssa.rn_student_session_desc = 1
left join school_to_region as str on ssa.site_id = str.powerschool_school_id
where
    a.is_internal_assessment
    and a.subject_area in ('Text Study', 'Mathematics', 'Social Studies', 'Science')
    and a.grade_level <= 8
```

(`cc_dcid` / `cc_source_relation` set to NULL here — the K-8 replacement branch
has no section context. Task 5 adds these columns to the internal branch where
they're meaningful.)

- [ ] **Step 4.5: Replace `null as region` in the "all other assessments"
      branch.** Same pattern — add the `school_to_region` left join on
      `ssa.site_id`:

```sql
/* all other assessments */
select
    sa.student_id as illuminate_student_id,

    s.local_student_id as powerschool_student_number,

    a.assessment_id,
    a.title,
    a.subject_area,
    a.academic_year_clean as academic_year,
    a.administered_at,
    a.performance_band_set_id,

    ssa.site_id as powerschool_school_id,

    str.region,

    null as grade_level_id,

    a.scope,
    a.module_type,
    a.module_code,

    null as discipline,

    sa.student_assessment_id,
    sa.date_taken,

    false as is_internal_assessment,
    false as is_replacement,

    cast(null as int64) as cc_dcid,
    cast(null as string) as cc_source_relation,
from {{ ref("int_assessments__assessments") }} as a
inner join
    {{ ref("stg_illuminate__dna_assessments__students_assessments") }} as sa
    on a.assessment_id = sa.assessment_id
inner join
    {{ ref("stg_illuminate__public__students") }} as s on sa.student_id = s.student_id
inner join
    {{ ref("int_illuminate__student_session_aff") }} as ssa
    on a.academic_year = ssa.academic_year
    and sa.student_id = ssa.student_id
    and ssa.rn_student_session_desc = 1
left join school_to_region as str on ssa.site_id = str.powerschool_school_id
where not a.is_internal_assessment
```

- [ ] **Step 4.6: Build and verify region populated.**

```bash
uv run dbt build --select int_assessments__scaffold --target dev --defer --state=src/dbt/kipptaf/target/prod/ --project-dir src/dbt/kipptaf
```

Then via BigQuery MCP:

```sql
SELECT
  is_internal_assessment, is_replacement,
  COUNTIF(region IS NULL) AS n_null_region,
  COUNT(*) AS n,
FROM `teamster-332318.<dev_schema>.int_assessments__scaffold`
GROUP BY 1,2;
```

Expected: `n_null_region` is 0 across all branches (or near-0, with any residual
NULL caused by `powerschool_school_id` values that don't appear in the location
crosswalk — investigate residuals).

- [ ] **Step 4.7: Commit.**

```bash
git add src/dbt/kipptaf/models/assessments/intermediate/int_assessments__scaffold.sql
git commit -m "fix(dbt): populate region in int_assessments__scaffold via location crosswalk

Two of three UNION branches (K-8 replacement, all-other-assessments)
emitted null region for ~1.6M rows, breaking dim_student_assessment_-
expectations term_key resolution. Resolves region from
powerschool_school_id via int_people__location_crosswalk; all 25
distinct school_ids resolve.

Refs #3736."
```

### Task 5 — Thread `cc_dcid` and `_dbt_source_relation` through scaffold

**Files:**

- Modify:
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__course_enrollments.sql`
- Modify:
  `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__course_enrollments.yml`
- Modify:
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__scaffold.sql`
- Modify:
  `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__scaffold.yml`

- [ ] **Step 5.1: Read `int_assessments__course_enrollments.sql`** to see how it
      composes from `base_powerschool__course_enrollments`. The base model has
      `cc_dcid` and `_dbt_source_relation`; the int currently strips them.

- [ ] **Step 5.2: Add `cc_dcid` and `_dbt_source_relation` as additive columns
      to `int_assessments__course_enrollments.sql`.** In the final SELECT (or
      whichever CTE projects from `base_powerschool__course_enrollments`),
      include both columns alongside the existing ones. Place them in the SELECT
      order rule's "column enumerations" group with their source table:

```sql
select
    cc_dcid,
    _dbt_source_relation,
    -- ... existing column list ...
from {{ ref("base_powerschool__course_enrollments") }}
-- ... existing joins ...
```

(Read the file first to see the exact existing SELECT structure and integrate
without breaking column ordering rules.)

- [ ] **Step 5.3: Update the YAML for the int.** Add the two new column entries
      to `properties/int_assessments__course_enrollments.yml`, placed at the
      appropriate position in the column list:

```yaml
- name: cc_dcid
  data_type: int64
  description: >-
    PowerSchool course enrollment row identifier. Used as an upstream component
    of dim_student_section_enrollments.student_section_enrollment_key.
  config:
    meta:
      source_column: base_powerschool__course_enrollments.cc_dcid

- name: _dbt_source_relation
  data_type: string
  description: >-
    dbt union-relation metadata string identifying the source district project.
    Required upstream for the cc_dcid + _dbt_source_relation composite that
    uniquely identifies a course enrollment across the four district projects.
```

- [ ] **Step 5.4: Update the `internal_assessments` CTE in
      `int_assessments__scaffold.sql`** (both K-8 and HS subqueries) to project
      `ce.cc_dcid` and `ce._dbt_source_relation` as `cc_dcid` and
      `cc_source_relation` (rename to avoid clash with scaffold's own
      `_dbt_source_relation` if it inherits one — it doesn't; the rename is
      purely for downstream clarity). For the K-8 subquery:

```sql
select
    a.assessment_id,
    a.title,
    a.administered_at,
    a.performance_band_set_id,
    a.academic_year_clean,
    a.subject_area,
    a.scope,
    a.module_type,
    a.module_code,
    a.region,
    a.grade_level_id,

    ssa.student_id as illuminate_student_id,

    s.local_student_id as powerschool_student_number,

    ce.powerschool_school_id,
    ce.cc_dateenrolled,
    ce.cc_dateleft,
    ce.discipline,
    ce.cc_dcid,
    ce._dbt_source_relation as cc_source_relation,
from assessment_region_scaffold as a
-- existing joins unchanged
```

Same addition to the HS subquery. Then propagate `cc_dcid` and
`cc_source_relation` through the `deduplicate` CTE's column list (since
`dbt_utils.deduplicate` returns all input columns, the columns flow
automatically — but verify by reading the macro's compiled output if uncertain).

- [ ] **Step 5.5: Add `cc_dcid` and `cc_source_relation` to the final scaffold
      SELECT for the internal-assessment branch:**

```sql
/* internal assessments */
select
    ia.illuminate_student_id,
    ia.powerschool_student_number,
    ia.assessment_id,
    ia.title,
    ia.subject_area,
    ia.academic_year_clean as academic_year,
    ia.administered_at,
    ia.performance_band_set_id,
    ia.powerschool_school_id,
    ia.region,
    ia.grade_level_id,
    ia.scope,
    ia.module_type,
    ia.module_code,
    ia.discipline,
    ia.cc_dcid,
    ia.cc_source_relation,

    sa.student_assessment_id,
    sa.date_taken,

    true as is_internal_assessment,
    false as is_replacement,
from deduplicate as ia
left join
    {{ ref("stg_illuminate__dna_assessments__students_assessments") }} as sa
    on ia.illuminate_student_id = sa.student_id
    and ia.assessment_id = sa.assessment_id
```

The two non-internal branches already emit `cast(null as int64) as cc_dcid` and
`cast(null as string) as cc_source_relation` from Task 4, so the UNION ALL is
column-compatible.

- [ ] **Step 5.6: Update YAML for `int_assessments__scaffold`.** Add the two new
      column entries (with the same descriptions as the course_enrollments int's
      YAML, adjusted source pointers).

- [ ] **Step 5.7: Build and verify column population.**

```bash
uv run dbt build --select int_assessments__course_enrollments int_assessments__scaffold --target dev --defer --state=src/dbt/kipptaf/target/prod/ --project-dir src/dbt/kipptaf
```

Then:

```sql
SELECT
  is_internal_assessment,
  is_replacement,
  COUNTIF(cc_dcid IS NOT NULL) AS n_with_dcid,
  COUNTIF(cc_dcid IS NULL) AS n_without_dcid,
FROM `teamster-332318.<dev_schema>.int_assessments__scaffold`
GROUP BY 1,2;
```

Expected: `n_with_dcid > 0` for
`is_internal_assessment=true AND is_replacement=false`; `n_with_dcid = 0` for
the other two branches.

- [ ] **Step 5.8: Confirm no `dbt_utils.star()` consumer breaks.**

```bash
grep -rn "star.*int_assessments__course_enrollments\|star.*int_assessments__scaffold" src/dbt/ --include="*.sql"
```

If any consumers use `dbt_utils.star`, add the new column names to the `except`
list in those refs (none expected, but verify).

- [ ] **Step 5.9: Commit.**

```bash
git add src/dbt/kipptaf/models/assessments/intermediate/int_assessments__course_enrollments.sql \
        src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__course_enrollments.yml \
        src/dbt/kipptaf/models/assessments/intermediate/int_assessments__scaffold.sql \
        src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__scaffold.yml
git commit -m "feat(dbt): thread cc_dcid + _dbt_source_relation through assessment scaffold

Adds cc_dcid and cc_source_relation as additive columns on
int_assessments__course_enrollments and on int_assessments__scaffold
(internal-assessment branch only — set null on K-8-replacement and
external branches). Required upstream for the new
bridge_assessment_expectations_enrollment_scoped to hash a
student_section_enrollment_key.

Refs #3640."
```

---

## Phase 3 — Mart cutover

### Task 6 — Rewrite `dim_assessments`

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_assessments.sql`
- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_assessments.yml`

The existing `dim_assessments` already uses `SELECT DISTINCT` per source — we
keep that pattern, replace the `TODO:` comments with documenting comments, and
(per spec) keep `assessment_key` composition unchanged. `assessment_key` stays
at definition grain. **Hash is unchanged** — this task is documentation cleanup;
the new `dim_assessment_administrations` (Task 7) is where the
per-administration grain lives.

- [ ] **Step 6.1: Rewrite `dim_assessments.sql`** to replace each `-- TODO:`
      with a documenting comment that explains the projection-not-dedup
      distinction:

```sql
with
    -- DISTINCT projects from response grain (one row per student) to
    -- definition grain (one row per assessment definition). Per-student
    -- columns are not in the projection, so byte-identical projected tuples
    -- are coalesced. Not a workaround for dirty data — the projection IS
    -- the operation. Per-administration attributes live on
    -- dim_assessment_administrations.
    illuminate_assessments as (
        select distinct
            'illuminate' as assessment_type,
            title,
            subject_area,
            scope,
            module_code,
            module_type,
            grade_level,
            is_internal_assessment,

            'enrollment' as assessment_scope,

            cast(null as string) as combined_academic_subject,
            cast(null as string) as aligned_academic_subject,
            cast(null as string) as credit_category,
        from {{ ref("int_assessments__assessments") }}
        where is_internal_assessment
    ),

    -- DISTINCT projects from response grain to definition grain (see
    -- illuminate_assessments comment above).
    state_nj as (
        select distinct
            'state' as assessment_type,
            assessment_name as title,

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

            cast(null as string) as module_type,

            test_grade as grade_level,

            false as is_internal_assessment,

            'enrollment' as assessment_scope,

            cast(null as string) as combined_academic_subject,
            cast(null as string) as aligned_academic_subject,
            cast(null as string) as credit_category,
        from {{ ref("int_pearson__all_assessments") }}
        where testscalescore is not null
    ),

    -- DISTINCT projects from response grain to definition grain.
    state_fl as (
        select distinct
            'state' as assessment_type,
            assessment_name as title,
            assessment_subject as subject_area,
            discipline as scope,
            test_code as module_code,

            cast(null as string) as module_type,

            cast(assessment_grade as int) as grade_level,

            false as is_internal_assessment,

            'enrollment' as assessment_scope,

            cast(null as string) as combined_academic_subject,
            cast(null as string) as aligned_academic_subject,
            cast(null as string) as credit_category,
        from {{ ref("int_fldoe__all_assessments") }}
        where scale_score is not null
    ),

    -- DISTINCT projects from response grain to definition grain.
    college_assessments as (
        select distinct
            'college' as assessment_type,
            scope as title,
            subject_area,
            scope,
            score_type as module_code,

            cast(null as string) as module_type,
            cast(null as int64) as grade_level,

            false as is_internal_assessment,

            'student' as assessment_scope,

            aligned_subject as combined_academic_subject,
            aligned_subject_area as aligned_academic_subject,
            course_discipline as credit_category,
        from {{ ref("int_assessments__college_assessment") }}
    ),

    -- DISTINCT projects from response grain to definition grain.
    ap_assessments as (
        select distinct
            'college' as assessment_type,
            concat('AP ', test_subject) as title,
            test_subject as subject_area,

            'AP' as scope,

            ps_ap_course_subject_code as module_code,

            cast(null as string) as module_type,
            cast(null as int64) as grade_level,

            false as is_internal_assessment,

            'student' as assessment_scope,

            cast(null as string) as combined_academic_subject,
            cast(null as string) as aligned_academic_subject,
            cast(null as string) as credit_category,
        from {{ ref("int_assessments__ap_assessments") }}
    ),

    all_assessments as (
        select *,
        from illuminate_assessments
        union all
        select *,
        from state_nj
        union all
        select *,
        from state_fl
        union all
        select *,
        from college_assessments
        union all
        select *,
        from ap_assessments
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "assessment_type",
                "title",
                "subject_area",
                "scope",
                "module_code",
                "grade_level",
            ]
        )
    }} as assessment_key,

    assessment_type as `type`,
    title,
    subject_area as academic_subject,
    scope as category,
    module_code,
    module_type,
    grade_level as grade_level_tested,
    is_internal_assessment,
    assessment_scope as scope,
    combined_academic_subject,
    aligned_academic_subject,
    credit_category,
from all_assessments
```

- [ ] **Step 6.2: Build and verify uniqueness.**

```bash
uv run dbt build --select dim_assessments --target dev --defer --state=src/dbt/kipptaf/target/prod/ --project-dir src/dbt/kipptaf
```

Expected: passes, including the existing `unique` test on `assessment_key`. Row
count should match prod (no logical change — only comments).

- [ ] **Step 6.3: Commit.**

```bash
git add src/dbt/kipptaf/models/marts/dimensions/dim_assessments.sql
git commit -m "refactor(dbt): document SELECT DISTINCT as projection in dim_assessments

Comments mark each per-source DISTINCT as a projection from response
grain to definition grain — not a dedup workaround. Hash composition
unchanged.

Refs #3646."
```

### Task 7 — Create `dim_assessment_administrations`

**Files:**

- Create:
  `src/dbt/kipptaf/models/marts/dimensions/dim_assessment_administrations.sql`
- Create:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_assessment_administrations.yml`

- [ ] **Step 7.1: Write `dim_assessment_administrations.sql`.** One CTE per
      source projecting administration-grain columns; UNION ALL into
      `all_administrations`; final SELECT generates
      `assessment_administration_key` + the FK to `dim_assessments`:

```sql
with
    -- DISTINCT projects from response grain to administration grain (one row
    -- per scheduled occurrence). Internal assessments use administered_at as
    -- the occurrence date.
    illuminate_administrations as (
        select distinct
            'illuminate' as assessment_type,
            title,
            subject_area,
            scope,
            module_code,
            grade_level,

            cast(administered_at as date) as administered_date,
            academic_year,
            region,

            cast(null as string) as administration_round,
            cast(null as string) as season,
            cast(null as string) as administration_window,
            cast(null as string) as test_type,
        from {{ ref("int_assessments__assessments") }}
        where is_internal_assessment
    ),

    -- State NJ: one administration per (testcode, period, academic_year,
    -- region). period acts as the season/window.
    state_nj_administrations as (
        select distinct
            'state' as assessment_type,
            assessment_name as title,

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

            initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_'))
            as region,

            cast(null as string) as administration_round,

            if(`period` = 'FallBlock', 'Fall', `period`) as season,
            if(`period` = 'FallBlock', 'Fall', `period`) as administration_window,

            cast(null as string) as test_type,
        from {{ ref("int_pearson__all_assessments") }}
        where testscalescore is not null
    ),

    -- State FL: one administration per (test_code, season, academic_year, region).
    state_fl_administrations as (
        select distinct
            'state' as assessment_type,
            assessment_name as title,
            assessment_subject as subject_area,
            discipline as scope,
            test_code as module_code,

            cast(assessment_grade as int) as grade_level,

            cast(null as date) as administered_date,
            academic_year,

            initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_'))
            as region,

            cast(null as string) as administration_round,

            season,
            administration_window,

            cast(null as string) as test_type,
        from {{ ref("int_fldoe__all_assessments") }}
        where scale_score is not null
    ),

    -- College: one administration per (score_type, test_date,
    -- administration_round). region is null because college tests are
    -- region-agnostic.
    college_administrations as (
        select distinct
            'college' as assessment_type,
            scope as title,
            subject_area,
            scope,
            score_type as module_code,

            cast(null as int64) as grade_level,

            test_date as administered_date,
            academic_year,

            cast(null as string) as region,

            administration_round,

            cast(null as string) as season,
            cast(null as string) as administration_window,

            test_type,
        from {{ ref("int_assessments__college_assessment") }}
    ),

    -- AP: one administration per (subject, academic_year). Test date is
    -- not captured upstream.
    ap_administrations as (
        select distinct
            'college' as assessment_type,
            concat('AP ', test_subject) as title,
            test_subject as subject_area,

            'AP' as scope,

            ps_ap_course_subject_code as module_code,

            cast(null as int64) as grade_level,

            cast(null as date) as administered_date,
            academic_year,

            cast(null as string) as region,
            cast(null as string) as administration_round,
            cast(null as string) as season,
            cast(null as string) as administration_window,

            'Official' as test_type,
        from {{ ref("int_assessments__ap_assessments") }}
    ),

    all_administrations as (
        select *, from illuminate_administrations
        union all
        select *, from state_nj_administrations
        union all
        select *, from state_fl_administrations
        union all
        select *, from college_administrations
        union all
        select *, from ap_administrations
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "assessment_type",
                "title",
                "subject_area",
                "scope",
                "module_code",
                "grade_level",
                "administered_date",
                "academic_year",
                "administration_round",
                "region",
            ]
        )
    }} as assessment_administration_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "assessment_type",
                "title",
                "subject_area",
                "scope",
                "module_code",
                "grade_level",
            ]
        )
    }} as assessment_key,

    administered_date as administered_date_key,

    academic_year,
    region,
    administration_round,
    season,
    administration_window,
    test_type,
from all_administrations
```

- [ ] **Step 7.2: Write `properties/dim_assessment_administrations.yml`.**

```yaml
models:
  - name: dim_assessment_administrations
    description: >-
      Per-scheduled-occurrence dimension paralleling dim_survey_administrations.
      One row per (assessment_definition × administered_date × academic_year ×
      administration_round × region). Covers internal Illuminate assessments, NJ
      and FL state assessments, and college-entrance assessments (SAT, ACT, AP).
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - assessment_administration_key
    columns:
      - name: assessment_administration_key
        data_type: string
        description: >-
          Surrogate key derived from the assessment definition components plus
          administered_date, academic_year, administration_round, and region.
          Primary key.
        constraints:
          - type: primary_key
            warn_unsupported: false
        data_tests:
          - unique
          - not_null

      - name: assessment_key
        data_type: string
        description: >-
          FK to dim_assessments. Same hash composition as
          dim_assessments.assessment_key — joining on this column lifts
          assessment-definition attributes.
        constraints:
          - type: foreign_key
            to: ref('dim_assessments')
            to_columns: [assessment_key]
            warn_unsupported: false
        data_tests:
          - relationships:
              arguments:
                to: ref('dim_assessments')
                field: assessment_key

      - name: administered_date_key
        data_type: date
        description: >-
          FK to dim_dates. Date the assessment administration occurred. Null for
          sources that don't capture an exact date (state, AP) — the
          administration is identified by academic_year + season +
          administration_window instead.
        constraints:
          - type: foreign_key
            to: ref('dim_dates')
            to_columns: [date_key]
            warn_unsupported: false
        data_tests:
          - relationships:
              arguments:
                to: ref('dim_dates')
                field: date_key

      - name: academic_year
        data_type: int64
        description: >-
          Academic year of the administration.

      - name: region
        data_type: string
        description: >-
          KIPP region the administration is scoped to (Newark, Camden, Miami,
          Paterson). Null for college-entrance assessments which are region-
          agnostic.

      - name: administration_round
        data_type: string
        description: >-
          College Board administration round (Sept, Oct, Nov, Dec, Mar, May,
          June). Populated for college-entrance assessments only.

      - name: season
        data_type: string
        description: >-
          State assessment season (e.g., Fall, Winter, Spring). Populated for
          state assessments only.

      - name: administration_window
        data_type: string
        description: >-
          State assessment administration window. Populated for state
          assessments only; mirrors season for NJ but distinct for FL.

      - name: test_type
        data_type: string
        description: >-
          'Official' for AP and college assessments; null for internal and
          state.
```

- [ ] **Step 7.3: Build and test.**

```bash
uv run dbt build --select dim_assessment_administrations --target dev --defer --state=src/dbt/kipptaf/target/prod/ --project-dir src/dbt/kipptaf
```

Expected: passes, including the uniqueness and relationships tests on
`assessment_key → dim_assessments`.

- [ ] **Step 7.4: Commit.**

```bash
git add src/dbt/kipptaf/models/marts/dimensions/dim_assessment_administrations.sql \
        src/dbt/kipptaf/models/marts/dimensions/properties/dim_assessment_administrations.yml
git commit -m "feat(dbt): add dim_assessment_administrations

Per-scheduled-occurrence dim parallel to dim_survey_administrations.
One row per definition × administered_date × academic_year ×
administration_round × region. Source-system multi-administration
patterns are heterogeneous (Illuminate per-region per-AY, state per-AY-
per-window, College Board per-sitting, AP per-AY); splitting from
dim_assessments keeps each dim grain-clean.

Refs #3646."
```

### Task 8 — Rewrite `dim_surveys`

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_surveys.sql`

- [ ] **Step 8.1: Replace TODO comments** in the two `select distinct` CTEs
      (`google_forms_surveys`, `alchemer_surveys`) with documenting comments.
      The model is otherwise correct:

```sql
    -- DISTINCT projects from response grain to survey grain.
    google_forms_surveys as (
        select distinct
            form_id as survey_id, info_title as survey_name, 'Google Forms' as platform,
        from {{ ref("int_google_forms__form_responses") }}
        where form_id is not null
    ),

    -- DISTINCT projects from response grain to survey grain.
    alchemer_surveys as (
        select distinct
            safe_cast(survey_id as string) as survey_id,
            survey_title as survey_name,

            'Alchemer' as platform,
        from {{ source("alchemer", "base_alchemer__survey_results") }}
        where survey_id is not null
    ),
```

- [ ] **Step 8.2: Build and test.**

```bash
uv run dbt build --select dim_surveys --target dev --defer --state=src/dbt/kipptaf/target/prod/ --project-dir src/dbt/kipptaf
```

- [ ] **Step 8.3: Commit.**

```bash
git add src/dbt/kipptaf/models/marts/dimensions/dim_surveys.sql
git commit -m "refactor(dbt): document SELECT DISTINCT as projection in dim_surveys

Refs #3646."
```

### Task 9 — Rewrite `dim_survey_questions`

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_survey_questions.sql`

- [ ] **Step 9.1: Replace the `google_forms_questions` TODO** with a documenting
      comment matching Task 8. The existing `dbt_utils.deduplicate` block on the
      union stays — it handles cross-source collisions (google_forms vs SCD),
      which is a different operation from the per-source projection.

```sql
    -- DISTINCT projects from response grain to question grain.
    google_forms_questions as (
        select distinct
            fr.item_abbreviation as question_shortname,
            fr.item_title as question_text,
            fr.question_kind as question_type,
        from {{ ref("int_google_forms__form_responses") }} as fr
        where fr.item_abbreviation is not null and fr.item_title is not null
    ),
```

- [ ] **Step 9.2: Build and test.**

```bash
uv run dbt build --select dim_survey_questions --target dev --defer --state=src/dbt/kipptaf/target/prod/ --project-dir src/dbt/kipptaf
```

- [ ] **Step 9.3: Commit.**

```bash
git add src/dbt/kipptaf/models/marts/dimensions/dim_survey_questions.sql
git commit -m "refactor(dbt): document SELECT DISTINCT as projection in dim_survey_questions

Refs #3646."
```

### Task 10 — Rewrite `bridge_survey_questions`

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/bridges/bridge_survey_questions.sql`

- [ ] **Step 10.1: Replace the `google_forms_pairs` TODO** with a documenting
      comment:

```sql
    -- DISTINCT projects from response grain to (survey, question) pair grain.
    google_forms_pairs as (
        select distinct
            fr.form_id as survey_id,
            fr.item_abbreviation as question_shortname,
            fr.question_required as is_required,
        from {{ ref("int_google_forms__form_responses") }} as fr
        where fr.form_id is not null and fr.item_abbreviation is not null
    ),
```

- [ ] **Step 10.2: Build and test.**

```bash
uv run dbt build --select bridge_survey_questions --target dev --defer --state=src/dbt/kipptaf/target/prod/ --project-dir src/dbt/kipptaf
```

- [ ] **Step 10.3: Commit.**

```bash
git add src/dbt/kipptaf/models/marts/bridges/bridge_survey_questions.sql
git commit -m "refactor(dbt): document SELECT DISTINCT as projection in bridge_survey_questions

Refs #3646."
```

### Task 11 — Create `bridge_assessment_expectations_enrollment_scoped`

**Files:**

- Create:
  `src/dbt/kipptaf/models/marts/bridges/bridge_assessment_expectations_enrollment_scoped.sql`
- Create:
  `src/dbt/kipptaf/models/marts/bridges/properties/bridge_assessment_expectations_enrollment_scoped.yml`

- [ ] **Step 11.1: Write the bridge SQL.** Source rows from the scaffold's
      internal-assessment-and-not-replacement subset; hash
      `student_section_enrollment_key` from `(cc_dcid, cc_source_relation)` and
      `assessment_administration_key` from the same composition
      `dim_assessment_administrations` uses.

```sql
with
    expectations as (
        select
            cc_dcid,
            cc_source_relation,
            assessment_id,
            title,
            subject_area,
            scope,
            module_code,
            grade_level_id,
            administered_at,
            academic_year,
            region,

            cast(null as string) as administration_round,
        from {{ ref("int_assessments__scaffold") }}
        where is_internal_assessment and not is_replacement
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "cc_dcid",
                "cc_source_relation",
                "assessment_id",
                "administered_at",
            ]
        )
    }} as assessment_expectation_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "cc_dcid",
                "cc_source_relation",
            ]
        )
    }} as student_section_enrollment_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "'illuminate'",
                "title",
                "subject_area",
                "scope",
                "module_code",
                "grade_level_id",
                "cast(administered_at as date)",
                "academic_year",
                "administration_round",
                "region",
            ]
        )
    }} as assessment_administration_key,
from expectations
```

- [ ] **Step 11.2: Write the YAML.**

```yaml
models:
  - name: bridge_assessment_expectations_enrollment_scoped
    description: >-
      Factless many-to-many bridge linking student section enrollments to
      scheduled assessment administrations. One row per (student section
      enrollment × assessment administration). Replaces the internal- assessment
      portion of the deleted dim_student_assessment_expectations.
    columns:
      - name: assessment_expectation_key
        data_type: string
        description: >-
          Surrogate key. Primary key.
        constraints:
          - type: primary_key
            warn_unsupported: false
        data_tests:
          - unique
          - not_null

      - name: student_section_enrollment_key
        data_type: string
        description: >-
          FK to dim_student_section_enrollments. Identifies the student section
          enrollment under which the assessment is expected to be administered.
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

      - name: assessment_administration_key
        data_type: string
        description: >-
          FK to dim_assessment_administrations. Identifies the scheduled
          administration of the assessment definition.
        constraints:
          - type: foreign_key
            to: ref('dim_assessment_administrations')
            to_columns: [assessment_administration_key]
            warn_unsupported: false
        data_tests:
          - relationships:
              arguments:
                to: ref('dim_assessment_administrations')
                field: assessment_administration_key
```

- [ ] **Step 11.3: Build and test.**

```bash
uv run dbt build --select bridge_assessment_expectations_enrollment_scoped --target dev --defer --state=src/dbt/kipptaf/target/prod/ --project-dir src/dbt/kipptaf
```

Expected: passes uniqueness; both relationships tests at 0 orphans (the bridge's
source filter `is_internal_assessment AND NOT is_replacement` matches the
section-context-bearing scaffold rows from Task 5;
`assessment_administration_key` resolves because the dim's per-source CTEs cover
Illuminate via `int_assessments__assessments`).

- [ ] **Step 11.4: Commit.**

```bash
git add src/dbt/kipptaf/models/marts/bridges/bridge_assessment_expectations_enrollment_scoped.sql \
        src/dbt/kipptaf/models/marts/bridges/properties/bridge_assessment_expectations_enrollment_scoped.yml
git commit -m "feat(dbt): add bridge_assessment_expectations_enrollment_scoped

Refs #3640."
```

### Task 12 — Create `bridge_assessment_expectations_student_scoped`

**Files:**

- Create:
  `src/dbt/kipptaf/models/marts/bridges/bridge_assessment_expectations_student_scoped.sql`
- Create:
  `src/dbt/kipptaf/models/marts/bridges/properties/bridge_assessment_expectations_student_scoped.yml`

- [ ] **Step 12.1: Write the bridge SQL.** Source from scaffold rows where
      `NOT is_internal_assessment OR is_replacement`. Hash `student_key` from
      `powerschool_student_number`; `assessment_administration_key` from the
      same composition; `term_key` resolves via the existing
      `stg_google_sheets__reporting__terms` join.

```sql
with
    expectations as (
        select
            sc.powerschool_student_number,
            sc.assessment_id,
            sc.title,
            sc.subject_area,
            sc.scope,
            sc.module_code,
            sc.grade_level_id,
            sc.administered_at,
            sc.academic_year,
            sc.region,
            sc.powerschool_school_id,
            sc.is_internal_assessment,

            cast(null as string) as administration_round,

            rt.code as term_code,
            rt.type as term_type,
            rt.name as term_name,
            rt.start_date as term_start_date,
            rt.region as term_region,
            rt.school_id as term_school_id,
        from {{ ref("int_assessments__scaffold") }} as sc
        left join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on sc.administered_at between rt.start_date and rt.end_date
            and sc.powerschool_school_id = rt.school_id
            and sc.region = rt.region
            and rt.type = 'RT'
        where not sc.is_internal_assessment or sc.is_replacement
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "powerschool_student_number",
                "assessment_id",
                "administered_at",
            ]
        )
    }} as assessment_expectation_key,

    if(
        powerschool_student_number is not null,
        {{ dbt_utils.generate_surrogate_key(["powerschool_student_number"]) }},
        cast(null as string)
    ) as student_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "if(is_internal_assessment, 'illuminate', 'state')",
                "title",
                "subject_area",
                "scope",
                "module_code",
                "grade_level_id",
                "cast(administered_at as date)",
                "academic_year",
                "administration_round",
                "region",
            ]
        )
    }} as assessment_administration_key,

    if(
        term_code is not null,
        {{
            dbt_utils.generate_surrogate_key(
                [
                    "term_type",
                    "term_code",
                    "term_name",
                    "term_start_date",
                    "term_region",
                    "term_school_id",
                ]
            )
        }},
        cast(null as string)
    ) as term_key,
from expectations
```

(The `if(is_internal_assessment, 'illuminate', 'state')` literal is a
CTE-derived computed column per `src/dbt/CLAUDE.md` "Don't inline CASE
expressions in generate_surrogate_key" — but the rule applies to CASE
specifically; an `if()` here is a single string expression, no comma collisions.
If the linter flags it, lift to a CTE column named `assessment_source` and hash
that.)

Wait — it would still require derivation in the CTE for safety. **Substitute
Step 12.1 SQL with this** — derive `assessment_source` in `expectations`:

```sql
with
    expectations as (
        select
            sc.powerschool_student_number,
            sc.assessment_id,
            sc.title,
            sc.subject_area,
            sc.scope,
            sc.module_code,
            sc.grade_level_id,
            sc.administered_at,
            sc.academic_year,
            sc.region,
            sc.powerschool_school_id,
            sc.is_internal_assessment,

            cast(null as string) as administration_round,

            if(sc.is_internal_assessment, 'illuminate', 'state')
            as assessment_source,

            rt.code as term_code,
            rt.type as term_type,
            rt.name as term_name,
            rt.start_date as term_start_date,
            rt.region as term_region,
            rt.school_id as term_school_id,
        from {{ ref("int_assessments__scaffold") }} as sc
        left join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on sc.administered_at between rt.start_date and rt.end_date
            and sc.powerschool_school_id = rt.school_id
            and sc.region = rt.region
            and rt.type = 'RT'
        where not sc.is_internal_assessment or sc.is_replacement
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "powerschool_student_number",
                "assessment_id",
                "administered_at",
            ]
        )
    }} as assessment_expectation_key,

    if(
        powerschool_student_number is not null,
        {{ dbt_utils.generate_surrogate_key(["powerschool_student_number"]) }},
        cast(null as string)
    ) as student_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "assessment_source",
                "title",
                "subject_area",
                "scope",
                "module_code",
                "grade_level_id",
                "cast(administered_at as date)",
                "academic_year",
                "administration_round",
                "region",
            ]
        )
    }} as assessment_administration_key,

    if(
        term_code is not null,
        {{
            dbt_utils.generate_surrogate_key(
                [
                    "term_type",
                    "term_code",
                    "term_name",
                    "term_start_date",
                    "term_region",
                    "term_school_id",
                ]
            )
        }},
        cast(null as string)
    ) as term_key,
from expectations
```

- [ ] **Step 12.2: Write the YAML.**

```yaml
models:
  - name: bridge_assessment_expectations_student_scoped
    description: >-
      Factless many-to-many bridge linking students to scheduled assessment
      administrations for external (state, college, AP) and K-8 replacement
      assessments where there is no section enrollment context. One row per
      (student × assessment administration). Replaces the external- assessment
      portion of the deleted dim_student_assessment_expectations.
    columns:
      - name: assessment_expectation_key
        data_type: string
        description: >-
          Surrogate key. Primary key.
        constraints:
          - type: primary_key
            warn_unsupported: false
        data_tests:
          - unique
          - not_null

      - name: student_key
        data_type: string
        description: >-
          FK to dim_students.
        constraints:
          - type: foreign_key
            to: ref('dim_students')
            to_columns: [student_key]
            warn_unsupported: false
        data_tests:
          - relationships:
              arguments:
                to: ref('dim_students')
                field: student_key

      - name: assessment_administration_key
        data_type: string
        description: >-
          FK to dim_assessment_administrations.
        constraints:
          - type: foreign_key
            to: ref('dim_assessment_administrations')
            to_columns: [assessment_administration_key]
            warn_unsupported: false
        data_tests:
          - relationships:
              arguments:
                to: ref('dim_assessment_administrations')
                field: assessment_administration_key

      - name: term_key
        data_type: string
        description: >-
          FK to dim_terms. Resolves via (region × administered_date × school)
          against the reporting terms sheet.
        constraints:
          - type: foreign_key
            to: ref('dim_terms')
            to_columns: [term_key]
            warn_unsupported: false
        data_tests:
          - relationships:
              arguments:
                to: ref('dim_terms')
                field: term_key
```

- [ ] **Step 12.3: Build and test.**

```bash
uv run dbt build --select bridge_assessment_expectations_student_scoped --target dev --defer --state=src/dbt/kipptaf/target/prod/ --project-dir src/dbt/kipptaf
```

Expected: passes; relationships warnings on `term_key` may persist for Paterson
2026-02-02 rows until #3737 sheet edit lands. Document any non-zero residuals.

- [ ] **Step 12.4: Commit.**

```bash
git add src/dbt/kipptaf/models/marts/bridges/bridge_assessment_expectations_student_scoped.sql \
        src/dbt/kipptaf/models/marts/bridges/properties/bridge_assessment_expectations_student_scoped.yml
git commit -m "feat(dbt): add bridge_assessment_expectations_student_scoped

Refs #3640."
```

### Task 13 — Delete `dim_student_assessment_expectations`; update `cube.yml`

**Files:**

- Delete:
  `src/dbt/kipptaf/models/marts/dimensions/dim_student_assessment_expectations.sql`
- Delete:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_student_assessment_expectations.yml`
- Modify: `src/dbt/kipptaf/models/exposures/cube.yml`

- [ ] **Step 13.1: Confirm zero non-cube consumers.**

```bash
grep -rn "dim_student_assessment_expectations" src/dbt/ --include="*.sql" --include="*.yml" | grep -v "/target/" | grep -v "dim_student_assessment_expectations\.\(sql\|yml\):"
```

Expected: only `cube.yml` line 35 (already verified during brainstorming).

- [ ] **Step 13.2: Update `cube.yml`.** Replace the
      `ref("dim_student_assessment_expectations")` line with two refs:

```yaml
- ref("bridge_assessment_expectations_enrollment_scoped")
- ref("bridge_assessment_expectations_student_scoped")
```

- [ ] **Step 13.3: Delete the old dim files.**

```bash
git rm src/dbt/kipptaf/models/marts/dimensions/dim_student_assessment_expectations.sql \
       src/dbt/kipptaf/models/marts/dimensions/properties/dim_student_assessment_expectations.yml
```

- [ ] **Step 13.4: Parse and verify.**

```bash
uv run dbt parse --target dev --project-dir src/dbt/kipptaf
```

Expected: no errors; dropped node disappears from the manifest; new bridge nodes
present.

- [ ] **Step 13.5: Commit.**

```bash
git add src/dbt/kipptaf/models/exposures/cube.yml
git commit -m "refactor(dbt): replace dim_student_assessment_expectations with bridges

The dim was a factless many-to-many mislabeled as a dim, with two
distinct grains conflated (internal-assessment with section context vs.
external-assessment without). Adding student_section_enrollment_key
would have introduced two diamond paths (to dim_terms and dim_students).
Splitting by is_internal_assessment removes the diamonds and renames
to bridge_* per project conventions. Cube exposure updated.

Refs #3640."
```

### Task 14 — Update `fct_assessment_scores_enrollment_scoped`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_enrollment_scoped.sql`
- Modify:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_assessment_scores_enrollment_scoped.yml`

The existing fact file produces R9-violating columns (`academic_year`,
`provider`) and uses `dbt_utils.deduplicate` as a workaround for upstream
`int_assessments__response_rollup` dups (resolved in Task 1). It also FKs to
`assessment_key` directly, which we're switching to
`assessment_administration_key`.

- [ ] **Step 14.1: Rewrite the SQL.** Drop the
      `internal_assessments_raw → internal_assessments` deduplicate wrapper
      (Task 1 deduplicates upstream); keep the state CTEs; switch the final
      SELECT to emit `assessment_administration_key` (built from the same
      composition as
      `dim_assessment_administrations.assessment_administration_key`); drop
      `academic_year` and `provider` from final SELECT.

```sql
with
    internal_assessments as (
        select
            powerschool_student_number as student_number,
            academic_year,
            scope,
            subject_area,
            module_code,
            region,
            title,
            assessment_id,
            response_type,
            response_type_id,
            response_type_code,
            performance_band_label,
            is_mastery,
            n_assessments,
            assessment_ids,

            cast(date_taken as date) as test_date,
            cast(administered_at as date) as administered_date,

            cast(null as numeric) as scale_score,

            percent_correct,

            performance_band_label as proficiency_level,
        from {{ ref("int_assessments__response_rollup") }}
        where is_internal_assessment
    ),

    state_nj as (
        select
            localstudentidentifier as student_number,
            academic_year,

            if(
                `subject` = 'English Language Arts/Literacy',
                'English Language Arts',
                `subject`
            ) as subject_area,

            discipline,

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
            testscalescore as scale_score,
            is_proficient,
            testperformancelevel_text as performance_band,
            testperformancelevel as performance_band_level,

            if(`period` = 'FallBlock', 'Fall', `period`) as administration_window,

            if(`period` = 'FallBlock', 'Fall', `period`) as season,

            assessment_name as title,

            initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_'))
            as region,

            cast(null as date) as test_date,
            cast(null as date) as administered_date,
            cast(null as numeric) as percent_correct,
        from {{ ref("int_pearson__all_assessments") }}
        where
            academic_year >= {{ var("current_academic_year") - 7 }}
            and testscalescore is not null
    ),

    state_fl as (
        select
            student_id as state_student_id,
            academic_year,
            assessment_subject as subject_area,
            discipline,
            test_code as module_code,
            cast(assessment_grade as int) as grade_level,
            scale_score,
            is_proficient,
            achievement_level as performance_band,
            performance_level as performance_band_level,
            administration_window,
            season,
            assessment_name as title,

            initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_'))
            as region,

            cast(null as date) as test_date,
            cast(null as date) as administered_date,
            cast(null as numeric) as percent_correct,
        from {{ ref("int_fldoe__all_assessments") }}
        where scale_score is not null
    ),

    state_union as (
        select
            nj.student_number,
            nj.academic_year,
            nj.subject_area,
            nj.discipline,
            nj.module_code,
            nj.grade_level,
            nj.scale_score,
            nj.is_proficient,
            nj.performance_band,
            nj.performance_band_level,
            nj.administration_window,
            nj.season,
            nj.title,
            nj.region,
            nj.test_date,
            nj.administered_date,
            nj.percent_correct,

            cast(null as string) as state_student_id,
        from state_nj as nj

        union all

        select
            cast(null as int64) as student_number,
            fl.academic_year,
            fl.subject_area,
            fl.discipline,
            fl.module_code,
            fl.grade_level,
            fl.scale_score,
            fl.is_proficient,
            fl.performance_band,
            fl.performance_band_level,
            fl.administration_window,
            fl.season,
            fl.title,
            fl.region,
            fl.test_date,
            fl.administered_date,
            fl.percent_correct,

            fl.state_student_id,
        from state_fl as fl
    )

/* internal assessments */
select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "ia.student_number",
                "ia.assessment_id",
                "TO_JSON_STRING(ia.assessment_ids)",
                "ia.response_type",
                "ia.response_type_id",
                "ia.response_type_code",
            ]
        )
    }} as assessment_score_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "'illuminate'",
                "ia.title",
                "ia.subject_area",
                "ia.scope",
                "ia.module_code",
                "cast(null as int64)",
                "ia.administered_date",
                "ia.academic_year",
                "cast(null as string)",
                "ia.region",
            ]
        )
    }} as assessment_administration_key,

    {{ dbt_utils.generate_surrogate_key(["ia.student_number"]) }} as student_key,

    ia.test_date as test_date_key,

    ia.scale_score,
    ia.percent_correct,
    ia.proficiency_level,
    ia.is_mastery,
from internal_assessments as ia

union all

/* state assessments */
select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "su.region",
                "coalesce(cast(su.student_number as string), su.state_student_id)",
                "su.academic_year",
                "su.administration_window",
                "su.subject_area",
            ]
        )
    }} as assessment_score_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "'state'",
                "su.title",
                "su.subject_area",
                "su.discipline",
                "su.module_code",
                "su.grade_level",
                "su.administered_date",
                "su.academic_year",
                "cast(null as string)",
                "su.region",
            ]
        )
    }} as assessment_administration_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "coalesce(cast(su.student_number as string), su.state_student_id)",
            ]
        )
    }} as student_key,

    su.test_date as test_date_key,

    su.scale_score,
    su.percent_correct,

    su.performance_band as proficiency_level,

    su.is_proficient as is_mastery,
from state_union as su
```

(Note: the `assessment_score_key` for state is rebuilt from
`region + student + AY + window + subject` — replaces the previous
`_dbt_source_relation`-based composition because the fact no longer carries
`_dbt_source_relation`. Verify the new composition is unique via the YAML
uniqueness test.)

- [ ] **Step 14.2: Update the YAML.** Drop `academic_year` and `provider`
      columns; rename `assessment_key` to `assessment_administration_key`;
      update the relationships test to point at
      `dim_assessment_administrations`:

```yaml
- name: assessment_administration_key
  data_type: string
  description: >-
    FK to dim_assessment_administrations. Joining lifts both the administration
    attributes (administered_date_key, season, region) and definition attributes
    (via dim_assessment_administrations → dim_assessments).
  constraints:
    - type: foreign_key
      to: ref('dim_assessment_administrations')
      to_columns: [assessment_administration_key]
      warn_unsupported: false
  data_tests:
    - relationships:
        arguments:
          to: ref('dim_assessment_administrations')
          field: assessment_administration_key
```

Remove the `academic_year` and `provider` column entries entirely.

- [ ] **Step 14.3: Build and test.**

```bash
uv run dbt build --select fct_assessment_scores_enrollment_scoped --target dev --defer --state=src/dbt/kipptaf/target/prod/ --project-dir src/dbt/kipptaf
```

Expected: passes uniqueness on `assessment_score_key`; new
`relationships → dim_assessment_administrations` test runs.

- [ ] **Step 14.3.5: Verify hash parity across dim, bridge, fact.** The existing
      `fct_assessment_scores_enrollment_scoped` internal-branch hash passes
      `cast(null as int64)` for the grade_level slot, while `dim_assessments`
      illuminate CTE passes the actual `grade_level`. This is a pre-existing FK
      inconsistency. Run:

```sql
SELECT
  (SELECT COUNT(*) FROM `teamster-332318.<dev_schema>.fct_assessment_scores_enrollment_scoped` f
    LEFT JOIN `teamster-332318.<dev_schema>.dim_assessment_administrations` d
    ON f.assessment_administration_key = d.assessment_administration_key
    WHERE d.assessment_administration_key IS NULL) AS fact_orphans,
  (SELECT COUNT(*) FROM `teamster-332318.<dev_schema>.bridge_assessment_expectations_enrollment_scoped` b
    LEFT JOIN `teamster-332318.<dev_schema>.dim_assessment_administrations` d
    ON b.assessment_administration_key = d.assessment_administration_key
    WHERE d.assessment_administration_key IS NULL) AS bridge_orphans;
```

If `fact_orphans > 0`, the fact's internal-branch hash does not match the dim.
Resolution: extend `int_assessments__response_rollup` (already in scope per Task
1's audit) to expose `grade_level_id`, then in Task 14 pass `ia.grade_level_id`
instead of `cast(null as int64)` in the internal branch's
`assessment_administration_key` composition. Same fix applies symmetrically:
dim_assessments / dim_assessment_administrations / both bridges / both facts
must pass the **same** value at the grade_level slot for any given logical
administration.

Document the chosen alignment (which value is canonical at the grade_level slot)
in the PR description and ensure all five hash sites are consistent. Re-run the
orphan count after alignment; expected: 0.

- [ ] **Step 14.4: Audit FK orphans.**

```sql
SELECT COUNT(*) AS n_orphans
FROM `teamster-332318.<dev_schema>.fct_assessment_scores_enrollment_scoped` AS f
LEFT JOIN `teamster-332318.<dev_schema>.dim_assessment_administrations` AS d
  ON f.assessment_administration_key = d.assessment_administration_key
WHERE d.assessment_administration_key IS NULL;
```

Expected: 0 (or known-residual to be fixed before merge).

- [ ] **Step 14.5: Commit.**

```bash
git add src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_enrollment_scoped.sql \
        src/dbt/kipptaf/models/marts/facts/properties/fct_assessment_scores_enrollment_scoped.yml
git commit -m "refactor(dbt): drop dedup workaround + R9 columns from fct_assessment_scores_enrollment_scoped

Drops dbt_utils.deduplicate (upstream int_assessments__response_rollup
now dedups). Drops academic_year (reachable via assessment_administration_key
or test_date_key) and provider (encoded in assessment_administration_key).
Switches FK from assessment_key to assessment_administration_key.

Refs #3628, #3640, #3646."
```

### Task 15 — Update `fct_assessment_scores_student_scoped`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_student_scoped.sql`
- Modify:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_assessment_scores_student_scoped.yml`

Same shape as Task 14: drop `dbt_utils.deduplicate` workaround on the college
branch (Task 2 deduplicates upstream), drop R9 columns (`academic_year`,
`provider`, `type`, `administration_round`, `test_type`), switch FK to
`assessment_administration_key`.

- [ ] **Step 15.1: Rewrite the SQL.** Read the current file first; the structure
      is two CTEs (`college_assessments_raw` → `college_assessments` deduped,
      plus `ap_assessments`). Drop the dedupe layer; rebuild final SELECTs with
      `assessment_administration_key` instead of `assessment_key`:

```sql
with
    college_assessments as (
        select
            student_number,
            academic_year,
            test_date,
            scope,
            subject_area,
            score_type,
            scale_score,
            administration_round,
            rn_highest,
            max_scale_score,
            superscore,
            running_max_scale_score,
            test_type,

            cast(null as numeric) as percent_correct,
        from {{ ref("int_assessments__college_assessment") }}
    ),

    ap_assessments as (
        select
            powerschool_student_number as student_number,
            academic_year,
            test_subject,
            exam_score,
            test_name,
            ps_ap_course_subject_code,
            ap_course_name,
            `data_source`,
            rn_highest,
        from {{ ref("int_assessments__ap_assessments") }}
    )

/* college entrance (SAT, ACT, PSAT) */
select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "ca.student_number",
                "ca.score_type",
                "ca.test_date",
                "ca.rn_highest",
            ]
        )
    }} as assessment_score_key,

    {{ dbt_utils.generate_surrogate_key(["ca.student_number"]) }} as student_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "'college'",
                "ca.scope",
                "ca.subject_area",
                "ca.scope",
                "ca.score_type",
                "cast(null as int64)",
                "ca.test_date",
                "ca.academic_year",
                "ca.administration_round",
                "cast(null as string)",
            ]
        )
    }} as assessment_administration_key,

    ca.test_date as test_date_key,

    ca.scale_score,
    ca.rn_highest as `rank`,
    ca.max_scale_score,
    ca.superscore,
    ca.running_max_scale_score,

    cast(null as string) as proficiency_level,
from college_assessments as ca

union all

/* AP exams */
select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "ap.student_number",
                "ap.ap_course_name",
                "ap.academic_year",
                "ap.rn_highest",
            ]
        )
    }} as assessment_score_key,

    {{ dbt_utils.generate_surrogate_key(["ap.student_number"]) }} as student_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "'college'",
                "concat('AP ', ap.test_subject)",
                "ap.test_subject",
                "'AP'",
                "ap.ps_ap_course_subject_code",
                "cast(null as int64)",
                "cast(null as date)",
                "ap.academic_year",
                "cast(null as string)",
                "cast(null as string)",
            ]
        )
    }} as assessment_administration_key,

    cast(null as date) as test_date_key,

    cast(ap.exam_score as numeric) as scale_score,

    ap.rn_highest as `rank`,

    cast(null as numeric) as max_scale_score,
    cast(null as numeric) as superscore,
    cast(null as numeric) as running_max_scale_score,

    case
        when ap.exam_score >= 3 then 'Qualified' else 'Not Qualified'
    end as proficiency_level,
from ap_assessments as ap
```

- [ ] **Step 15.2: Update the YAML.** Drop column entries: `academic_year`,
      `provider`, `type`, `administration_round`, `test_type`. Rename
      `assessment_key` entry to `assessment_administration_key` with the new
      relationships test target. Add backticks + `quote: true` to `rank`
      (BigQuery reserved word).

- [ ] **Step 15.3: Build, test, audit FK orphans, commit** (same pattern as Task
      14).

```bash
git add src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_student_scoped.sql \
        src/dbt/kipptaf/models/marts/facts/properties/fct_assessment_scores_student_scoped.yml
git commit -m "refactor(dbt): drop dedup workaround + R9 columns from fct_assessment_scores_student_scoped

Drops dbt_utils.deduplicate (upstream int_assessments__college_assessment
now dedups). Drops academic_year, provider, type, administration_round,
test_type (reachable via assessment_administration_key or test_date_key).
Switches FK from assessment_key to assessment_administration_key.

Refs #3628, #3640, #3646."
```

### Task 16 — Update `fct_survey_responses`

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/facts/fct_survey_responses.sql`
- Modify:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_survey_responses.yml`

- [ ] **Step 16.1: Drop the `dbt_utils.deduplicate()` block.** Replace the
      `deduped` CTE with a direct select from `all_responses`:

```sql
-- existing CTEs above unchanged through all_responses

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "survey_id",
                "survey_response_id",
                "respondent_identifier",
                "question_shortname",
            ]
        )
    }} as survey_response_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "survey_id",
                "survey_response_id",
                "respondent_identifier",
            ]
        )
    }} as survey_submission_key,

    {{ dbt_utils.generate_surrogate_key(["question_shortname"]) }}
    as survey_question_key,

    response_value,
    response_text,
from all_responses
```

- [ ] **Step 16.2: Build and test.**

```bash
uv run dbt build --select fct_survey_responses --target dev --defer --state=src/dbt/kipptaf/target/prod/ --project-dir src/dbt/kipptaf
```

- [ ] **Step 16.3: Verify #3766 relationships tests at 0.**

```bash
uv run dbt test --select fct_survey_responses --target dev --defer --state=src/dbt/kipptaf/target/prod/ --project-dir src/dbt/kipptaf
```

Expected:

- `relationships_fct_survey_responses_survey_question_key__survey_question_key__ref_dim_survey_questions_`
  returns 0 orphans (was 39K).
- `relationships_fct_survey_responses_survey_submission_key__survey_submission_key__ref_fct_survey_submissions_`
  returns 0 orphans (was 415K).

If either test still has orphans:

- For `survey_question_key`: investigate whether `dim_survey_questions` is
  missing question variants referenced by responses. Check whether the
  response's `question_shortname` is unique against
  `dim_survey_questions.shortname`.
- For `survey_submission_key`: investigate whether `fct_survey_submissions`
  filters out submissions that still appear in `fct_survey_responses` (e.g. a
  status / completeness filter). Open a follow-up task; document findings in the
  PR description.

- [ ] **Step 16.4: Promote relationships warnings to errors** in
      `properties/fct_survey_responses.yml` once both tests confirmed at 0:

```yaml
- name: survey_question_key
  # ...
  data_tests:
    - relationships:
        arguments:
          to: ref('dim_survey_questions')
          field: survey_question_key
        # promoted from warn now that #3766 is closed

- name: survey_submission_key
  # ...
  data_tests:
    - relationships:
        arguments:
          to: ref('fct_survey_submissions')
          field: survey_submission_key
        # promoted from warn now that #3766 is closed
```

(If the existing config has `severity: warn`, remove it; the project default is
`warn` for marts but we promote these specifically.)

- [ ] **Step 16.5: Commit.**

```bash
git add src/dbt/kipptaf/models/marts/facts/fct_survey_responses.sql \
        src/dbt/kipptaf/models/marts/facts/properties/fct_survey_responses.yml
git commit -m "refactor(dbt): drop dedup workaround from fct_survey_responses

Upstream int_surveys__survey_responses now dedups. Promotes #3766
relationships tests on survey_question_key and survey_submission_key —
both at 0 orphans after this PR's catalog refactor.

Refs #3629, #3766."
```

### Task 17 — Spec doc edits (#3648 comparisons + column-naming audit hash entries)

**Files:**

- Modify: existing star-schema spec doc (path discovered in Step 17.1)
- Modify: `docs/superpowers/specs/2026-04-15-column-naming-audit.md`

- [ ] **Step 17.1: Locate the star-schema spec.**

```bash
grep -rln "dim_assessment_comparisons" docs/superpowers/specs/ | head
```

- [ ] **Step 17.2: Remove the `dim_assessment_comparisons → dim_assessments` FK
      requirement** from the spec. Replace the FK row in the spec table with a
      note explaining that comparisons live at region × test × academic_year
      grain (no `grade_level`) and cannot FK to `dim_assessments` at definition
      grain or `dim_assessment_administrations` at per-occurrence grain.

- [ ] **Step 17.3: Add hash-change entries** to the column-naming audit's
      "Enumerated surrogate-key changes" table in
      `docs/superpowers/specs/2026-04-15-column-naming-audit.md`:

```markdown
| `dim_assessment_administrations.assessment_administration_key` | structural
add (#5) — new dim | n/a |
`(assessment_type, title, subject_area, scope, module_code, grade_level, administered_date, academic_year, administration_round, region)`
| |
`bridge_assessment_expectations_enrollment_scoped.assessment_expectation_key` |
structural add (#5) — replaces deleted
`dim_student_assessment_expectations.student_assessment_expectation_key` |
`(student_number, assessment_id, administered_at)` |
`(cc_dcid, cc_source_relation, assessment_id, administered_at)` | |
`bridge_assessment_expectations_student_scoped.assessment_expectation_key` |
structural add (#5) — replaces deleted
`dim_student_assessment_expectations.student_assessment_expectation_key` |
`(student_number, assessment_id, administered_at)` |
`(student_key, assessment_administration_key)` | |
`fct_assessment_scores_enrollment_scoped.assessment_score_key` (state branch) |
composition change (#3) — replaces `_dbt_source_relation` with `region` |
`(_dbt_source_relation, student/state_id, academic_year, administration_window, subject_area)`
|
`(region, student/state_id, academic_year, administration_window, subject_area)`
|
```

(Verify the hashes in the table match the actual `generate_surrogate_key()`
calls in Tasks 7, 11, 12, 14.)

- [ ] **Step 17.4: Commit the doc edits.**

```bash
git add docs/superpowers/specs/<star-schema-spec-path> docs/superpowers/specs/2026-04-15-column-naming-audit.md
git commit -m "docs(spec): drop dim_assessment_comparisons FK; record hash changes

Comparisons can't FK to dim_assessments (no grade_level on comparisons
sheet — coarser grain than the dim) or to dim_assessment_administrations
(no administered_date either). Spec updated. Column-naming audit gains
3 hash-change entries for the new dim/bridges and one for the state-
branch assessment_score_key composition change.

Closes #3648 (comparisons half)."
```

### Task 18 — Final pre-push validation

- [ ] **Step 18.1: Confirm Paterson sheet edit (#3737) has been applied.** Ask
      Ops to verify the Paterson 2026-02-02 RT row's `school_id` matches the
      canonical Paterson PowerSchool school_id used in the scaffold (1234 vs 2 —
      confirm with Ops which is canonical and edit to align).

After confirmation, rebuild the staging:

```bash
uv run dbt build --select stg_google_sheets__reporting__terms+1 --exclude resource_type:test --target dev --defer --state=src/dbt/kipptaf/target/prod/ --project-dir src/dbt/kipptaf
```

Then re-run the bridge tests:

```bash
uv run dbt test --select bridge_assessment_expectations_student_scoped --target dev --defer --state=src/dbt/kipptaf/target/prod/ --project-dir src/dbt/kipptaf
```

Expected: term_key relationships test at 0 orphans.

- [ ] **Step 18.2: Build the full impacted slice end-to-end.**

```bash
uv run dbt build --select state:modified+ --target dev --defer --state=src/dbt/kipptaf/target/prod/ --project-dir src/dbt/kipptaf --full-refresh
```

Expected: every model passes; relationships warnings on `fct_survey_responses`
at 0.

- [ ] **Step 18.3: Run the project linter.**

```bash
/workspaces/teamster/.trunk/tools/trunk check --ci
```

Fix any issues. Re-run until clean.

- [ ] **Step 18.4: Push the branch.**

```bash
git push -u origin cbini/feat/claude-batch-f-assessment-survey-catalog
```

- [ ] **Step 18.5: Open the PR.** Use the project's PR template; in the body
      include:
  - Closes #3628, #3629, #3640, #3646, #3736, #3766; partial close #3648
    (comparisons half).
  - Audit table per non-additive change (Tasks 1, 2, 3, 4): pre-count,
    post-count, expected delta, observed delta, status.
  - Diamond walk: enumerate FKs on each modified mart and verify no two FKs lead
    to the same ancestor dim through different chains. Note `test_date_key` vs
    `administered_date_key` as role-disambiguated date FKs (not a diamond).
  - Note that #3737 sheet edit was an Ops prerequisite; document the cell that
    was changed.
  - Note that #3648 targets is carved out into a follow-up issue gated on Ops
    adding a `Test_Program` column to the academic_goals sheet.

```bash
gh pr create --title "feat(dbt): batch F — assessment/survey catalog refactor + bridge restructure" \
  --body "$(cat <<'EOF'
## Summary

7-issue batch landing the assessment/survey catalog work for Cube prerequisites.

Closes:
- #3628 (dedup int_assessments__response_rollup + int_assessments__college_assessment)
- #3629 (dedup int_surveys__survey_responses)
- #3640 (replace dim_student_assessment_expectations with two grain-clean bridges)
- #3646 (eliminate response-grain DISTINCT workarounds; introduce dim_assessment_administrations)
- #3736 (populate region in int_assessments__scaffold)
- #3737 (Paterson 2026-02-02 sheet edit applied by Ops)
- #3766 (verify fct_survey_responses FK gaps at 0)

Partial close:
- #3648 — comparisons half resolved as spec edit; targets half carved into follow-up issue.

## Audit table

[Insert non-additive change audit table from PR description spec section]

## Diamond walk

[Insert FK enumeration per modified mart]

## Test plan

- [ ] dbt build state:modified+ passes
- [ ] All relationships tests for fct_survey_responses at 0
- [ ] FK orphan count for new bridges at 0
- [ ] Trunk check --ci clean

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-review note

After applying this plan, run `dbt parse --target dev` to verify the manifest,
and do a final pass over the worktree's diff against `main` to confirm:

1. No unintended file modifications outside the listed touch list.
2. Every new model has a properties YAML with `unique` and `not_null` on PK plus
   `relationships` tests on FKs.
3. Every modified intermediate keeps its uniqueness test.
4. The two bridges live under `marts/bridges/`, not `marts/dimensions/`.
5. No `_dbt_source_relation` reaches a mart SELECT (R8).
