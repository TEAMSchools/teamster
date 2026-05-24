# Push entity-grain projections from marts into intermediate (#3780)

## Problem

Five mart models in `marts/` collapse response-grain (or per-score-grain) rows
into entity-grain rows using `SELECT DISTINCT` or `GROUP BY` aggregates. This
violates `src/dbt/CLAUDE.md` "No manual deduplication" and "Canonical attributes
from a partition." The collapse belongs in intermediates so marts can read
pre-projected, entity-grain rows.

Affected marts (per
[#3780](https://github.com/TEAMSchools/teamster/issues/3780)):

- `dim_assessments`
- `dim_assessment_administrations` (non-illuminate CTEs only — illuminate is
  tracked separately under TODO #3800)
- `dim_survey_questions`
- `dim_surveys`
- `bridge_survey_questions`

## Investigation: per-CTE source-grain audit

Before deciding whether to build new intermediates, each DISTINCT/GROUP BY CTE
was audited against its source's actual grain. Three resolutions emerged:
**drop** (source is already unique, DISTINCT is defensive), **redirect** (an
entity-grain upstream already exists), or **build new int** (the source is
genuinely response/score grain with no entity-grain sibling).

### Assessments group

| Mart CTE                                    | Source                                         | Source grain                                                                                                        | Resolution                                                              |
| ------------------------------------------- | ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| `dim_assessments.illuminate_assessments`    | `int_assessments__assessments`                 | `assessment_id` (unique test)                                                                                       | **Drop stale comment.** No DISTINCT is currently used; comment is stale |
| `dim_assessments.state_nj`                  | `int_pearson__all_assessments`                 | per-student-per-assessment response                                                                                 | **Build new int** at assessment-definition grain                        |
| `dim_assessments.state_fl`                  | `int_fldoe__all_assessments`                   | per-student-per-assessment response                                                                                 | **Build new int** at assessment-definition grain                        |
| `dim_assessments.college_assessments`       | `int_assessments__college_assessment`          | per-student-per-test-date (has `surrogate_key` column)                                                              | **Build new int** at definition grain                                   |
| `dim_assessments.practice_assessments`      | `int_assessments__college_assessment_practice` | per-student-per-test response                                                                                       | **Build new int** at definition grain                                   |
| `dim_assessments.ap_assessments`            | `int_assessments__ap_assessments`              | per-student-per-exam (model carries `row_number() over (partition by student, ap_course_name order by exam_score)`) | **Build new int** at definition grain                                   |
| `dim_assessment_administrations.state_nj_*` | `int_pearson__all_assessments`                 | per-student response                                                                                                | **Build new int** at administration grain                               |
| `dim_assessment_administrations.state_fl_*` | `int_fldoe__all_assessments`                   | per-student response                                                                                                | **Build new int** at administration grain                               |
| `dim_assessment_administrations.college_*`  | `int_assessments__college_assessment`          | per-student-per-test-date                                                                                           | **Build new int** at administration grain                               |
| `dim_assessment_administrations.ap_*`       | `int_assessments__ap_assessments`              | per-student-per-exam                                                                                                | **Build new int** at administration grain                               |

Net: **9 new intermediates** + remove one stale comment block.

### Surveys group

The surveys-side investigation surfaced that all four current
DISTINCT-collapsing CTEs in `dim_survey_questions` (and their bridge / dim
counterparts) can resolve to **redirect** or **drop** — no new intermediates
required.

| Mart CTE                                        | Current source                                                                      | Entity-grain upstream that already exists                                                                                                            | Resolution                                                                                                                                                                                                        |
| ----------------------------------------------- | ----------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `dim_survey_questions.google_forms_questions`   | `int_google_forms__form_responses` (response grain)                                 | `int_google_forms__form__items` (item / question grain — carries `form_id`, `item_abbreviation`, `item_title`, `question_kind`, `question_required`) | **Redirect** to `int_google_forms__form__items`                                                                                                                                                                   |
| `dim_survey_questions.scd_questions`            | `stg_google_sheets__surveys__scd_question_crosswalk`                                | Already at question grain (BQ check: 10 rows = 10 distinct `question_code` values in the `School_Survey_%` filter)                                   | **No-op** — mart CTE already uses plain `SELECT`, no DISTINCT to remove                                                                                                                                           |
| `dim_survey_questions.alchemer_questions`       | `int_surveys__survey_responses` (response grain — union of Google Forms + Alchemer) | `stg_alchemer__survey_question` (per-`(survey_id, id)` grain, carries `shortname`, `title_english`)                                                  | **Redirect** to `stg_alchemer__survey_question`, scoped to Alchemer questions only. Google Forms questions in this CTE are now covered by the gforms redirect above                                               |
| `dim_survey_questions.manager_questions`        | `int_surveys__manager_survey_details` (response grain)                              | Manager Survey is Google Form `'1cvp9RnYxbn-WGLXsYSupbEl2KhVhWKcOFbHR2CgUBH0'`; its questions are already in `int_google_forms__form__items`         | **Drop** the CTE entirely. Coverage is redundant once gforms redirect lands. Per the post-#3899 comment in `int_surveys__manager_survey_details`, live Manager Survey identity already flows through Google Forms |
| `dim_surveys.google_forms_surveys`              | `int_google_forms__form_responses` (response grain)                                 | `stg_google_forms__form` (form / survey grain — carries `form_id`, `info_title`)                                                                     | **Redirect** to `stg_google_forms__form`                                                                                                                                                                          |
| `dim_surveys.alchemer_surveys`                  | `source("alchemer", "base_alchemer__survey_results")` (response grain)              | `stg_alchemer__survey` (per-`id` survey grain, carries `id` and title)                                                                               | **Redirect** to `stg_alchemer__survey`                                                                                                                                                                            |
| `bridge_survey_questions.google_forms_pairs`    | `int_google_forms__form_responses`                                                  | `int_google_forms__form__items` carries `(form_id, item_abbreviation, question_required)`                                                            | **Redirect** to `int_google_forms__form__items`                                                                                                                                                                   |
| `bridge_survey_questions.alchemer_pairs`        | `int_surveys__survey_responses`                                                     | `stg_alchemer__survey_question` carries `(survey_id, shortname)`                                                                                     | **Redirect** to `stg_alchemer__survey_question`                                                                                                                                                                   |
| `bridge_survey_questions.manager_pairs`         | `int_surveys__manager_survey_details`                                               | Subset of Google Forms after the gforms redirect                                                                                                     | **Drop** the CTE entirely                                                                                                                                                                                         |
| `bridge_survey_questions.scd_powerschool_pairs` | `stg_google_sheets__surveys__scd_question_crosswalk`                                | Already at question grain (see above)                                                                                                                | **No-op** — already uses plain `SELECT`                                                                                                                                                                           |

Net: **0 new intermediates**, 6 redirects (gforms ×3, alchemer ×3), 2 redundant
CTEs dropped, 2 no-ops on SCD CTEs (no DISTINCT was present).

Mart-side aggregate impact: the surveys trio loses 6 `SELECT DISTINCT`
occurrences, the manager arms simplify away entirely, and the gforms / alchemer
arms become plain `SELECT col, col ... FROM <entity-grain-model>`.

## Architecture

### Mart-side rewrites

All five marts switch their affected CTEs from response-grain `SELECT DISTINCT`
(or `GROUP BY`-with-min) to plain `SELECT` from an entity-grain source — either
a new intermediate (assessments) or an existing entity-grain upstream (surveys).
Final mart `SELECT` columns, surrogate-key composition, and downstream FK shapes
do not change.

The stale `-- DISTINCT projects from response grain to definition grain` comment
block in `dim_assessments.illuminate_assessments` is removed — no DISTINCT is
actually present in the SQL, and the comment misleads readers.

### New assessment intermediates (9 total)

Each new intermediate:

- Lives next to its source model (`models/pearson/intermediate/`,
  `models/fldoe/intermediate/`, `models/assessments/intermediate/`)
- Is `materialized: view` (intermediate default)
- Uses `dbt_utils.deduplicate` with the entity key as `partition_by` and a
  deterministic `order_by` for any non-key column resolution
- Ships a `properties.yml` entry with `description:`, column descriptions, and a
  uniqueness test on the partition key (per `src/dbt/CLAUDE.md` "All
  intermediate models must")

**Definition-grain ints** (consumed by `dim_assessments`):

| New intermediate                                           | Source                                         | `partition_by`                                                | Notes                                                                                                              |
| ---------------------------------------------------------- | ---------------------------------------------- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `int_pearson__assessments`                                 | `int_pearson__all_assessments`                 | `discipline, test_grade, subject, testcode`                   | Pre-filters `testscalescore is not null`. `order_by` = `assessment_name` to pick canonical title deterministically |
| `int_fldoe__assessments`                                   | `int_fldoe__all_assessments`                   | `assessment_subject, discipline, test_code, assessment_grade` | Pre-filters `scale_score is not null`. `order_by` = `assessment_name`                                              |
| `int_assessments__college_assessments_definitions`         | `int_assessments__college_assessment`          | `scope, subject_area, score_type`                             | Projects `aligned_subject`, `aligned_subject_area`, `course_discipline`                                            |
| `int_assessments__college_assessment_practice_definitions` | `int_assessments__college_assessment_practice` | `scope, subject_area`                                         | Computed `module_code` lives in the mart (it's a mart-shape concern, not a source attribute)                       |
| `int_assessments__ap_assessments_definitions`              | `int_assessments__ap_assessments`              | `test_subject, ps_ap_course_subject_code`                     |                                                                                                                    |

**Administration-grain ints** (consumed by `dim_assessment_administrations`):

| New intermediate                           | Source                                | `partition_by` (canonical admin key per mart's current DISTINCT)                                                                                                                                   |
| ------------------------------------------ | ------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `int_pearson__administrations`             | `int_pearson__all_assessments`        | `subject_area, scope, module_code, grade_level, administered_date, academic_year, region, administration_period, test_type` (1:1 with current DISTINCT key list in `state_nj_administrations` CTE) |
| `int_fldoe__administrations`               | `int_fldoe__all_assessments`          | Same shape, FL-source column names                                                                                                                                                                 |
| `int_assessments__college_administrations` | `int_assessments__college_assessment` | Same shape                                                                                                                                                                                         |
| `int_assessments__ap_administrations`      | `int_assessments__ap_assessments`     | Same shape                                                                                                                                                                                         |

Each admin int's `partition_by` column list is copied 1:1 from the columns
currently inside that CTE's DISTINCT SELECT in `dim_assessment_administrations`.
Mart CTEs then become `SELECT ... FROM int_<source>__administrations` with no
DISTINCT.

### Surveys-side redirects (0 new ints)

| Mart CTE                                      | Replace `ref(...)` with                |
| --------------------------------------------- | -------------------------------------- |
| `dim_survey_questions.google_forms_questions` | `ref("int_google_forms__form__items")` |
| `dim_survey_questions.alchemer_questions`     | `ref("stg_alchemer__survey_question")` |
| `dim_survey_questions.manager_questions`      | (delete CTE + its UNION ALL branch)    |
| `dim_surveys.google_forms_surveys`            | `ref("stg_google_forms__form")`        |
| `dim_surveys.alchemer_surveys`                | `ref("stg_alchemer__survey")`          |
| `bridge_survey_questions.google_forms_pairs`  | `ref("int_google_forms__form__items")` |
| `bridge_survey_questions.alchemer_pairs`      | `ref("stg_alchemer__survey_question")` |
| `bridge_survey_questions.manager_pairs`       | (delete CTE + its UNION ALL branch)    |

All four `SELECT DISTINCT` clauses in the surveys trio drop to plain `SELECT`.
The final mart row-count delta is whatever the difference is between "every
(survey, question) pair that has ever appeared in a response" (current) and
"every (survey, question) pair that exists in the form/question definition"
(post-redirect). For well-maintained forms these should match; any delta is
itself a signal worth investigating in the verification step.

## Verification

Per CLAUDE.md "For dbt changes, `uv run dbt build --select <model>+`":

```bash
VIRTUAL_ENV= uv \
  --directory .worktrees/cbini-refactor-claude-distinct-cleanup-3780 \
  run dbt build \
  --project-dir src/dbt/kipptaf \
  --select \
    +dim_assessments \
    +dim_assessment_administrations \
    +dim_survey_questions \
    +dim_surveys \
    +bridge_survey_questions
```

**Row-count parity** against the PR-branch schema once dbt Cloud CI builds. For
each of the five marts:

```sql
select
  (select count(*) from `<prod_schema>.<mart>`) as n_prod,
  (select count(*) from `<pr_branch_schema>.<mart>`) as n_pr,
```

Expected delta:

- `dim_assessments`, `dim_assessment_administrations`: **0** — intermediates are
  1:1 pushes of the mart's current DISTINCT key.
- `dim_survey_questions`, `dim_surveys`, `bridge_survey_questions`: **may
  shift**, because the surveys redirects move from "appears in responses" to
  "exists as a definition." Any delta must be explained — typically rows for
  forms/questions that exist in metadata but have never received a response (new
  rows in the mart), or rows for response-only artifacts that shouldn't have
  been there (removed rows). Investigate each direction.

**Sample-check populated values** for any column whose value depends on which
row a previous `min()` or DISTINCT picked from a multi-row partition — state_nj
`title` (`min(assessment_name)`) is the canonical example. Before/after sample
on PR-branch vs prod for 20 sampled `module_code` values to confirm the new
`dbt_utils.deduplicate` `order_by` picks the same title as the previous `min()`.

## Files touched

**New** (9 SQL + 9 properties YAML entries):

- `src/dbt/kipptaf/models/pearson/intermediate/int_pearson__assessments.sql` +
  properties
- `src/dbt/kipptaf/models/pearson/intermediate/int_pearson__administrations.sql` +
  properties
- `src/dbt/kipptaf/models/fldoe/intermediate/int_fldoe__assessments.sql` +
  properties
- `src/dbt/kipptaf/models/fldoe/intermediate/int_fldoe__administrations.sql` +
  properties
- `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__college_assessments_definitions.sql` +
  properties
- `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__college_assessment_practice_definitions.sql` +
  properties
- `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__college_administrations.sql` +
  properties
- `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__ap_assessments_definitions.sql` +
  properties
- `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__ap_administrations.sql` +
  properties

**Modified** (5 mart SQL files; YAML untouched since contract surfaces don't
change):

- `src/dbt/kipptaf/models/marts/dimensions/dim_assessments.sql`
- `src/dbt/kipptaf/models/marts/dimensions/dim_assessment_administrations.sql`
- `src/dbt/kipptaf/models/marts/dimensions/dim_survey_questions.sql`
- `src/dbt/kipptaf/models/marts/dimensions/dim_surveys.sql`
- `src/dbt/kipptaf/models/marts/bridges/bridge_survey_questions.sql`

## Risks

- **Wrong `partition_by` column list on a new int.** A narrower partition than
  the mart's current DISTINCT key fans the mart out. Mitigation: copy the
  partition column list 1:1 from the current DISTINCT/GROUP BY in each mart CTE;
  row-count parity per mart catches this.
- **Surveys redirects shift row counts.** Definitions-grain sources may carry
  rows that responses-grain sources did not, and vice versa. Mitigation:
  pre/post row-count comparison is expected to differ for the three surveys
  marts; investigate each direction before merge. If a meaningful semantic shift
  surfaces, file follow-up and revert the affected CTE redirect to a new int
  instead.
- **Title / canonical-attribute drift.** The pearson / fldoe CTEs currently use
  `min(assessment_name) as title`. The new int's `dbt_utils.deduplicate`
  `order_by` must pick the same row. Mitigation: use
  `order_by="assessment_name asc"` (matches `min()` semantics for non-NULL ASCII
  titles); sample-check 20 codes.

## Out of scope

- `dim_assessment_administrations.illuminate_administrations` (TODO #3800 in the
  existing source, tracked separately).
- Any column renames, FK restructures, or hash recompositions on the mart side.
- Re-org of `int_assessments__assessments` itself.
- The `int_surveys__manager_survey_details` post-#3899 cleanup (#3918) — this
  spec drops the mart's reads of it, but the model itself stays.

## Sequencing

One PR, four logical commits inside the branch:

1. Assessment-definition intermediates (5 new) + `dim_assessments` mart rewrite
   (drops 4 DISTINCTs / GROUP BYs and the stale comment). Verify parity.
2. Assessment-administration intermediates (4 new) +
   `dim_assessment_administrations` non-illuminate CTE rewrites. Verify parity.
3. Surveys redirects across `dim_survey_questions`, `dim_surveys`,
   `bridge_survey_questions`. Verify (expected non-zero delta; investigate each
   direction).
4. Drop redundant manager CTEs from `dim_survey_questions` and
   `bridge_survey_questions`. Verify zero net delta vs commit 3.
