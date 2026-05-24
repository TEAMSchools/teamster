# Push entity-grain projections from marts into intermediate (#3780)

## Problem

Five mart models use `SELECT DISTINCT` to collapse response-grain (or
per-score-grain) rows into entity-grain rows. This violates the project rule in
`src/dbt/CLAUDE.md` ("No manual deduplication — do not use `SELECT DISTINCT` or
`qualify row_number() = 1`... If `DISTINCT` is truly unavoidable, it must
include a `-- TODO:` comment explaining why").

Affected marts (per
[#3780](https://github.com/TEAMSchools/teamster/issues/3780)):

- `dim_assessments`
- `dim_assessment_administrations` (non-illuminate CTEs only — illuminate is
  tracked separately under TODO #3800)
- `dim_survey_questions`
- `dim_surveys`
- `bridge_survey_questions`

The fix is structural: the projection from response/score grain to entity grain
belongs in intermediate models. Marts should read pre-projected, entity-grain
rows and either pass them through or UNION ALL them.

## Scope

All five cleanups in one PR. The surveys trio shares so much upstream that
splitting them buys little, and the assessments pair has parallel structure to
the surveys pair, so the spec is uniform.

In scope:

- Build per-source entity-grain intermediates that collapse response/score
  grain.
- Rewrite the five mart files to drop `SELECT DISTINCT` / `GROUP BY` collapse
  CTEs.
- Verify pre/post row-count parity per mart.

Out of scope:

- `dim_assessment_administrations.illuminate_administrations` (TODO #3800 in the
  existing source, tracked separately).
- Any column renames, FK restructures, or hash recompositions on the mart side.
  Mart surface stays byte-identical except for SQL structure.
- Re-org of `int_assessments__assessments` itself (the canonical-grain collapse
  there is its own follow-up).

## Architecture

### Pattern

Each new intermediate is `materialized: view` (default for intermediates), uses
`dbt_utils.deduplicate` with:

- `partition_by` = the entity key the mart joins on
- `order_by` = a canonical-attribute ordering (e.g., `title`) so that multi-row
  partitions resolve deterministically per "Canonical attributes from a
  partition" in `src/dbt/CLAUDE.md`

Each new intermediate gets a `properties.yml` entry with `description:`, column
descriptions, and a uniqueness test on the partition key (intermediates require
uniqueness per `src/dbt/CLAUDE.md` "All intermediate models must").

### Assessments group

Eight new intermediates total, split into two parallel sets.

**Assessment-definition grain** (consumed by `dim_assessments`):

| New intermediate                                   | Source                                | Partition key                                                                                   |
| -------------------------------------------------- | ------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `int_pearson__assessments`                         | `int_pearson__all_assessments`        | `discipline, test_grade, subject, testcode` (where `testscalescore is not null`)                |
| `int_fldoe__assessments`                           | `int_fldoe__all_assessments`          | `assessment_subject, discipline, test_code, assessment_grade` (where `scale_score is not null`) |
| `int_assessments__college_assessments_definitions` | `int_assessments__college_assessment` | `scope, subject_area, score_type`                                                               |
| `int_assessments__ap_assessments_definitions`      | `int_assessments__ap_assessments`     | `test_subject, ps_ap_course_subject_code`                                                       |

These pre-project all the columns currently selected inside the corresponding
DISTINCT/GROUP BY CTEs in `dim_assessments`. The mart then becomes:

```sql
illuminate_assessments as (select ... from int_assessments__assessments where is_internal_assessment),
state_nj as (select ... from int_pearson__assessments),
state_fl as (select ... from int_fldoe__assessments),
college_assessments as (select ... from int_assessments__college_assessments_definitions),
practice_assessments as (...),  -- already collapsed via int_assessments__college_assessment_practice; verify and drop DISTINCT
ap_assessments as (select ... from int_assessments__ap_assessments_definitions),
... existing UNION ALL + dedup ...
```

**Administration grain** (consumed by `dim_assessment_administrations`):

| New intermediate                           | Source                                | Partition key                                                                                          |
| ------------------------------------------ | ------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `int_pearson__administrations`             | `int_pearson__all_assessments`        | `module_code, grade_level, administered_date, academic_year, region, administration_period, test_type` |
| `int_fldoe__administrations`               | `int_fldoe__all_assessments`          | same shape, with FL-specific column names                                                              |
| `int_assessments__college_administrations` | `int_assessments__college_assessment` | same shape                                                                                             |
| `int_assessments__ap_administrations`      | `int_assessments__ap_assessments`     | same shape                                                                                             |

Exact partition columns mirror the current DISTINCT key list in each mart CTE —
each new intermediate's `dbt_utils.deduplicate` partition column list is copied
1:1 from the columns currently inside that CTE's projection.

After: each non-illuminate CTE in `dim_assessment_administrations` becomes a
plain `SELECT ... FROM int_<source>__administrations`. The existing illuminate
CTE (with its TODO #3800 comment) is unchanged.

### Surveys group

Three new pairs of intermediates plus a verification on the SCD source.

**Per-source question-grain and survey-grain intermediates:**

| Pair         | Source (response grain)               | Question-grain int               | Survey-grain int               |
| ------------ | ------------------------------------- | -------------------------------- | ------------------------------ |
| Google Forms | `int_google_forms__form_responses`    | `int_google_forms__questions`    | `int_google_forms__surveys`    |
| Alchemer     | `int_surveys__survey_responses`       | `int_alchemer__questions`        | `int_alchemer__surveys`        |
| Manager      | `int_surveys__manager_survey_details` | `int_surveys__manager_questions` | `int_surveys__manager_surveys` |

Partition key for question-grain ints: `(survey_id, question_shortname)` plus
whatever question-level attributes (`question_text`, `question_type`, display
order, etc.) the mart currently projects. Partition key for survey-grain ints:
`survey_id` plus survey-level attributes (`survey_title`, `survey_type`, etc.).
Exact column lists come from the current DISTINCT projections in
`dim_survey_questions` / `dim_surveys`.

**SCD source review:** `stg_google_sheets__surveys__scd_question_crosswalk` is
staging from a Google Sheet — already at question grain by definition. The
DISTINCT in `dim_survey_questions.scd_questions` is likely vestigial. Verify by
querying the staging table for uniqueness on `(survey_id, question_shortname)`;
if unique, drop the DISTINCT, no new intermediate.

**After:** the three marts become plain UNION ALLs over the per-source
intermediates (plus SCD staging). `bridge_survey_questions` collapses similarly
— each branch reads `(survey_id, question_shortname)` from the corresponding
`int_*__questions` model.

### Special case: `dim_assessments.illuminate_assessments`

The issue flags this CTE for review: "Source already exists at assessment-id
grain (`int_assessments__assessments`); review whether DISTINCT is actually
needed or just defensive."

`int_assessments__assessments` begins with a `GROUP BY assessment_id` on the
agl/iae dedup CTE and downstream selects propagate that grain. The DISTINCT in
`dim_assessments.illuminate_assessments` is defensive.

**Action:** drop the DISTINCT, replace with a plain SELECT. No new intermediate.

If pre/post row-count parity fails on this CTE alone, restore DISTINCT with a
`-- TODO:` comment per the project rule, and file the upstream uniqueness issue
separately.

## Verification

Per CLAUDE.md superpowers override "For dbt changes,
`uv run dbt build --select <model>+` against the relevant project":

```bash
cd /workspaces/teamster
VIRTUAL_ENV= uv --directory .worktrees/cbini-refactor-claude-distinct-cleanup-3780 \
  run dbt build \
  --project-dir src/dbt/kipptaf \
  --select \
    +dim_assessments \
    +dim_assessment_administrations \
    +dim_survey_questions \
    +dim_surveys \
    +bridge_survey_questions
```

**Row-count parity** against the PR-branch schema after dbt Cloud CI builds:

```sql
-- Per mart: pre (prod) vs post (PR-branch schema)
select 'dim_assessments' as model, count(*) as n from `<prod_schema>.dim_assessments`
union all
select 'dim_assessments' as model, count(*) as n from `<pr_branch_schema>.dim_assessments`
-- ... repeat for the other four marts
```

Per the marts CLAUDE.md "Removing a mart-level qualify row_number() = 1"
guidance: net mart row-count delta should be **zero** when the DISTINCT is
purely projecting (which is the case for all five marts here — the DISTINCT is
the projection operation, not a defensive dedup of dirty source data). Any
non-zero delta is a signal that a partition_by column list is wrong and the
intermediate is fanning out where the mart used to collapse.

## Files touched

**New** (14 SQL + 14 properties YAML entries):

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
- `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__college_administrations.sql` +
  properties
- `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__ap_assessments_definitions.sql` +
  properties
- `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__ap_administrations.sql` +
  properties
- `src/dbt/kipptaf/models/google/forms/intermediate/int_google_forms__questions.sql` +
  properties
- `src/dbt/kipptaf/models/google/forms/intermediate/int_google_forms__surveys.sql` +
  properties
- `src/dbt/kipptaf/models/alchemer/intermediate/int_alchemer__questions.sql` +
  properties
- `src/dbt/kipptaf/models/alchemer/intermediate/int_alchemer__surveys.sql` +
  properties
- `src/dbt/kipptaf/models/surveys/intermediate/int_surveys__manager_questions.sql` +
  properties
- `src/dbt/kipptaf/models/surveys/intermediate/int_surveys__manager_surveys.sql` +
  properties

(Final directory placement for Google Forms / Alchemer / Manager intermediates
mirrors the existing source directory layout — `models/alchemer/intermediate/`
already exists; Google Forms may need creation; Manager already lives under
`models/surveys/intermediate/`.)

**Modified** (5 mart SQL files only; YAML untouched since contract surfaces
don't change):

- `src/dbt/kipptaf/models/marts/dimensions/dim_assessments.sql`
- `src/dbt/kipptaf/models/marts/dimensions/dim_assessment_administrations.sql`
- `src/dbt/kipptaf/models/marts/dimensions/dim_survey_questions.sql`
- `src/dbt/kipptaf/models/marts/dimensions/dim_surveys.sql`
- `src/dbt/kipptaf/models/marts/bridges/bridge_survey_questions.sql`

## Risks

- **Wrong partition_by column list.** If a new intermediate's
  `dbt_utils.deduplicate` partitions by a narrower key than the mart's current
  DISTINCT, the mart fans out. Mitigation: copy the partition column list 1:1
  from the current DISTINCT/GROUP BY in each mart CTE; verify row-count parity
  per mart.
- **Stale DISTINCT was masking source non-uniqueness.** If a source response
  table actually has duplicate (entity-key, projected-attribute) tuples that
  differ in some excluded column, removing DISTINCT changes the resolved
  attribute. Mitigation: `order_by` in `dbt_utils.deduplicate` picks
  deterministically; sample-check populated values before vs after on PR-branch
  schema for any column that matters (titles, codes).
- **Hash-input drift on FKs into these dims.** Mart surrogate keys
  (`assessment_key`, `survey_question_key`, etc.) are computed from projected
  columns. If a new intermediate changes any of those column values (vs. the
  current DISTINCT's outputs), downstream FKs hash-diff. Mitigation: the
  intermediates must project exactly the columns the marts currently project,
  with the same casts. No semantic changes in this PR.

## Sequencing

One PR, one commit per logical sub-step (split between assessments and surveys
groups). Suggested commit order inside the branch:

1. Assessments-definition intermediates (4 new) + `dim_assessments` mart
   rewrite. Verify parity.
2. Assessments-administration intermediates (4 new) +
   `dim_assessment_administrations` non-illuminate CTE rewrites. Verify parity.
3. Survey question + survey intermediates (6 new) + `dim_survey_questions`,
   `dim_surveys`, `bridge_survey_questions` rewrites. Verify parity.
4. SCD DISTINCT removal in `dim_survey_questions` (separate commit so the
   row-count parity check isolates the SCD source case).
