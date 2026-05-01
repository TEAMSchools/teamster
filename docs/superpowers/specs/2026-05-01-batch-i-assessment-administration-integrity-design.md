# Batch I — assessment-administration integrity (umbrella design)

Single atomic PR that consolidates batch I of the Data Team project board into
one hash redefinition of `assessment_administration_key` and `assessment_key`,
plus the additive upstream and mart changes that support it.

Closes [#3774](https://github.com/TEAMSchools/teamster/issues/3774),
[#3775](https://github.com/TEAMSchools/teamster/issues/3775),
[#3782](https://github.com/TEAMSchools/teamster/issues/3782),
[#3787](https://github.com/TEAMSchools/teamster/issues/3787),
[#3788](https://github.com/TEAMSchools/teamster/issues/3788) (with the
documented soft-gate residual on the 43 cross-region orphans of #3774, which
clears post-merge once Ops widens the AppSheet catalog).

## Context

PR [#3770](https://github.com/TEAMSchools/teamster/pull/3770) introduced
`dim_assessment_administrations` and the `assessment_administration_key`
surrogate hash, with several `dbt_utils.deduplicate` workarounds at the mart
layer and three temporal-grouping degenerate columns (`administration_round`,
`season`, `administration_window`). Five follow-ups were filed (#3774, #3775,
#3782, #3787, #3788). All five touch the admin-key surface area or its inputs.
Sequencing them as separate PRs would force `fct_assessment_scores_*` and
`bridge_assessment_expectations_*` to rebuild 3+ times with churning FK orphan
reports.

This umbrella ships the entire surface area in one atomic PR.

## Goals

- Redefine `assessment_administration_key` and `assessment_key` once, with
  pruned input lists that contain only load-bearing natural-key columns.
- Push all `dbt_utils.deduplicate` workarounds for assessments out of the marts
  layer, by either fixing upstream additively or restructuring the hash so the
  dedup is no longer required.
- Add SAT/ACT Practice rows to `dim_assessment_administrations` and
  `fct_assessment_scores_student_scoped`.
- Drive in-code FK orphans on `assessment_administration_key` to zero (43
  cross-region orphans remain as a soft-gate Ops handoff).

## Non-goals

- Module-level reporting rollup (Newark/Camden/Miami region-copies of an
  Illuminate module checkpoint stay distinct in the dim; if BI consumers ever
  ask for a logical-module rollup, that is a separate `rpt_*` ticket).
- Promoting `administration_period` from a degenerate column to a real
  `dim_administration_period` (deferred until period-level metadata accrues).
- Source-system catalog edits (Ops-owned; tracked post-merge against the 43
  cross-region orphan report).
- Crosswalk redesign for `int_people__location_crosswalk` beyond filling the 6
  missing rows (broader redesign tracked under #3633).

## Scope

### Hash redefinitions

`assessment_administration_key` — 12 inputs → **8 inputs**:

```sql
generate_surrogate_key([
  "assessment_type",
  "module_code",
  "administered_date",
  "academic_year",
  "region",
  "administration_period",
  "source_assessment_id",
  "test_type",
])
```

Removed inputs (functionally determined by `module_code` or
`source_assessment_id`, retained as descriptive columns on the dim): `title`,
`subject_area`, `scope`, `grade_level`.

Removed inputs (collapsed into `administration_period`): `administration_round`,
`season`, `administration_window`.

Added inputs:

- `administration_period` — single text column populated per branch from the
  source's native period concept (NJ `period`, FL `season`, College Board
  `administration_round`); NULL where the source has no period concept.
- `source_assessment_id` — Illuminate-branch discriminator carrying
  `int_assessments__assessments.assessment_id`; NULL elsewhere. Required because
  Newark/Camden/Miami region-copies of the same module checkpoint are genuinely
  distinct assessments in the source and must remain distinct admin rows.
- `test_type` — `'Official'` / `'Practice'` for college; NULL elsewhere.

`assessment_key` — 6 inputs → **4 inputs**:

```sql
generate_surrogate_key([
  "assessment_type",
  "module_code",
  "source_assessment_id",
  "test_type",
])
```

Removed inputs (functionally determined): `title`, `subject_area`, `scope`,
`grade_level`.

Added input: `test_type`.

#### Per-branch null pattern

| Branch             | type | module_code | admin_date | year | region | period | src_id | test_type |
| ------------------ | ---- | ----------- | ---------- | ---- | ------ | ------ | ------ | --------- |
| illuminate         | ✓    | ✗           | ✗          | ✗    | ✗      | ✗      | ✓      | ✗         |
| state_nj           | ✓    | ✓           | ✗          | ✓    | ✓      | ✓      | ✗      | ✗         |
| state_fl           | ✓    | ✓           | ✗          | ✓    | ✓      | ✓      | ✗      | ✗         |
| college (Official) | ✓    | ✓           | ✓          | ✗    | ✗      | ✓      | ✗      | ✓         |
| college (Practice) | ✓    | ✓           | ✓          | ✗    | ✗      | ✓      | ✗      | ✓         |
| ap                 | ✓    | ✓           | ✗          | ✓    | ✗      | ✗      | ✗      | ✗         |

NULLs hash to a placeholder; branches are collectively unique on the populated
fields.

#### AP `assessment_type` rename

Today AP rows in `dim_assessment_administrations` set
`assessment_type='college'`. With descriptive columns dropped from the hash, AP
and SAT/ACT could collide on `(assessment_type='college', module_code)` if any
AP `ps_ap_course_subject_code` happens to match a College Board `score_type`
string. Rename to `assessment_type='ap'`.

### Files touched

#### Additive upstream (outside `marts/`)

1. **`int_illuminate__agg_student_responses`** — replace NULL `response_type_id`
   with a sentinel for overall-score rows. Pre-edit verification: query the
   model for the populated range of `response_type_id`. If all real values are
   positive, sentinel `-1` is safe. Otherwise use
   `-1 * <stable per-row identifier>` to guarantee no collision with any
   existing id.

2. **`int_assessments__response_rollup`** properties.yml — re-declare the
   natural grain to `(illuminate_student_id, assessment_id, response_type_id)`.
   No SQL change. The current 1014-violation test was on the wrong grain;
   correcting the declared grain plus the upstream sentinel fix in (1) is
   expected to reduce dupe count to zero. Any residual is a real bug to
   investigate inline.

3. **`int_people__location_crosswalk`** — add missing rows for the 6
   `ssa.site_id` values surfaced by the bridge-orphan test on
   `bridge_assessment_expectations_student_scoped`. Pre-edit verification:
   confirm the gap is "missing rows," not "wrong region on existing rows." If
   the latter, drop from this PR and escalate to #3633.

#### Marts

4. **`dim_assessments`** — add `test_type` column; include in `assessment_key`
   hash. Source: Official college branch sets `'Official'`; Practice branch sets
   `'Practice'`; other branches NULL.

5. **`dim_assessment_administrations`**:
   - Drop the `illuminate_deduped` CTE (lines 22–33 of current SQL).
   - Add `source_assessment_id` to the Illuminate `illuminate_unnested` CTE
     (carry `assessment_id` through from `int_assessments__assessments`).
   - Add `practice_administrations` CTE unioning
     `int_assessments__college_assessment_practice`. Sets
     `test_type='Practice'`; Official sets `test_type='Official'`.
   - Replace `administration_round`, `season`, `administration_window` with
     single `administration_period`. NJ populates from
     `if(period='FallBlock','Fall',period)`; FL populates from `season` (see
     verification gate below for the FL `season`+`administration_window`
     separability question); College populates from `administration_round`.
   - Rename AP `assessment_type` from `'college'` to `'ap'`.
   - Apply pruned 8-input admin-key and 4-input assessment-key hash definitions.

6. **`fct_assessment_scores_student_scoped`** — add Practice CTE with the same
   8-element admin-key hash; rebuild `assessment_administration_key` for both
   Official and Practice branches.

7. **`fct_assessment_scores_enrollment_scoped`** — rebuild
   `assessment_administration_key` with the new 8-input hash, passing
   `source_assessment_id` (= `assessment_id` from
   `int_assessments__response_rollup`) through for the Illuminate branch; remove
   the `dbt_utils.deduplicate` workaround on `int_assessments__response_rollup`
   (relies on item 1 + item 2 fixing the upstream grain).

8. **`bridge_assessment_expectations_student_scoped`** — rebuild
   `assessment_administration_key` with the new hash inputs.

### Issue closure map

| Issue                                    | Resolved by                                                             | Notes                                                                                                                                |
| ---------------------------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| #3774 (43 cross-region fact orphans)     | Bucketed orphan report posted to issue body pre-merge                   | B′ soft-gate; closes when Ops widens `regions_assessed` post-merge. WARN-level test remains until Ops acts.                          |
| #3774 (6 bridge orphans)                 | Item 3                                                                  | Conditional on additive verification gate.                                                                                           |
| #3775 (superscore drift)                 | Pre-PR investigation; outcome documented inline in spec before PR opens | If a non-additive upstream fix is required, drops out of this umbrella into a separate PR.                                           |
| #3782 Surface 1 (response_rollup dupes)  | Items 1, 2; item 7's dedup removal                                      |                                                                                                                                      |
| #3782 Surface 2 (illuminate admin dupes) | Item 5 (Illuminate discriminator + drop dedup CTE)                      | Replaces the original "collapse upstream" framing — region-copies are genuinely distinct assessments and remain distinct admin rows. |
| #3787 (Practice rows)                    | Items 4, 5, 6                                                           | `test_type` lives at assessment level (Option B from #3787).                                                                         |
| #3788 (period normalization)             | Item 5 (option β: single degenerate column)                             | Closes as "implemented as degenerate; promote to dim later if metadata accrues."                                                     |

## Verification gates (pre-edit)

These run before the corresponding edit lands. Each blocks its edit if the
result invalidates the design assumption.

### G1 — sentinel collision check (item 1)

```sql
select min(response_type_id), max(response_type_id), count(*)
from `<dev_dataset>.int_illuminate__agg_student_responses`
where response_type_id is not null
```

Pass: `min(response_type_id) >= 0` → sentinel `-1` is safe. Fail: pick a per-row
synthetic sentinel.

### G2 — bridge-orphan additivity (item 3)

For each of the 6 `ssa.site_id` values in
`bridge_assessment_expectations_student_scoped`'s
`relationships(assessment_administration_key)` orphan list, query
`int_people__location_crosswalk`:

- If the `ssa.site_id` is **absent** from the crosswalk → adding rows is
  additive. Proceed.
- If the `ssa.site_id` is **present** but resolves to a region not matching the
  assessment's expected region → mutating existing rows. Drop from this PR;
  escalate to #3633.

### G3 — FL season/window separability (item 5)

Query Tableau and Cube exposures depending on `dim_assessment_administrations`
for references to either `season` or `administration_window`:

- If both are referenced separately → `administration_period` populates from
  `concat(season, ' ', administration_window)`, plus retain `season` and
  `administration_window` as descriptive columns on the dim (out of hash).
- If only `season` is referenced (or neither) → `administration_period`
  populates from `season` alone; both source columns drop.

### G4 — superscore drift root cause (#3775, pre-spec finalization)

Already partially covered by the dedup tiebreaker shipped in #3770.
Investigation: query `int_kippadb__standardized_test_unpivot` and
`int_collegeboard__psat_unpivot` for duplicate
`(student_number, score_type, test_date, rn_highest)` rows; inspect any window
functions in the superscore computation lineage for non-deterministic `order by`
clauses.

- If root cause is non-additive (e.g., a window-function fix that changes
  existing superscore values) → splits to a separate PR; this umbrella documents
  the finding and keeps the existing tiebreaker.
- If root cause is additive (e.g., upstream dedup that doesn't change surviving
  values) → fold into this PR.

## Risks

- **Hash blast radius.** Every consumer of `assessment_administration_key` and
  `assessment_key` rebuilds. Branch CI must run against all dependents
  (`fct_assessment_scores_*`, `bridge_assessment_expectations_*`). dbt Cloud CI
  will need a full-refresh; flag in PR description.
- **Stale defer tables on hash-changed dims.** Per project conventions,
  defer-mode dev builds may use stale dev tables for parents of modified models,
  producing false-positive `relationships` warnings. Pre-merge testing must
  include the parent dims via `--select` or explicit
  `dbt clone --select <parent>`.
- **PR review burden.** Single atomic PR is large. Mitigated by the per-issue
  closure map and the verification-gate structure — reviewers can audit each
  gate independently.
- **#3775 split risk.** If G4 fails non-additively, the umbrella ships with
  #3775 still open; not a blocker for the hash redefinition but reduces
  "everything closed in one PR" claim.

## Out of scope

- New `dim_administration_period` (option β chosen instead).
- `int_assessments__assessments` grain change (region-copies stay distinct).
- New module-level reporting rollup view.
- AppSheet catalog edits for the 43 cross-region orphans (Ops-owned).
- Broader `int_people__location_crosswalk` redesign (#3633).
- Hash changes to non-assessment marts.
