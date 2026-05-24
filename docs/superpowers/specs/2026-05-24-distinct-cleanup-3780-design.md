# Push entity-grain projections from marts into intermediate (#3780)

## Problem

Five mart models in `marts/` use `SELECT DISTINCT` or `GROUP BY` aggregates to
collapse response-grain (or per-score-grain) rows into entity-grain rows. Some
of these are pure grain projection (every projected column is functionally
determined by the partition key); some resolve a canonical attribute from a
multi-row partition.

`src/dbt/CLAUDE.md` ("SQL conventions") permits DISTINCT for pure grain
projection with an annotation, and requires `dbt_utils.deduplicate()` when a
projected column varies within the partition. The fix is to align each CTE with
the correct construct — not to layer every projection into an intermediate.
Single-consumer ints add maintenance without payoff.

Affected marts (per
[#3780](https://github.com/TEAMSchools/teamster/issues/3780)):

- `dim_assessments`
- `dim_assessment_administrations` (non-illuminate CTEs only — illuminate is
  tracked separately under TODO #3800)
- `dim_survey_questions`
- `dim_surveys`
- `bridge_survey_questions`

## Investigation: per-CTE classification

Each CTE was audited against its source's actual grain and classified by whether
the collapse is **pure projection** (every projected column functionally
determined by the partition key — byte-identical tuples coalesce) or
**canonical-attribute resolution** (at least one projected column varies within
the partition and needs deterministic selection).

### Assessments group

| Mart CTE                                    | Source                                         | Source grain                                                                                                        | Collapse type                                                                           | Resolution                                                                                                                                                 |
| ------------------------------------------- | ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `dim_assessments.illuminate_assessments`    | `int_assessments__assessments`                 | `assessment_id` (unique test)                                                                                       | No collapse                                                                             | Remove stale "DISTINCT projects..." comment block — no DISTINCT is actually present in the SQL                                                             |
| `dim_assessments.state_nj`                  | `int_pearson__all_assessments`                 | per-student-per-assessment response                                                                                 | Pure projection AFTER admitting `assessment_name` as a key column (see "Lineage split") | Switch from `GROUP BY ... min(assessment_name)` to plain DISTINCT with annotation; emit `concat('state_nj_', lower(assessment_name))` as `assessment_type` |
| `dim_assessments.state_fl`                  | `int_fldoe__all_assessments`                   | per-student-per-assessment response                                                                                 | Pure projection AFTER admitting `assessment_name` as a key column                       | Switch from `GROUP BY ... min(assessment_name)` to plain DISTINCT with annotation; emit `concat('state_fl_', lower(assessment_name))` as `assessment_type` |
| `dim_assessments.college_assessments`       | `int_assessments__college_assessment`          | per-student-per-test-date (has `surrogate_key`)                                                                     | Pure projection                                                                         | Keep DISTINCT; replace existing comment block with the annotation phrase                                                                                   |
| `dim_assessments.practice_assessments`      | `int_assessments__college_assessment_practice` | per-student-per-test response                                                                                       | Pure projection                                                                         | Keep DISTINCT with annotation                                                                                                                              |
| `dim_assessments.ap_assessments`            | `int_assessments__ap_assessments`              | per-student-per-exam (model carries `row_number() over (partition by student, ap_course_name order by exam_score)`) | Pure projection                                                                         | Keep DISTINCT with annotation                                                                                                                              |
| `dim_assessment_administrations.state_nj_*` | `int_pearson__all_assessments`                 | per-student response                                                                                                | Pure projection AFTER lineage split                                                     | Keep DISTINCT with annotation; project `assessment_name`; emit `concat('state_nj_', lower(assessment_name))` as `assessment_type`                          |
| `dim_assessment_administrations.state_fl_*` | `int_fldoe__all_assessments`                   | per-student response                                                                                                | Pure projection AFTER lineage split                                                     | Keep DISTINCT with annotation; project `assessment_name`; emit `concat('state_fl_', lower(assessment_name))` as `assessment_type`                          |
| `dim_assessment_administrations.college_*`  | `int_assessments__college_assessment`          | per-student-per-test-date                                                                                           | Pure projection                                                                         | Keep DISTINCT with annotation                                                                                                                              |
| `dim_assessment_administrations.ap_*`       | `int_assessments__ap_assessments`              | per-student-per-exam                                                                                                | Pure projection                                                                         | Keep DISTINCT with annotation                                                                                                                              |

Net: **0 new intermediates**, 9 DISTINCT CTEs annotated as pure projection, 2
lineage-split rewrites (state_nj, state_fl across both marts), 1 stale comment
block removed. No `dbt_utils.deduplicate` switches (the lineage split makes the
`min()` resolution unnecessary).

### Lineage split: NJSLA / PARCC and FAST / FSA / Science

The current `state_nj` and `state_fl` CTEs collapse historical title variants
(`NJSLA | PARCC` on every NJ ELA / Math testcode; `FAST | FSA` on every FL ELA /
Math testcode; `FSA | Science` on SCI05 / SCI08) into one mart row per
`(module_code, grade)` with `min(assessment_name) as title`. Successor
assessments (NJSLA after PARCC, FAST after FSA) are different programs
administered to similar student populations — surfacing them as one dim row
erases that distinction.

**Fix**: include `assessment_name` in the state-branch projections; encode the
program-level distinction in `assessment_type`. Per-region literal `'state_nj'`
becomes `'state_nj_njsla'` / `'state_nj_parcc'`. Per-region literal `'state_fl'`
becomes `'state_fl_fast'` / `'state_fl_fsa'` / `'state_fl_science'`.

After the split, `state_nj` and `state_fl` CTEs become pure projection (every
projected column functionally determined by the new partition key that includes
`assessment_name`) — straight DISTINCT with the standard annotation. Same in the
corresponding `dim_assessment_administrations` CTEs.

**Hash composition is unchanged.** `assessment_key` and
`assessment_administration_key` continue to hash from
`assessment_type, module_code, source_assessment_id, test_type` (and
admin-specific extras). The type-string split causes hashes to diverge naturally
— no input list change required.

**Downstream impact**:

- `fct_assessment_scores_enrollment_scoped` state branches hash
  `assessment_administration_key` from literal `'state'` (not `'state_nj'` /
  `'state_fl'`), so they were already not joining to
  `dim_assessment_administrations.assessment_administration_key`. This
  pre-existing mismatch is out of scope; flag in the PR body and file a separate
  issue.
- `fct_assessment_scores_enrollment_scoped.score_source` literals (`'state_nj'`
  / `'state_fl'`) stay unchanged — `score_source` is a data-integration label
  (which system produced the score), not a program-lineage label. Program
  lineage is already on the fact under `title` and reachable from the joined
  dim.
- Cube / BI filters that match `assessment_type = 'state_nj'` need to become
  `assessment_type LIKE 'state_nj_%'`. Per the marts spec-authoring rule ("No
  production consumers yet"), this is allowed; call out in the PR body so Cube
  `cube.yml` filters get audited.

### Surveys group

The surveys-side investigation surfaced that all four current
DISTINCT-collapsing CTEs in `dim_survey_questions` (and their bridge / dim
counterparts) can resolve to **redirect** or **drop** — entity-grain upstreams
already exist.

| Mart CTE                                        | Current source                                                                      | Entity-grain upstream that already exists                                                                                                            | Resolution                                                                                                                                                                                                        |
| ----------------------------------------------- | ----------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `dim_survey_questions.google_forms_questions`   | `int_google_forms__form_responses` (response grain)                                 | `int_google_forms__form__items` (item / question grain — carries `form_id`, `item_abbreviation`, `item_title`, `question_kind`, `question_required`) | **Redirect** to `int_google_forms__form__items`                                                                                                                                                                   |
| `dim_survey_questions.scd_questions`            | `stg_google_sheets__surveys__scd_question_crosswalk`                                | Already at question grain (BQ check: 10 rows = 10 distinct `question_code` values in the `School_Survey_%` filter)                                   | **No-op** — mart CTE already uses plain `SELECT`, no DISTINCT to remove                                                                                                                                           |
| `dim_survey_questions.alchemer_questions`       | `int_surveys__survey_responses` (response grain — union of Google Forms + Alchemer) | `stg_alchemer__survey_question` (per-`(survey_id, id)` grain, carries `shortname`, `title_english`)                                                  | **Redirect** to `stg_alchemer__survey_question`, scoped to Alchemer questions only. Google Forms questions in this CTE are now covered by the gforms redirect above                                               |
| `dim_survey_questions.manager_questions`        | `int_surveys__manager_survey_details` (response grain)                              | Manager Survey is Google Form `'1cvp9RnYxbn-WGLXsYSupbEl2KhVhWKcOFbHR2CgUBH0'`; its questions are already in `int_google_forms__form__items`         | **Drop** the CTE entirely. Coverage is redundant once gforms redirect lands. Per the post-#3899 comment in `int_surveys__manager_survey_details`, live Manager Survey identity already flows through Google Forms |
| `dim_surveys.google_forms_surveys`              | `int_google_forms__form_responses` (response grain)                                 | `stg_google_forms__form` (form / survey grain — carries `form_id`, `info_title`)                                                                     | **Redirect** to `stg_google_forms__form`                                                                                                                                                                          |
| `dim_surveys.alchemer_surveys`                  | `source("alchemer", "base_alchemer__survey_results")` (response grain)              | `stg_alchemer__survey` (per-`id` survey grain)                                                                                                       | **Redirect** to `stg_alchemer__survey`                                                                                                                                                                            |
| `bridge_survey_questions.google_forms_pairs`    | `int_google_forms__form_responses`                                                  | `int_google_forms__form__items` carries `(form_id, item_abbreviation, question_required)`                                                            | **Redirect** to `int_google_forms__form__items`                                                                                                                                                                   |
| `bridge_survey_questions.alchemer_pairs`        | `int_surveys__survey_responses`                                                     | `stg_alchemer__survey_question` carries `(survey_id, shortname)`                                                                                     | **Redirect** to `stg_alchemer__survey_question`                                                                                                                                                                   |
| `bridge_survey_questions.manager_pairs`         | `int_surveys__manager_survey_details`                                               | Subset of Google Forms after the gforms redirect                                                                                                     | **Drop** the CTE entirely                                                                                                                                                                                         |
| `bridge_survey_questions.scd_powerschool_pairs` | `stg_google_sheets__surveys__scd_question_crosswalk`                                | Already at question grain                                                                                                                            | **No-op** — already uses plain `SELECT`                                                                                                                                                                           |

Net: **0 new intermediates**, 6 redirects, 2 redundant CTEs dropped, 2 no-ops.

## Architecture

### Companion `src/dbt/CLAUDE.md` change

Replace the "No manual deduplication" bullet with two bullets that distinguish
dirty-data workarounds from pure grain projection. Applied in the same PR so the
marts changes and the rule clarification ship together. See commit
(`refactor(dbt): permit DISTINCT for pure grain projection`).

### Assessments marts — inline rewrites

**`dim_assessments`:**

- Remove the stale "DISTINCT projects..." comment block above
  `illuminate_assessments` (no DISTINCT is present in that CTE).
- `state_nj` and `state_fl`: drop the `GROUP BY` and `min(assessment_name)`.
  Switch to plain `SELECT DISTINCT` over a source CTE that retains
  `assessment_name`. Project `assessment_name as title` directly. Compose
  `assessment_type` as `concat('state_nj_', lower(assessment_name))` (or
  `state_fl_` for FL). Annotate with the standard
  `-- projection IS the operation, not deduplication`. Update the existing block
  comments that reference "Collapse historical title variants" — those collapses
  are now treated as distinct lineages, not collapsed.
- `college_assessments`, `practice_assessments`, `ap_assessments`: keep
  `SELECT DISTINCT`. Replace the existing "DISTINCT projects..." comment block
  above each with the single-line annotation.

**`dim_assessment_administrations`:** all four non-illuminate CTEs keep
`SELECT DISTINCT` with the annotation. `state_nj_administrations` and
`state_fl_administrations` additionally project `assessment_name` and compose
the split `assessment_type` per the lineage rules above — matching the dim's
composition exactly so `assessment_administration_key` and `assessment_key`
hashes align. The illuminate CTE and its existing TODO #3800 comment stay
untouched.

### Surveys marts — redirects

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

All four `SELECT DISTINCT` clauses in the surveys trio drop to plain `SELECT`
because the redirect targets are already at entity grain. Final mart row-count
delta is whatever the difference is between "every (survey, question) pair that
has ever appeared in a response" (current) and "every (survey, question) pair
that exists in the form / question definition" (post-redirect).

## Phase 0: Pre-merge BQ shape audit

The surveys redirects move grain from "appears in any response" to "exists as a
definition" — the row-count delta isn't predictable from inspection. Before
mart-side commits land, run these queries against prod to size the delta per
redirect and surface anything anomalous. Each query is a symmetric-difference
count plus a small sample of unmatched rows; if the delta is large or asymmetric
in a way the redirect can't explain, escalate that redirect to a new int
instead.

Schemas: `kipptaf_google_forms`, `kipptaf_alchemer`, `kipptaf_surveys`,
`kipptaf_google_sheets`.

### A. Google Forms questions redirect

```sql
with
  current as (
    select distinct
      form_id,
      item_abbreviation,
      item_title,
      question_kind,
    from `teamster-332318.kipptaf_google_forms.int_google_forms__form_responses`
    where item_abbreviation is not null and item_title is not null
  ),
  target as (
    select
      form_id,
      item_abbreviation,
      item_title,
      question_kind,
    from `teamster-332318.kipptaf_google_forms.int_google_forms__form__items`
    where item_abbreviation is not null and item_title is not null
  )
select
  (select count(*) from current) as n_current,
  (select count(*) from target) as n_target,
  (select count(*) from current except distinct select * from target) as n_current_only,
  (select count(*) from target except distinct select * from current) as n_target_only,
```

### B. Alchemer questions redirect

```sql
with
  current as (
    select distinct
      survey_id,
      question_shortname,
      question_title,
    from `teamster-332318.kipptaf_surveys.int_surveys__survey_responses`
    where question_shortname is not null
      and survey_id is not null
      -- scope to Alchemer rows only; Google Forms rows now flow through redirect A
      and safe_cast(survey_id as int) is not null
  ),
  target as (
    select
      safe_cast(survey_id as string) as survey_id,
      shortname as question_shortname,
      title_english as question_title,
    from `teamster-332318.kipptaf_alchemer.stg_alchemer__survey_question`
    where shortname is not null
  )
select
  (select count(*) from current) as n_current,
  (select count(*) from target) as n_target,
  (select count(*) from current except distinct select * from target) as n_current_only,
  (select count(*) from target except distinct select * from current) as n_target_only,
```

### C. Google Forms surveys redirect

```sql
with
  current as (
    select distinct form_id, info_title
    from `teamster-332318.kipptaf_google_forms.int_google_forms__form_responses`
    where form_id is not null
  ),
  target as (
    select form_id, info_title
    from `teamster-332318.kipptaf_google_forms.stg_google_forms__form`
    where form_id is not null
  )
select
  (select count(*) from current) as n_current,
  (select count(*) from target) as n_target,
  (select count(*) from current except distinct select * from target) as n_current_only,
  (select count(*) from target except distinct select * from current) as n_target_only,
```

### D. Alchemer surveys redirect

```sql
with
  current as (
    select distinct
      safe_cast(survey_id as string) as survey_id,
      survey_title,
    from `teamster-332318.kipptaf_alchemer.base_alchemer__survey_results`
    where survey_id is not null
  ),
  target as (
    select
      safe_cast(id as string) as survey_id,
      <title_col> as survey_title,
    from `teamster-332318.kipptaf_alchemer.stg_alchemer__survey`
    where id is not null
  )
select
  (select count(*) from current) as n_current,
  (select count(*) from target) as n_target,
  (select count(*) from current except distinct select * from target) as n_current_only,
  (select count(*) from target except distinct select * from current) as n_target_only,
```

(Resolve `<title_col>` from `stg_alchemer__survey` schema at query time — the
staging model uses `dbt_utils.star()` so the title column name depends on the
source. Run
`select column_name from INFORMATION_SCHEMA.COLUMNS where table_name = 'stg_alchemer__survey'`
first.)

### E. Google Forms bridge pairs

```sql
with
  current as (
    select distinct form_id, item_abbreviation, question_required
    from `teamster-332318.kipptaf_google_forms.int_google_forms__form_responses`
    where form_id is not null and item_abbreviation is not null
  ),
  target as (
    select form_id, item_abbreviation, question_required
    from `teamster-332318.kipptaf_google_forms.int_google_forms__form__items`
    where form_id is not null and item_abbreviation is not null
  )
select
  (select count(*) from current) as n_current,
  (select count(*) from target) as n_target,
  (select count(*) from current except distinct select * from target) as n_current_only,
  (select count(*) from target except distinct select * from current) as n_target_only,
```

### F. Alchemer bridge pairs

```sql
with
  current as (
    select distinct survey_id, question_shortname
    from `teamster-332318.kipptaf_surveys.int_surveys__survey_responses`
    where survey_id is not null
      and question_shortname is not null
      and safe_cast(survey_id as int) is not null  -- Alchemer rows only
  ),
  target as (
    select
      safe_cast(survey_id as string) as survey_id,
      shortname as question_shortname,
    from `teamster-332318.kipptaf_alchemer.stg_alchemer__survey_question`
    where shortname is not null
  )
select
  (select count(*) from current) as n_current,
  (select count(*) from target) as n_target,
  (select count(*) from current except distinct select * from target) as n_current_only,
  (select count(*) from target except distinct select * from current) as n_target_only,
```

### G. Manager drop validation

Confirm that every `(survey_id, question_shortname)` pair the manager CTEs
currently contribute is already covered by the gforms or SCD surfaces (otherwise
the drop loses rows):

```sql
with
  manager_pairs as (
    select distinct survey_id, question_shortname
    from `teamster-332318.kipptaf_surveys.int_surveys__manager_survey_details`
    where survey_id is not null and question_shortname is not null
  ),
  gforms_pairs as (
    select form_id as survey_id, item_abbreviation as question_shortname
    from `teamster-332318.kipptaf_google_forms.int_google_forms__form__items`
    where item_abbreviation is not null
  ),
  scd_pairs as (
    select 'PowerSchool' as survey_id, question_code as question_shortname
    from `teamster-332318.kipptaf_google_sheets.stg_google_sheets__surveys__scd_question_crosswalk`
    where question_code like 'School_Survey_%'
  ),
  covered as (
    select * from gforms_pairs
    union all
    select * from scd_pairs
  )
select
  (select count(*) from manager_pairs) as n_manager,
  (
    select count(*)
    from manager_pairs
    except distinct
    select * from covered
  ) as n_manager_uncovered,
```

`n_manager_uncovered` must be 0 (or only `historic_alchemer_Manager_survey`
archive rows, handled by the hardcoded `archive_manager` CTE in `dim_surveys`).
Any other uncovered rows mean the drop is unsafe — keep the CTE.

### Phase-0 decision rules

For each redirect A–F:

- **Symmetric delta (`n_target` near `n_current` with small `n_*_only` on both
  sides)**: redirect safe. Document counts in PR body and proceed.
- **Large `n_target_only`**: many definitions never received responses. Expected
  for surveys with low completion rates; safe to proceed.
- **Large `n_current_only`**: response rows reference a (survey, question) the
  definition source doesn't carry — typically renamed shortnames or
  deleted/recreated forms. Sample 10 unmatched rows; if they trace to legitimate
  historical data, escalate that redirect to a new intermediate that unions
  definition with historical response artifacts. Otherwise (test / orphan rows),
  document and proceed.

Query G must return `n_manager_uncovered = 0` to proceed with the manager CTE
drops in commit 3.

## Verification

Per CLAUDE.md superpowers override "For dbt changes,
`uv run dbt build --select <model>+`":

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

**Row-count parity** against the PR-branch schema once dbt Cloud CI builds.

- `dim_assessments`: **+N rows** where N = count of distinct
  `(module_code, additional_assessment_name)` pairs minus the current
  single-row-per-`module_code` count. Pre-merge BQ confirmation:

  ```sql
  -- expected delta on NJ + FL state branches
  select
    (
      select count(distinct (testcode, assessment_name))
      from `teamster-332318.kipptaf_pearson.int_pearson__all_assessments`
      where testscalescore is not null
    ) - (
      select count(distinct testcode)
      from `teamster-332318.kipptaf_pearson.int_pearson__all_assessments`
      where testscalescore is not null
    ) as nj_added_rows,
    (
      select count(distinct (test_code, assessment_name))
      from `teamster-332318.kipptaf_fldoe.int_fldoe__all_assessments`
      where scale_score is not null
    ) - (
      select count(distinct test_code)
      from `teamster-332318.kipptaf_fldoe.int_fldoe__all_assessments`
      where scale_score is not null
    ) as fl_added_rows,
  ```

  Based on the lineage audit, expect roughly +18 NJ rows (NJSLA / PARCC split
  across ELA / Math test codes) and +14 FL rows (FAST / FSA split plus FSA /
  Science split). The delta count from PR-branch schema must match this expected
  count exactly; any other delta means the assessment_type composition or the
  partition is wrong.

- `dim_assessment_administrations`: **+M rows** where M scales with the number
  of historical administration occurrences carrying split lineages (multiple
  admin dates per testcode per region across the years NJSLA and PARCC both ran,
  etc.). Compute the expected M with the analogous query joined on the admin
  partition columns, before the commit lands.
- `dim_survey_questions`, `dim_surveys`, `bridge_survey_questions`: delta
  matches Phase-0 audit counts; any discrepancy is a failed redirect.

**Spot-check `assessment_type` lineage values**:

```sql
select assessment_type, count(*)
from `<pr_branch>.dim_assessments`
where assessment_type like 'state_%'
group by 1
order by 1
```

Must return exactly: `state_fl_fast`, `state_fl_fsa`, `state_fl_science`,
`state_nj_njsla`, `state_nj_parcc`. Any other value (e.g. `state_nj_null`, extra
suffixes) indicates a NULL `assessment_name` upstream or a typo / casing bug in
the `concat(...)` composition.

**`assessment_name` NULL audit** before commit 1:

```sql
select
  countif(assessment_name is null) as n_null_nj,
from `teamster-332318.kipptaf_pearson.int_pearson__all_assessments`
where testscalescore is not null
```

(repeat for FL). Must return 0 in both — otherwise the lineage split produces a
`state_nj_null` lineage that needs handling.

## Files touched

**Modified**:

- `src/dbt/CLAUDE.md` — split "No manual deduplication" bullet (companion rule
  clarification)
- `src/dbt/kipptaf/models/marts/dimensions/dim_assessments.sql`
- `src/dbt/kipptaf/models/marts/dimensions/dim_assessment_administrations.sql`
- `src/dbt/kipptaf/models/marts/dimensions/dim_survey_questions.sql`
- `src/dbt/kipptaf/models/marts/dimensions/dim_surveys.sql`
- `src/dbt/kipptaf/models/marts/bridges/bridge_survey_questions.sql`

**New**: none. Mart-side changes only; YAML untouched since contract surfaces
don't change.

## Risks

- **NULL `assessment_name` produces `state_nj_null` / `state_fl_null` lineage
  rows.** The `concat('state_nj_', lower(assessment_name))` composition emits
  `state_nj_null` when `assessment_name` is NULL. Mitigation: pre-commit NULL
  audit query (see Verification); if any NULL rows exist, exclude them with a
  source CTE `where` filter and document.
- **Cube / BI filters break on the `assessment_type` split.** Any Cube filter or
  query expression matching `assessment_type = 'state_nj'` or `'state_fl'`
  exact-strings no longer returns rows for state assessments. Mitigation: grep
  `src/cube/model/` for the literal strings; PR body lists every match plus the
  `LIKE 'state_nj_%'` migration pattern.
- **`assessment_administration_key` hash collision with the fct's pre-existing
  `'state'` literal.** The fact already hashes `'state'` (not `'state_nj'` /
  `'state_fl'`), so the dim split doesn't make the fact↔dim join worse than it
  already is. But it also doesn't fix it. Mitigation: out-of-scope flag in PR
  body + separate follow-up issue.
- **Surveys redirects shift row counts.** Definitions-grain sources may carry
  rows that responses-grain sources did not, and vice versa. Mitigation: Phase-0
  audit, escalation path documented.
- **Pure-projection misclassification.** A CTE classified as pure projection but
  actually carrying a column that varies in the partition would silently pick
  the wrong row when DISTINCT coalesces tuples that differ. Mitigation: each
  "pure projection" CTE in the assessments marts was inspected and only contains
  columns derivable from the partition key (constants, casts of constants, and
  the partition columns themselves). On any future addition of a non-derivable
  column to one of these CTEs, the annotation rule forces a switch to
  `dbt_utils.deduplicate`.

## Out of scope

- `dim_assessment_administrations.illuminate_administrations` (TODO #3800 in the
  existing source, tracked separately).
- Any column renames, FK restructures, or hash recompositions on the mart side.
- Re-org of `int_assessments__assessments` itself.
- `int_surveys__manager_survey_details` post-#3899 cleanup (#3918) — this spec
  drops the mart's reads of it, but the model stays.

## Sequencing

One PR, three commits plus a pre-commit Phase 0:

0. **Phase 0 (no commit)**: run BQ queries A–G against prod. Paste results into
   the PR body. Apply Phase-0 decision rules; if any redirect fails its rule,
   escalate that redirect to a new intermediate before commit 2.
1. **Assessments + CLAUDE.md.** Single commit: rule clarification in
   `src/dbt/CLAUDE.md`, plus all mart-side changes in `dim_assessments` and
   `dim_assessment_administrations`: annotate pure-projection DISTINCTs; apply
   lineage split to `state_nj` / `state_fl` (and their admin counterparts) —
   projecting `assessment_name` and composing the split `assessment_type`;
   remove stale illuminate comment. Verify expected non-zero row-count delta
   matches the formula in "Verification".
2. **Surveys redirects.** All redirects across `dim_survey_questions`,
   `dim_surveys`, `bridge_survey_questions`. Row-count delta against prod is
   expected to match Phase-0 audit counts; flag any discrepancy.
3. **Drop manager CTEs** (gated on Phase 0 query G returning
   `n_manager_uncovered = 0`). Verify zero net delta vs commit 2.
