# Batch F — assessment / survey catalog design

Implementation design for
[PR batch F](https://github.com/orgs/TEAMSchools/projects/4) of the Cube
prerequisite work: assessment and survey catalog refactor, source dedup,
scaffold enhancements, and bridge restructuring.

## Issues addressed

| Issue                                                                           | Title                                                                              | Resolution in this PR                                                                                                      |
| ------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| [#3646](https://github.com/TEAMSchools/teamster/issues/3646)                    | definition-grain catalog intermediates for `dim_assessments` and `dim_surveys`     | catalog ints + new `dim_assessment_administrations` (parallels `dim_survey_administrations`)                               |
| [#3628](https://github.com/TEAMSchools/teamster/issues/3628)                    | dedup `int_assessments__response_rollup` and `int_assessments__college_assessment` | dedup at originating layer; remove `dbt_utils.deduplicate()` workarounds in facts                                          |
| [#3629](https://github.com/TEAMSchools/teamster/issues/3629)                    | dedup `int_surveys__survey_responses`                                              | dedup at originating layer; remove fact workaround                                                                         |
| [#3766](https://github.com/TEAMSchools/teamster/issues/3766)                    | `fct_survey_responses` FK gaps (39K + 415K)                                        | verify gaps close after #3646 + #3629; root-cause residual if any                                                          |
| [#3736](https://github.com/TEAMSchools/teamster/issues/3736)                    | `int_assessments__scaffold.region` NULL on 1.6M rows                               | populate `region` from `powerschool_school_id` via location crosswalk                                                      |
| [#3640](https://github.com/TEAMSchools/teamster/issues/3640)                    | `student_section_enrollment_key` FK on `dim_student_assessment_expectations`       | split dim into two grain-clean bridges (rename + restructure)                                                              |
| [#3737](https://github.com/TEAMSchools/teamster/issues/3737)                    | Paterson 2026-02-02 term gap (~105 rows)                                           | Ops corrects RT sheet cell; rebuild stg before merge                                                                       |
| [#3648](https://github.com/TEAMSchools/teamster/issues/3648) (comparisons half) | `dim_assessment_comparisons → dim_assessments` FK                                  | spec doc edit only — drop FK requirement; comparisons grain is region × test × year, no `grade_level`                      |
| [#3648](https://github.com/TEAMSchools/teamster/issues/3648) (targets half)     | `dim_assessment_targets → dim_assessments` FK crosswalk                            | **out of scope** — gated on Ops adding a `Test_Program` column to the academic_goals sheet. Carved into a follow-up issue. |

## Non-mart-breakage invariant

Every change in `staging/` or `intermediate/` must be either additive (new
column or model) or come with verification that all downstream consumers produce
identical output. Any non-additive change requires a documented downstream
audit.

| Change                                                                      | Layer          | Additive?                      | Audit                                                                       |
| --------------------------------------------------------------------------- | -------------- | ------------------------------ | --------------------------------------------------------------------------- |
| 7 new catalog ints                                                          | new int models | yes                            | none                                                                        |
| dedup `int_assessments__response_rollup`                                    | int            | no — row count drops           | clone prod consumer baseline; row-count + checksum diff per direct consumer |
| dedup `int_assessments__college_assessment`                                 | int            | no                             | same                                                                        |
| dedup `int_surveys__survey_responses`                                       | int            | no                             | same                                                                        |
| populate `region` in scaffold                                               | int            | no — NULL → value on 1.6M rows | enumerate scaffold consumers; verify none use `region IS NULL` as a flag    |
| add `cc_dcid` + `_dbt_source_relation` to scaffold + course_enrollments int | int            | yes                            | confirm no `dbt_utils.star()` consumer breaks on column add                 |
| Paterson sheet cell                                                         | source data    | n/a                            | n/a                                                                         |
| spec doc edits                                                              | doc            | n/a                            | n/a                                                                         |
| catalog cutover (mart side)                                                 | mart           | by definition the mart change  | covered by mart contract + downstream exposure tests                        |

Audit results are recorded in the PR description as a table per non-additive
change: pre-count, post-count, expected delta, observed delta, status.

## Architecture

### New intermediates

`assessments/intermediate/`:

- `int_assessments__illuminate_catalog.sql` — definition × administration grain
  from `int_assessments__response_rollup`
- `int_assessments__pearson_catalog.sql` — from `int_pearson__all_assessments`
- `int_assessments__fldoe_catalog.sql` — from `int_fldoe__all_assessments`
- `int_assessments__college_assessment_catalog.sql` — from
  `int_assessments__college_assessment`; carries `administration_round`,
  `test_type`
- `int_assessments__ap_assessments_catalog.sql` — from
  `int_assessments__ap_assessments`; carries `test_type`

All five at the same composite grain (the `dim_assessments` PK composition; see
below). Each has a `unique_combination_of_columns` test on that grain.

`surveys/intermediate/`:

- `int_surveys__alchemer_survey_catalog.sql` — survey-grain (one row per survey
  definition)
- `int_surveys__alchemer_question_catalog.sql` — question-grain (one row per
  question on a survey)

### Modified intermediates

`assessments/intermediate/`:

- `int_assessments__scaffold.sql`
  - populate `region` from `powerschool_school_id` via
    `int_people__location_crosswalk` in the K-8-replacement and "all other
    assessments" UNION branches (#3736)
  - thread `cc_dcid` and `_dbt_source_relation` through the
    `internal_assessments` CTE so the bridge can hash a
    `student_section_enrollment_key` (#3640)
- `int_assessments__course_enrollments.sql`
  - expose `cc_dcid` and `_dbt_source_relation` (additive; #3640)
- `int_assessments__response_rollup.sql` — dedup at originating layer (or push
  to staging if spike shows raw dups; #3628)
- `int_assessments__college_assessment.sql` — dedup at originating layer (#3628)

`surveys/intermediate/`:

- `int_surveys__survey_responses.sql` — dedup at originating layer (#3629)

### `dim_assessments` + new `dim_assessment_administrations`

`dim_assessments` stays definition-grain. A new `dim_assessment_administrations`
carries the per-scheduled-occurrence attributes, parallel to the existing
`dim_survey_administrations`. Source-system multi-administration patterns are
heterogeneous (Illuminate: per-region per-AY; state: per-AY per-window; College
Board: per-sitting; AP: per-AY) — splitting keeps each dim grain-clean rather
than forcing a heterogeneous PK composition onto `dim_assessments`.

```text
dim_assessments  (definition grain)
  PK: assessment_key = hash(source, type, title, subject_area, scope,
                            module_code, grade_level)
  attrs: source, type, title, academic_subject, category, module_code,
         module_type, grade_level_tested, is_internal_assessment, scope,
         combined_academic_subject, aligned_academic_subject, credit_category
  (no administered_date, no academic_year, no administration_round, no test_type)

dim_assessment_administrations  (per scheduled occurrence)
  PK: assessment_administration_key = hash(assessment_key, administered_date,
                                           academic_year, administration_round,
                                           region)
  FKs: assessment_key, administered_date_key
  attrs: academic_year, administration_round, season, administration_window,
         test_type, region
```

Where `source` in `assessment_key` is the catalog-int identifier
(`'illuminate'`, `'state_nj'`, `'state_fl'`, `'college'`, `'ap'`).

Layer responsibility rule (load-bearing): **anything originating from
`int_assessments__assessments` terminates at `dim_assessments` or
`dim_assessment_administrations`** — definition attributes on the former,
scheduled-occurrence attributes on the latter. Downstream facts and bridges
carry only measures and FKs.

### Bridge split — replaces `dim_student_assessment_expectations`

The current `dim_student_assessment_expectations` is a factless many-to-many
bridge mislabeled as a dim. Adding `student_section_enrollment_key` to it would
create two diamond paths (to `dim_terms` via section enrollment, to
`dim_students` via section → enrollment). Splitting by `is_internal_assessment`
removes the diamond.

Naming mirrors the assessment fact pair
(`fct_assessment_scores_enrollment_scoped`,
`fct_assessment_scores_student_scoped`):

```text
marts/bridges/bridge_assessment_expectations_enrollment_scoped.sql
  PK: assessment_expectation_key = hash(student_section_enrollment_key,
                                         assessment_administration_key)
  FKs: assessment_administration_key, student_section_enrollment_key
  source: scaffold rows where is_internal_assessment AND NOT is_replacement
  no other columns

marts/bridges/bridge_assessment_expectations_student_scoped.sql
  PK: assessment_expectation_key = hash(student_key, assessment_administration_key)
  FKs: assessment_administration_key, student_key, term_key
  source: scaffold rows where NOT is_internal_assessment OR is_replacement
  no other columns
```

R9 cleanup applied:

- `academic_year` dropped (reachable via
  `assessment_administration_key → dim_assessment_administrations.academic_year`;
  also via `term_key` on student-scoped)
- `administered_date` dropped (reachable via
  `assessment_administration_key → dim_assessment_administrations.administered_date_key → dim_dates`)
- `is_internal_assessment` dropped (reachable via
  `assessment_administration_key → assessment_key → dim_assessments.is_internal_assessment`;
  also encoded by which bridge holds the row)

The old `dim_student_assessment_expectations.sql` and its YAML are deleted.
`cube.yml` exposure updated to `ref()` both new bridges.

### Assessment-fact R9 cleanup

`fct_assessment_scores_enrollment_scoped` final SELECT:

- Keep: `assessment_score_key`, `assessment_administration_key`, `student_key`,
  `test_date_key`, `scale_score`, `percent_correct`, `proficiency_level`,
  `is_mastery`
- Drop: `assessment_key` (replaced by `assessment_administration_key`),
  `academic_year`, `provider`

`fct_assessment_scores_student_scoped` final SELECT:

- Keep: `assessment_score_key`, `assessment_administration_key`, `student_key`,
  `test_date_key`, `scale_score`, `rank`, `max_scale_score`, `superscore`,
  `running_max_scale_score`, `proficiency_level`
- Drop: `assessment_key`, `academic_year`, `provider`, `type`,
  `administration_round`, `test_type`

`administration_round`, `season`, `administration_window`, `test_type` move
upstream to the catalog ints and surface on `dim_assessment_administrations`.

`test_date_key` (on the fact) and `administered_date_key` (on
`dim_assessment_administrations`) are role-disambiguated date FKs per the marts
CLAUDE.md `created_date_key`/`solved_date_key` convention. They reach different
`dim_dates` rows for internal assessments (`test_date` is when the student took
it; `administered_date` is when the assessment was scheduled). Not a diamond —
two distinct roles.

Both facts also lose their `dbt_utils.deduplicate()` workaround — the dedup now
lives at the originating int layer (#3628).

### Survey-side mart cleanup

- `dim_surveys.sql` — pass-through select from
  `int_surveys__alchemer_survey_catalog`; no `DISTINCT`
- `dim_survey_questions.sql` — pass-through select from
  `int_surveys__alchemer_question_catalog`; no `DISTINCT`
- `bridge_survey_questions.sql` — built directly from question catalog (which
  carries the survey FK)
- `fct_survey_responses.sql` — drops `dbt_utils.deduplicate()` workaround
  (#3629)

### Spec doc edit (#3648 comparisons)

The star schema spec entry for `dim_assessment_comparisons` is updated to remove
the `assessment_key` FK requirement. Comparisons live at region × test ×
academic_year grain (no `grade_level`); they cannot FK to `dim_assessments` at
the definition grain or to `dim_assessment_administrations` at the
per-occurrence grain.

## Build phasing

Each phase ends at a green-tests checkpoint before the next begins.

1. **Catalog intermediates (additive only)** — add 5 assessment + 2 survey
   catalog ints. Build, test, parse. No existing model touched. Marts produce
   identical output. New ints pass uniqueness on definition-administration
   grain.
2. **Source dedup (non-additive; per-change audit)** — spike each
   (response_rollup, college_assessment, survey_responses); apply dedup at
   originating layer; run the downstream audit. Mart workarounds NOT yet
   removed.
3. **Scaffold enhancements** — populate `region`; thread `cc_dcid` +
   `_dbt_source_relation`. Audit scaffold consumers.
4. **Mart cutover**
   - 4a. `dim_assessments` switches to definition-grain catalog union; new
     `dim_assessment_administrations` materializes from the same catalogs at
     per-occurrence grain
   - 4b. `dim_surveys`, `dim_survey_questions`, `bridge_survey_questions` switch
     to catalogs
   - 4c. New `bridge_assessment_expectations_enrollment_scoped` +
     `bridge_assessment_expectations_student_scoped`; delete old
     `dim_student_assessment_expectations`; update `cube.yml`
   - 4d. `fct_assessment_scores_*` and `fct_survey_responses` drop dedup
     workarounds and R9-violating columns
   - 4e. Spec doc edit removes the
     `dim_assessment_comparisons → dim_assessments` FK
   - 4f. Verify #3766 relationships tests return 0 rows (39K + 415K orphans). If
     `survey_submission_key` gap remains, root-cause inside this phase as a
     sub-investigation.

Out-of-band prerequisite: Ops corrects the Paterson RT sheet cell (#3737);
`stg_google_sheets__reporting__terms` rebuilt before final tests run.

## Surrogate-key hash changes

Per `kipptaf/marts/CLAUDE.md` discipline, the following hash changes are
recorded in the column-naming audit's "Enumerated surrogate-key changes" table:

| Key                                                                           | Reason                                                                                                          | Old composition                                                        | New composition                                                                    |
| ----------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `dim_assessments.assessment_key`                                              | composition change (#3)                                                                                         | `('illuminate', title, subject_area, scope, module_code, grade_level)` | `(source, title, subject_area, scope, module_code, grade_level)`                   |
| `dim_assessment_administrations.assessment_administration_key`                | structural add (#5) — new dim                                                                                   | n/a                                                                    | `(assessment_key, administered_date, academic_year, administration_round, region)` |
| `bridge_assessment_expectations_enrollment_scoped.assessment_expectation_key` | structural add (#5) — replaces deleted `dim_student_assessment_expectations.student_assessment_expectation_key` | `(student_number, assessment_id, administered_at)`                     | `(student_section_enrollment_key, assessment_administration_key)`                  |
| `bridge_assessment_expectations_student_scoped.assessment_expectation_key`    | structural add (#5) — replaces deleted `dim_student_assessment_expectations.student_assessment_expectation_key` | `(student_number, assessment_id, administered_at)`                     | `(student_key, assessment_administration_key)`                                     |

`assessment_key` consumers (facts, bridges) migrate to
`assessment_administration_key` — the FK rename cascades in lockstep with the
catalog cutover in phase 4a.

## Testing

Three layers:

**Per-model uniqueness + contract:**

- Each new catalog int gets `dbt_utils.unique_combination_of_columns` on the
  definition-administration composite.
- Both new bridges get `unique` + `not_null` on PK and `relationships` tests on
  every FK.
- Marts inherit `contract: enforced: true` from `dbt_project.yml`.

**Relationships tests for #3766 close signal:**

- Existing `fct_survey_responses → dim_survey_questions` (39K) and
  `→ fct_survey_submissions` (415K) tests stay; phase 4 success is both at 0.
- `bridge_assessment_expectations_enrollment_scoped.student_section_enrollment_key → dim_student_section_enrollments`
  test added (severity `error` since the bridge only holds rows where the FK is
  non-null by construction).

**Downstream invariance audit (the non-mart-breakage gate):**

For each non-additive int/staging change, before the mart cutover phase:

```sql
-- baseline (clone from prod)
dbt clone --select <consumer>+ --target dev

-- with change applied, build the same selectors
dbt build --select <consumer> --target dev

-- diff per consumer
select count(*) as n, to_hex(md5(string_agg(<pk> order by <pk>))) as ck
from <table>
```

Diffs must be zero or exactly the intended dup-removal count. Recorded per
change in the PR description.

**Diamond-walk audit (manual, recorded in PR):**

For every modified mart, enumerate the FKs it carries and verify no two FKs lead
to the same ancestor dim through different chains. The two new bridges and
`dim_assessment_administrations` are diamond-clean by construction. The two
facts have role-disambiguated date FKs (`test_date_key` direct +
`administered_date_key` via `dim_assessment_administrations`); not a diamond per
the role-playing convention since the two FKs reach different `dim_dates` rows.

Generalizing diamond detection (a custom macro that walks `manifest.json`
constraints) is out of scope; tracked as a follow-up issue.

## Out of scope

- **#3648 targets half** — needs Ops to add a `Test_Program` column to the
  academic_goals sheet, or a spec change accepting a coarser composite key.
  Carved into a follow-up issue.
- **`dim_*` → `bridge_*` rename for other mislabeled bridges** — only the
  assessment-expectations dim is touched here. Audit of the rest is separate
  work.
- **Manifest-walking diamond-detection macro** — separate issue.
- **Cube model definitions** — Cube hasn't been built yet; the entire batch F
  project exists to prepare for it.

## File touch list

New:

- `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__illuminate_catalog.{sql,yml}`
- `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__pearson_catalog.{sql,yml}`
- `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__fldoe_catalog.{sql,yml}`
- `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__college_assessment_catalog.{sql,yml}`
- `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__ap_assessments_catalog.{sql,yml}`
- `src/dbt/kipptaf/models/surveys/intermediate/int_surveys__alchemer_survey_catalog.{sql,yml}`
- `src/dbt/kipptaf/models/surveys/intermediate/int_surveys__alchemer_question_catalog.{sql,yml}`
- `src/dbt/kipptaf/models/marts/bridges/bridge_assessment_expectations_enrollment_scoped.{sql,yml}`
- `src/dbt/kipptaf/models/marts/bridges/bridge_assessment_expectations_student_scoped.{sql,yml}`
- `src/dbt/kipptaf/models/marts/dimensions/dim_assessment_administrations.{sql,yml}`

Modified:

- `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__scaffold.sql`
- `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__course_enrollments.sql`
- `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__response_rollup.sql`
- `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__college_assessment.sql`
- `src/dbt/kipptaf/models/surveys/intermediate/int_surveys__survey_responses.sql`
- `src/dbt/kipptaf/models/marts/dimensions/dim_assessments.{sql,yml}`
- `src/dbt/kipptaf/models/marts/dimensions/dim_surveys.{sql,yml}`
- `src/dbt/kipptaf/models/marts/dimensions/dim_survey_questions.{sql,yml}`
- `src/dbt/kipptaf/models/marts/bridges/bridge_survey_questions.{sql,yml}`
- `src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_enrollment_scoped.{sql,yml}`
- `src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_student_scoped.{sql,yml}`
- `src/dbt/kipptaf/models/marts/facts/fct_survey_responses.{sql,yml}`
- `src/dbt/kipptaf/models/exposures/cube.yml`
- existing star-schema spec doc (remove
  `dim_assessment_comparisons → dim_assessments` FK)
- column-naming audit spec doc (add 4 hash-change entries)

Deleted:

- `src/dbt/kipptaf/models/marts/dimensions/dim_student_assessment_expectations.sql`
- `src/dbt/kipptaf/models/marts/dimensions/properties/dim_student_assessment_expectations.yml`
