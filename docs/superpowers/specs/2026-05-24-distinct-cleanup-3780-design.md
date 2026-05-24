# Push entity-grain projections from marts into intermediate (#3780)

## Problem

Five mart models in `marts/` use `SELECT DISTINCT` or `GROUP BY` aggregates to
collapse response-grain (or per-score-grain) rows into entity-grain rows. Some
of these are pure grain projection (every projected column is functionally
determined by the partition key); some erase meaningful program-level lineage by
lumping successor assessments together.

`src/dbt/CLAUDE.md` ("SQL conventions") permits DISTINCT for pure grain
projection with an annotation, and requires `dbt_utils.deduplicate()` when a
projected column varies within the partition. The fix is to align each CTE with
the correct construct and surface lineage where it was being erased — not to
layer every projection into a single-consumer intermediate.

Affected marts (per
[#3780](https://github.com/TEAMSchools/teamster/issues/3780)):

- `dim_assessments`
- `dim_assessment_administrations` (non-illuminate CTEs only — illuminate is
  tracked separately under TODO #3800)
- `dim_survey_questions`
- `dim_surveys`
- `bridge_survey_questions`

## Investigation: per-CTE classification

### Assessments group

The current `state_nj` and `state_fl` CTEs read from
`int_pearson__all_assessments` and `int_fldoe__all_assessments` — legacy
denormalized intermediates that union per-program staging tables together and
then collapse them in the mart via `GROUP BY ... min(assessment_name)`. This
both (a) introduces an unnecessary intermediate dependency and (b) erases
program identity (NJSLA, PARCC, NJSLA Science, NJGPA all land under
`assessment_type='state_nj'`; FAST, FSA, EOC, Science all under
`assessment_type='state_fl'`).

**Fix**: in both marts, replace the single `state_nj` / `state_fl` CTE with one
CTE per Pearson / FLDOE staging table. Each new CTE is a plain `SELECT DISTINCT`
(pure projection) from one staging table, emitting a literal `assessment_type`
that encodes both the region and the program lineage:

| Region     | Lineage    | Staging source               | `assessment_type` literal  |
| ---------- | ---------- | ---------------------------- | -------------------------- |
| New Jersey | PARCC      | `stg_pearson__parcc`         | `'state_nj_parcc'`         |
| New Jersey | NJSLA      | `stg_pearson__njsla`         | `'state_nj_njsla'`         |
| New Jersey | NJSLA Sci. | `stg_pearson__njsla_science` | `'state_nj_njsla_science'` |
| New Jersey | NJGPA      | `stg_pearson__njgpa`         | `'state_nj_njgpa'`         |
| Florida    | FAST       | `stg_fldoe__fast`            | `'state_fl_fast'`          |
| Florida    | FSA        | `stg_fldoe__fsa`             | `'state_fl_fsa'`           |
| Florida    | EOC        | `stg_fldoe__eoc`             | `'state_fl_eoc'`           |
| Florida    | Science    | `stg_fldoe__science`         | `'state_fl_science'`       |

The remaining non-state CTEs stay as DISTINCT with the standard annotation (pure
projection); none requires `dbt_utils.deduplicate` since no projected column
varies within the partition.

| Mart CTE                                         | Source                                         | Collapse type   | Resolution                                                                                     |
| ------------------------------------------------ | ---------------------------------------------- | --------------- | ---------------------------------------------------------------------------------------------- |
| `dim_assessments.illuminate_assessments`         | `int_assessments__assessments`                 | No collapse     | Remove stale "DISTINCT projects..." comment block — no DISTINCT is actually present in the SQL |
| `dim_assessments` state CTEs (×8)                | per-program Pearson / FLDOE staging            | Pure projection | One CTE per staging table, literal `assessment_type`, plain DISTINCT with annotation           |
| `dim_assessments.college_assessments`            | `int_assessments__college_assessment`          | Pure projection | Keep DISTINCT; replace existing comment block with the annotation phrase                       |
| `dim_assessments.practice_assessments`           | `int_assessments__college_assessment_practice` | Pure projection | Keep DISTINCT with annotation                                                                  |
| `dim_assessments.ap_assessments`                 | `int_assessments__ap_assessments`              | Pure projection | Keep DISTINCT with annotation                                                                  |
| `dim_assessment_administrations` state CTEs (×8) | per-program Pearson / FLDOE staging            | Pure projection | One CTE per staging table, literal `assessment_type`, plain DISTINCT with annotation           |
| `dim_assessment_administrations.college_*`       | `int_assessments__college_assessment`          | Pure projection | Keep DISTINCT with annotation                                                                  |
| `dim_assessment_administrations.ap_*`            | `int_assessments__ap_assessments`              | Pure projection | Keep DISTINCT with annotation                                                                  |

Net: **0 new intermediates**, 16 staging-direct CTEs replace 4 legacy
int-sourced CTEs, all DISTINCTs annotated as pure projection. The
`int_pearson__all_assessments` and `int_fldoe__all_assessments` dependencies
disappear from the marts (legacy denormalized intermediates that shouldn't have
been mart sources).

### Surveys group

The surveys-side investigation surfaced that all four current
DISTINCT-collapsing CTEs in `dim_survey_questions` and the bridge can resolve to
**redirect** to existing entity-grain models. `dim_surveys` keeps its hardcoded
archive rows (`archive_manager`, `archive_support`, `powerschool_family`) —
these synthesize survey_key rows for legacy data whose original IDs were not
preserved, and downstream facts (`fct_survey_submissions:231`,
`dim_survey_administrations:64`) filter by the synthetic IDs.

| Mart CTE                                        | Current source                                        | Resolution                                                                                                                                                                                                                                                                                                             |
| ----------------------------------------------- | ----------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `dim_survey_questions.google_forms_questions`   | `int_google_forms__form_responses` (response)         | **Redirect** to `int_google_forms__form__items`                                                                                                                                                                                                                                                                        |
| `dim_survey_questions.scd_questions`            | `stg_google_sheets__surveys__scd_question_crosswalk`  | **No-op** — already plain SELECT, no DISTINCT to remove                                                                                                                                                                                                                                                                |
| `dim_survey_questions.alchemer_questions`       | `int_surveys__survey_responses` (response)            | **Redirect** to `stg_alchemer__survey_question` (Alchemer rows only; Google Forms questions in this CTE are now covered by the gforms redirect)                                                                                                                                                                        |
| `dim_survey_questions.manager_questions`        | `int_surveys__manager_survey_details` (response)      | **Drop** — live Manager Survey questions covered by the gforms redirect (same form_id); question grain carries no survey_id so the historic synthetic survey_id concern is bridge-side only                                                                                                                            |
| `dim_surveys.google_forms_surveys`              | `int_google_forms__form_responses`                    | **Redirect** to `stg_google_forms__form`                                                                                                                                                                                                                                                                               |
| `dim_surveys.alchemer_surveys`                  | `source("alchemer", "base_alchemer__survey_results")` | **Redirect** to `stg_alchemer__survey`                                                                                                                                                                                                                                                                                 |
| `dim_surveys.archive_manager`                   | (hardcoded literal)                                   | **Keep.** Synthesizes `survey_id='historic_alchemer_Manager_survey'`; referenced by downstream filters                                                                                                                                                                                                                 |
| `dim_surveys.archive_support`                   | (hardcoded literal)                                   | **Keep.** Synthesizes `survey_id='historic_alchemer_cmo_support_survey'`; referenced by downstream filters                                                                                                                                                                                                             |
| `dim_surveys.powerschool_family`                | (hardcoded literal)                                   | **Keep.** Unchanged.                                                                                                                                                                                                                                                                                                   |
| `bridge_survey_questions.google_forms_pairs`    | `int_google_forms__form_responses`                    | **Redirect** to `int_google_forms__form__items`                                                                                                                                                                                                                                                                        |
| `bridge_survey_questions.alchemer_pairs`        | `int_surveys__survey_responses`                       | **Redirect** to `stg_alchemer__survey_question`                                                                                                                                                                                                                                                                        |
| `bridge_survey_questions.manager_pairs`         | `int_surveys__manager_survey_details`                 | **Redirect, not drop.** Produce `('historic_alchemer_Manager_survey', <shortname>, null)` pairs from `int_google_forms__form__items` filtered to `form_id = '1cvp9RnYxbn-WGLXsYSupbEl2KhVhWKcOFbHR2CgUBH0'`. Live Manager Survey pairs (under the real `form_id` survey_id) are already covered by the gforms redirect |
| `bridge_survey_questions.scd_powerschool_pairs` | `stg_google_sheets__surveys__scd_question_crosswalk`  | **No-op** — already plain SELECT                                                                                                                                                                                                                                                                                       |

Net: **0 new intermediates**, 7 redirects, 1 redundant CTE dropped
(`manager_questions`), 2 no-ops on SCD CTEs, 3 hardcoded literal CTEs in
`dim_surveys` retained.

## Architecture

### Companion `src/dbt/CLAUDE.md` change

Replace the "No manual deduplication" bullet with two bullets that distinguish
dirty-data workarounds from pure grain projection. Already applied in this
branch — see commit `2008a52`
(`refactor(dbt): permit DISTINCT for pure grain projection`). The new rules:

- **No manual deduplication for dirty data** — `dbt_utils.deduplicate()` with a
  `-- TODO:` comment naming the upstream fix.
- **DISTINCT is allowed for pure grain projection** — every projected column
  functionally determined by the partition key; annotate with
  `projection IS the operation, not deduplication`.

### Assessments marts — staging-direct CTEs

**`dim_assessments`:**

- Remove the stale "DISTINCT projects..." comment block above
  `illuminate_assessments` (no DISTINCT is present in that CTE).
- Replace the single `state_nj` CTE with four CTEs (`parcc`, `njsla`,
  `njsla_science`, `njgpa`), each reading from its corresponding Pearson staging
  table, each emitting a literal `assessment_type` per the lineage table above.
  Each is `SELECT DISTINCT` with the projection annotation. The existing
  `case testcode when 'SC05' ...` module_code normalization moves to whichever
  CTEs carry SC-prefixed testcodes (typically `njsla_science`).
- Replace the single `state_fl` CTE with four CTEs (`fast`, `fsa`, `eoc`,
  `science`) on the same pattern.
- `college_assessments`, `practice_assessments`, `ap_assessments`: keep
  `SELECT DISTINCT`; replace existing comment blocks with the annotation.
- Final UNION ALL grows from 6 branches to 12; `all_assessments_unioned`
  partition_by stays the same
  (`assessment_type, source_assessment_id, module_code, test_type`). The
  downstream dedup remains as defense-in-depth against cross-branch collisions.

**`dim_assessment_administrations`:**

- Same per-staging-table CTE split for the eight non-illuminate administration
  CTEs (4 Pearson + 4 FLDOE). Each plain `SELECT DISTINCT` with annotation;
  literal `assessment_type` matching the dim's value.
- College and AP admin CTEs stay; replace comment blocks with the annotation
  phrase.
- The existing illuminate CTE and its TODO #3800 comment stay untouched.

**Hash composition unchanged.** `assessment_key` (in `dim_assessments`) and
`assessment_administration_key` (in `dim_assessment_administrations`) continue
to hash from `assessment_type, module_code, source_assessment_id, test_type` (+
admin-specific extras). The `assessment_type` literal split causes hashes to
diverge naturally — no hash-input list change required.

**Why one CTE per staging table** (over a single CTE with inner UNION ALL):
mirrors the existing per-`assessment_type` pattern already in `dim_assessments`
(illuminate / college / practice / ap each have their own CTE); makes
per-lineage logic — including the `SC05`-style module code normalization —
co-located with its source; lets reviewers diff a single CTE against its staging
table without indirection.

### Surveys marts — redirects

| Mart CTE                                      | Replace `ref(...)` with                                                                                                                                                                |
| --------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `dim_survey_questions.google_forms_questions` | `ref("int_google_forms__form__items")`                                                                                                                                                 |
| `dim_survey_questions.alchemer_questions`     | `ref("stg_alchemer__survey_question")`                                                                                                                                                 |
| `dim_survey_questions.manager_questions`      | (delete CTE + its UNION ALL branch)                                                                                                                                                    |
| `dim_surveys.google_forms_surveys`            | `ref("stg_google_forms__form")`                                                                                                                                                        |
| `dim_surveys.alchemer_surveys`                | `ref("stg_alchemer__survey")`                                                                                                                                                          |
| `bridge_survey_questions.google_forms_pairs`  | `ref("int_google_forms__form__items")`                                                                                                                                                 |
| `bridge_survey_questions.alchemer_pairs`      | `ref("stg_alchemer__survey_question")`                                                                                                                                                 |
| `bridge_survey_questions.manager_pairs`       | `ref("int_google_forms__form__items")` filtered to `form_id = '1cvp9RnYxbn-WGLXsYSupbEl2KhVhWKcOFbHR2CgUBH0'`, projecting the synthetic `'historic_alchemer_Manager_survey'` survey_id |

`archive_manager`, `archive_support`, `powerschool_family` hardcoded literals in
`dim_surveys` are untouched.

## Phase 0: Pre-merge BQ shape audit

Surveys redirects move grain from "appears in any response" to "exists as a
definition" — the row-count delta isn't predictable from inspection. Before
mart-side commits land, run these queries against prod to size each delta and
surface anomalies. Each query is a symmetric-difference count; if delta is
asymmetric in a way the redirect can't explain, escalate that redirect to a new
int.

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
      and safe_cast(survey_id as int) is not null  -- Alchemer rows only
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

(Resolve `<title_col>` from `stg_alchemer__survey` schema at query time.)

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

### G. Manager-pairs redirect equivalence

Confirm the redirect target produces the same set of
`('historic_alchemer_Manager_survey', shortname)` pairs that the current
`int_surveys__manager_survey_details`-sourced CTE produces:

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

`n_current_only` must be 0 (every historic Manager pair must exist in the Google
Form's items). Non-zero means the redirect drops pairs and needs a more complete
source.

### Phase-0 decision rules

For each redirect A–F:

- **Symmetric delta**: redirect safe. Document counts in PR body, proceed.
- **Large `n_target_only`**: many definitions never received responses.
  Expected; proceed.
- **Large `n_current_only`**: response rows reference a definition the target
  doesn't carry. Sample 10 unmatched rows; if legitimate historical data,
  escalate to a new int that unions definition with historical artifacts.
  Otherwise document and proceed.

Query G must return `n_current_only = 0` to proceed with the `manager_pairs`
redirect in commit 2.

## Verification

Per CLAUDE.md superpowers override:

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

**`dim_assessments` row-count delta**:

```sql
-- expected delta per region after lineage split
with
  nj_current as (
    select count(distinct testcode) as n
    from `teamster-332318.kipptaf_pearson.int_pearson__all_assessments`
    where testscalescore is not null
  ),
  nj_after as (
    select count(distinct (table_name, testcode)) as n
    from (
      select 'parcc' as table_name, testcode from `teamster-332318.kipptaf_pearson.stg_pearson__parcc` where testscalescore is not null
      union all select 'njsla', testcode from `teamster-332318.kipptaf_pearson.stg_pearson__njsla` where testscalescore is not null
      union all select 'njsla_science', testcode from `teamster-332318.kipptaf_pearson.stg_pearson__njsla_science` where testscalescore is not null
      union all select 'njgpa', testcode from `teamster-332318.kipptaf_pearson.stg_pearson__njgpa` where testscalescore is not null
    )
  )
select (select n from nj_after) - (select n from nj_current) as nj_added_rows
```

(Repeat the analogous query for FL across the four FLDOE staging tables.)
Compute these expected deltas before commit 1; the PR-branch row counts must
match. Any other delta = a partition-by or lineage-label bug.

**`dim_assessment_administrations` row-count delta** scales with the number of
(date, region, period) tuples carrying multiple lineages. Compute analogously
across the admin partition columns before commit 1.

**`assessment_type` lineage spot-check**:

```sql
select assessment_type, count(*) as n_module_codes
from `<pr_branch>.dim_assessments`
where assessment_type like 'state_%'
group by 1
order by 1
```

Must return exactly the 8 expected values: `state_fl_eoc`, `state_fl_fast`,
`state_fl_fsa`, `state_fl_science`, `state_nj_njgpa`, `state_nj_njsla`,
`state_nj_njsla_science`, `state_nj_parcc`. Any other value indicates a typo or
unintended staging-table-name suffix leak.

**Surveys row-count delta**: matches Phase-0 audit counts; any discrepancy is a
failed redirect.

## Files touched

**Modified**:

- `src/dbt/CLAUDE.md` — already done in commit `2008a52`
- `src/dbt/kipptaf/models/marts/dimensions/dim_assessments.sql`
- `src/dbt/kipptaf/models/marts/dimensions/dim_assessment_administrations.sql`
- `src/dbt/kipptaf/models/marts/dimensions/dim_survey_questions.sql`
- `src/dbt/kipptaf/models/marts/dimensions/dim_surveys.sql`
- `src/dbt/kipptaf/models/marts/bridges/bridge_survey_questions.sql`

**New**: none. Mart-side changes only; YAML untouched since contract surfaces
don't change.

**Removed dependencies**: marts no longer `ref()` `int_pearson__all_assessments`
or `int_fldoe__all_assessments`. The int models themselves stay (other consumers
exist or may exist).

## Risks

- **Cube / BI filters break on the `assessment_type` split.** Any Cube filter
  matching exact `'state_nj'` / `'state_fl'` returns nothing for state
  assessments. Mitigation: grep `src/cube/model/` for the literals; PR body
  lists every match plus the `LIKE 'state_nj_%'` migration pattern.
- **`assessment_administration_key` hash collision with the fct's pre-existing
  `'state'` literal.** Pre-existing — the fact already hashes `'state'` (not the
  region/lineage), so its admin-key never matched the dim's. Out of scope for
  this spec; flag and file follow-up.
- **Staging-table column drift.** The four Pearson staging tables share the
  columns the mart projects (`discipline`, `test_grade`, `subject`, `testcode`,
  `testscalescore`, `administration_window`, etc.) by way of
  `dbt_utils.union_relations` in the int — same for FLDOE. If any staging table
  drops or renames one of those columns, the per-staging-table CTE breaks at
  compile time (contract enforcement would catch it). Mitigation: dbt build
  catches before merge.
- **Pure-projection misclassification.** A CTE classified as pure projection but
  actually carrying a column that varies in the partition would silently
  coalesce divergent tuples. Mitigation: each new state CTE projects only
  literals, partition columns, and casts of partition columns — no per-row
  varying attributes. The annotation comment forces a switch to
  `dbt_utils.deduplicate` on any future addition of a non-derivable column.
- **Manager-pairs redirect loses pairs.** If the historic Manager Survey
  response data references shortnames the Google Form's items don't carry, the
  redirect drops rows. Mitigation: Phase 0 query G must return
  `n_current_only = 0`.

## Out of scope

- `dim_assessment_administrations.illuminate_administrations` (TODO #3800).
- Column renames, FK restructures, or hash recompositions on the mart side.
- Re-org of `int_assessments__assessments`.
- Pre-existing `fct_assessment_scores_enrollment_scoped` state-branch admin-key
  hash mismatch (uses `'state'` literal vs dim's region-split values). File
  separate issue.
- `int_surveys__manager_survey_details` post-#3899 cleanup (#3918).
- Removal of `archive_manager` / `archive_support` synthetic survey rows in
  `dim_surveys` — load-bearing for downstream filters.

## Sequencing

One PR, three commits plus a pre-commit Phase 0:

0. **Phase 0 (no commit)**: run BQ queries A–G against prod. Compute the
   expected `dim_assessments` / `dim_assessment_administrations` row-count
   deltas per "Verification". Paste all results into the PR body. Apply Phase-0
   decision rules; escalate any failed redirect to a new intermediate before
   commit 2.
1. **Assessments mart rewrite.** Single commit: replace `state_nj` and
   `state_fl` CTEs in both marts with the eight per-staging-table CTEs; annotate
   the surviving pure-projection DISTINCTs; remove stale illuminate comment.
   Verify expected non-zero row-count delta matches the Phase-0 formula.
2. **Surveys redirects.** All redirects across `dim_survey_questions`,
   `dim_surveys`, `bridge_survey_questions` (including `manager_pairs` redirect
   to gforms items). Drop the `manager_questions` CTE. Row-count delta against
   prod is expected to match Phase-0 counts; flag any discrepancy.
3. **Cube migration (if needed).** If Phase-0 cube grep surfaces filters on the
   old `assessment_type='state_nj'` / `'state_fl'` literals, swap to
   `LIKE 'state_nj_%'` patterns. If no matches, skip this commit.
