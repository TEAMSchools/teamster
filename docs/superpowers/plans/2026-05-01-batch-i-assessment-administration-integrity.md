# Batch I — assessment-administration integrity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.
>
> **REQUIRED CONTEXT FOR EVERY TASK:** Before any dbt work, invoke `Skill` with
> skill=`dbt:using-dbt-for-analytics-engineering`. For unit-test tasks, also
> invoke skill=`dbt:adding-dbt-unit-test`. For dbt CLI command formatting,
> invoke skill=`dbt:running-dbt-commands`.

**Goal:** Single atomic PR redefining `assessment_administration_key` (12→8
inputs) and `assessment_key` (6→4 inputs), pruning descriptive columns out of
the hash, consolidating period columns, adding Practice rows, and pushing all
`dbt_utils.deduplicate` workarounds upstream — closing #3774, #3775, #3782,
#3787, #3788.

**Architecture:** Phased execution: (0) verification gates that gate edits, (1)
additive upstream fixes, (2) atomic mart hash redefinition, (3) build +
relationships verification, (4) pre-merge audit, (5) PR.

**Tech Stack:** dbt-core 1.11+, BigQuery, dbt_utils, dbt-MCP / BigQuery-MCP /
GitHub-MCP / Dagster-MCP, trunk.

**Working directory:** Always `cd` to
`/workspaces/teamster/.worktrees/cbini/feat/claude-batch-i-assessment-admin-integrity`
before any command. The main repo and worktree have separate git state; commands
run from the main repo silently affect `main`.

**Spec reference:**
[`docs/superpowers/specs/2026-05-01-batch-i-assessment-administration-integrity-design.md`](../specs/2026-05-01-batch-i-assessment-administration-integrity-design.md)

---

## Phase 0 — Verification gates

These gates run **before** the corresponding implementation tasks. Each gate's
outcome may alter or block the corresponding edit.

### Task 0.1: G1 — sentinel collision check

**Goal:** Pick a sentinel value for replacing NULL `response_type_id` that
cannot collide with any real Illuminate id.

**Files:** None (BigQuery query only)

- [ ] **Step 1: Query the populated range of `response_type_id` in prod**

Use `mcp__bigquery__execute_sql`:

```sql
select
  min(response_type_id) as min_id,
  max(response_type_id) as max_id,
  count(*) as n_rows,
  countif(response_type_id is null) as n_null,
from `teamster-332318.kipptaf_illuminate.int_illuminate__agg_student_responses`
```

- [ ] **Step 2: Decide the sentinel value**

If `min_id >= 1`: use `coalesce(response_type_id, -1)`. Record decision:
`SENTINEL = -1`.

If `min_id < 1` (negative or zero ids exist): use
`coalesce(response_type_id, -1 * student_assessment_id)` — guarantees per-row
uniqueness across overall rows. Record decision:
`SENTINEL = -1 * student_assessment_id`.

Also note `n_null` — this is the expected count of rows that will be touched by
Task 1.1.

- [ ] **Step 3: Document outcome**

Append the sentinel decision and `n_null` to the spec under
`## Verification gates` → `### G1`. Commit with message
`docs(spec): record G1 sentinel decision`.

### Task 0.2: G2 — bridge-orphan additivity check

**Goal:** Confirm fixing the 6 bridge orphans on
`bridge_assessment_expectations_student_scoped` is purely additive on
`int_people__location_crosswalk` (adding rows, not mutating existing rows).

**Files:** None (BigQuery query only)

- [ ] **Step 1: Identify the 6 orphan ssa.site_id values**

Use `mcp__bigquery__execute_sql` to get the failing rows from the relationships
test:

```sql
select distinct ssa.site_id, ssa.region as expected_region
from `teamster-332318.kipptaf.bridge_assessment_expectations_student_scoped` as b
left join `teamster-332318.kipptaf.dim_assessment_administrations` as d
  on b.assessment_administration_key = d.assessment_administration_key
where d.assessment_administration_key is null
```

If the query depends on `ssa` being a CTE name not in the bridge, instead
inspect the bridge's source SQL to identify how `site_id` reaches the bridge,
then query the equivalent.

- [ ] **Step 2: For each `site_id`, check its presence in the crosswalk**

```sql
select
  c.site_id,
  c.location_name,
  c.region,
  c.location_dagster_code_location,
from `teamster-332318.kipptaf.int_people__location_crosswalk` as c
where c.site_id in (<list-from-step-1>)
```

- [ ] **Step 3: Decide additivity**

- All 6 `site_id`s **absent** from crosswalk → adding rows is additive. Proceed
  with Task 1.3.
- Any `site_id` **present** but resolves to a non-matching region → mutating
  existing rows. Drop Task 1.3 from this PR; open follow-up issue and reference
  #3633.

- [ ] **Step 4: Document outcome**

Append the per-site decision (proceed / drop) to the spec under `### G2`. Commit
with message `docs(spec): record G2 crosswalk additivity decision`.

### Task 0.3: G3 — FL season/window separability

**Goal:** Determine whether to populate `administration_period` from `season`
alone or from `concat(season, ' ', administration_window)`, and whether to keep
`season` and `administration_window` as descriptive columns.

**Files:** None (search-only)

- [ ] **Step 1: Search Tableau and Cube exposures for references to `season` or
      `administration_window`**

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-batch-i-assessment-admin-integrity
grep -rln 'administration_window\|\\bseason\\b' src/dbt/kipptaf/models/exposures/ src/cube/ 2>/dev/null
```

For each match, read the file to determine whether the consumer reads the column
from `dim_assessment_administrations`.

- [ ] **Step 2: Sample FL data to see if window adds info beyond season**

```sql
select season, administration_window, count(*) as n
from `teamster-332318.kipptaf_pearson.int_fldoe__all_assessments`
group by season, administration_window
order by season, administration_window
```

- [ ] **Step 3: Decide population**

- **Both columns are referenced separately by an active consumer** → populate
  `administration_period = concat(season, ' ', administration_window)`; retain
  `season` and `administration_window` as descriptive columns on
  `dim_assessment_administrations`.
- **Only `season` is referenced (or the season+window combinations are 1:1 with
  season)** → populate `administration_period = season`; drop both source
  columns from the dim.

- [ ] **Step 4: Document outcome**

Append decision to spec under `### G3`. Commit.

### Task 0.4: G4 — superscore drift root cause (#3775)

**Goal:** Determine whether the superscore drift in
`int_assessments__college_assessment` has an additive upstream fix (fold into
this PR) or requires a non-additive mutation (split out to a separate PR).

**Files:** None (BigQuery diagnostic only)

- [ ] **Step 1: Confirm the drift surface**

```sql
with dups as (
  select
    student_number,
    score_type,
    test_date,
    rn_highest,
    count(distinct superscore) as n_distinct_superscore,
    count(distinct scale_score) as n_distinct_scale_score,
    count(*) as n_rows,
  from `teamster-332318.kipptaf.int_assessments__college_assessment`
  group by student_number, score_type, test_date, rn_highest
  having count(*) > 1
)
select
  countif(n_distinct_superscore > 1 and n_distinct_scale_score = 1) as superscore_drift_groups,
  countif(n_distinct_superscore > 1 and n_distinct_scale_score > 1) as both_drift_groups,
  count(*) as total_dup_groups,
from dups
```

- [ ] **Step 2: Trace the lineage of `superscore`**

```bash
grep -rn 'superscore' src/dbt/kipptaf/models/assessments/intermediate/ src/dbt/kipptaf/models/college_board/ src/dbt/kipptaf/models/kippadb/
```

Read the upstream models (`int_kippadb__standardized_test_unpivot`,
`int_collegeboard__psat_unpivot`, any model with a `superscore` window function)
and identify any window function whose `order by` is non-deterministic (i.e.,
includes a column that has ties within the partition).

- [ ] **Step 3: Categorize the root cause and decide**

- **Source row duplication** (e.g., `int_kippadb__standardized_test_unpivot`
  produces multiple rows for one logical superscore that differ only on a
  non-key column) — additive fix possible (dedupe upstream with a deterministic
  tiebreaker on a stable column). Fold into this PR as Task 1.4.
- **Non-deterministic window order** (e.g.,
  `row_number() over (... order by created_at desc)` where multiple rows share
  `created_at`) — additive fix possible (add a tiebreaker column). Fold into
  this PR as Task 1.4.
- **Real bug in superscore math** — non-additive (changes existing values).
  Split to separate PR; document finding in spec under `### G4`; this umbrella
  keeps the existing dedup tiebreaker.

- [ ] **Step 4: Document outcome**

Append decision (`fold` with proposed fix, or `split` with finding) to spec
under `### G4`. If `fold`, add Task 1.4 to this plan. Commit.

### Task 0.5: Phase 0 commit checkpoint

- [ ] **Step 1: Verify all G1-G4 outcomes recorded**

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-batch-i-assessment-admin-integrity
git log --oneline | head -10
```

Expected: 4 spec-update commits for G1, G2, G3, G4 outcomes (in addition to
prior spec commits).

- [ ] **Step 2: Push branch to remote**

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-batch-i-assessment-admin-integrity
.trunk/tools/trunk check --ci
git push
```

Trunk hooks are not installed in worktrees — `trunk check --ci` must run before
push.

---

## Phase 1 — Additive upstream changes

These tasks edit models outside `marts/`. Each must be additive: existing values
unchanged; only previously-NULL or absent rows mutate.

### Task 1.1: Add sentinel `response_type_id` to `int_illuminate__agg_student_responses`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/illuminate/dlt/intermediate/int_illuminate__agg_student_responses.sql`
- Modify:
  `src/dbt/kipptaf/models/illuminate/fivetran/intermediate/int_illuminate__agg_student_responses.sql`
  (if it exists; verify with grep)

**Note:** Two same-named models exist (DLT and Fivetran lineages). Verify which
is the canonical source feeding `int_assessments__response_rollup` via
`grep "ref(\"int_illuminate__agg_student_responses\")" src/dbt/kipptaf/models/`.
Only edit the active one; leave any disabled variant untouched.

- [ ] **Step 1: Read the current file**

Use Read on the file path identified above. Locate the `select` block that emits
`response_type_id`.

- [ ] **Step 2: Apply the sentinel**

Replace `response_type_id` with
`coalesce(response_type_id, <SENTINEL_FROM_G1>) as response_type_id` in the
final select. Preserve column ordering (ST06).

If the value comes from a CTE, push the coalesce into the CTE so all downstream
selects see a non-NULL value.

- [ ] **Step 3: Run the model**

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-batch-i-assessment-admin-integrity
uv run dbt run --select int_illuminate__agg_student_responses --project-dir src/dbt/kipptaf --target dev --defer --state src/dbt/kipptaf/target/prod/
```

Expected: `Completed successfully`.

- [ ] **Step 4: Verify NULL-elimination**

```sql
select countif(response_type_id is null) as n_null, count(*) as n_total
from `<dev_schema>.int_illuminate__agg_student_responses`
```

Expected: `n_null = 0`. The `n_total` should match prod within drift tolerance.

- [ ] **Step 5: Run tests**

```bash
uv run dbt test --select int_illuminate__agg_student_responses --project-dir src/dbt/kipptaf --target dev
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/dbt/kipptaf/models/illuminate/.../int_illuminate__agg_student_responses.sql
git commit -m "fix(dbt): populate sentinel response_type_id for overall-score rows

Replaces NULL response_type_id with sentinel <VALUE> so downstream
uniqueness tests on (illuminate_student_id, assessment_id, response_type_id)
no longer collapse all overall rows onto NULL=NULL.

Refs #3782."
```

### Task 1.2: Re-declare grain on `int_assessments__response_rollup`

**Files:**

- Modify: `src/dbt/kipptaf/models/assessments/intermediate/properties.yml` (or
  `int_assessments__response_rollup.yml` — verify with
  `find ... -name "*.yml" | xargs grep -l "int_assessments__response_rollup"`)

- [ ] **Step 1: Find the properties file**

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-batch-i-assessment-admin-integrity
grep -rln "name: int_assessments__response_rollup" src/dbt/kipptaf/models/assessments/
```

- [ ] **Step 2: Read the current properties**

Use Read on the file. Locate the `data_tests:` block at model level for
`int_assessments__response_rollup`.

- [ ] **Step 3: Update the uniqueness test**

Replace the existing `dbt_utils.unique_combination_of_columns` block with:

```yaml
data_tests:
  - dbt_utils.unique_combination_of_columns:
      arguments:
        combination_of_columns:
          - illuminate_student_id
          - assessment_id
          - response_type_id
```

Update the model `description:` if it asserts a different grain.

- [ ] **Step 4: Build the model and run tests**

```bash
uv run dbt build --select int_assessments__response_rollup --project-dir src/dbt/kipptaf --target dev --defer --state src/dbt/kipptaf/target/prod/
```

Expected: Test PASSES at the new grain (because Task 1.1's sentinel eliminated
the NULL-collision dupe vector). If test FAILS with violation count > 0, the
dupes have a separate root cause not covered by Task 1.1 — do **not** add a
`dbt_utils.deduplicate` workaround. Stop and investigate: query the failing
groups and identify the structural source of duplication. Add a follow-up
sub-task here documenting the root cause and fix.

- [ ] **Step 5: Commit**

```bash
git add src/dbt/kipptaf/models/assessments/intermediate/properties.yml
git commit -m "fix(dbt): re-declare int_assessments__response_rollup natural grain

Changes uniqueness test from (illuminate_student_id, assessment_id,
response_type, response_type_id, response_type_code, powerschool_school_id)
to (illuminate_student_id, assessment_id, response_type_id). The prior key
included redundant response_type/code columns and the wrong key column
(response_type vs response_type_id), generating 1014 false-positive
violations.

Refs #3782."
```

### Task 1.3: ~~Add missing rows to `int_people__location_crosswalk`~~ — DROPPED

G2 outcome: the 6 bridge orphans are cross-region administrations, not crosswalk
gaps. They fold into the same Ops/catalog handoff as the 43 fact orphans. No
code change required in this PR. The bridge orphans are added to the bucketed
orphan report posted to #3774 in Task 5.1.

### Task 1.4: ~~Superscore drift fix~~ — DROPPED

G4 outcome: split. Diagnosis (root cause, evidence queries, quantified impact,
proposed one-line fix) posted to
[#3775 comment 4361532388](https://github.com/TEAMSchools/teamster/issues/3775#issuecomment-4361532388).
The fix is value-mutating (14 ACT students lose 1–6 superscore points), so it's
paused for expert review and ships in a follow-up PR. #3775 stays open.

### Task 1.5: Phase 1 push checkpoint

- [ ] **Step 1: Run trunk check on full worktree**

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-batch-i-assessment-admin-integrity
.trunk/tools/trunk check --ci
```

Fix any issues. Re-run until clean.

- [ ] **Step 2: Push**

```bash
git push
```

---

## Phase 2 — Atomic mart hash redefinition

These edits are interlocking. Aim to land them in close succession on the branch
(one commit per file is fine, but do not push between them — push the whole
phase as one batch). Every consumer of `assessment_administration_key` and
`assessment_key` must use the matching new hash composition.

### Task 2.1: Update `dim_assessments` — add `test_type`, redefine `assessment_key`

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_assessments.sql`
- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_assessments.yml`

- [ ] **Step 1: Read current files**

Read both files in full.

- [ ] **Step 2: Identify the source CTEs that feed `dim_assessments`**

Most likely it derives from the same `int_assessments__*` lineages as
`dim_assessment_administrations`. Map each branch.

- [ ] **Step 3: Add `test_type` per branch**

- Official college branch (`int_assessments__college_assessment`) →
  `'Official' as test_type`
- Practice college branch (add CTE for
  `int_assessments__college_assessment_practice` if not already present) →
  `'Practice' as test_type`
- All other branches → `cast(null as string) as test_type`

Set `test_type` in each branch CTE and union it through.

- [ ] **Step 4: Redefine `assessment_key` hash to 4 inputs**

Replace the existing `generate_surrogate_key` call with:

```sql
{{
    dbt_utils.generate_surrogate_key([
        "assessment_type",
        "module_code",
        "source_assessment_id",
        "test_type",
    ])
}} as assessment_key,
```

If `dim_assessments` doesn't yet carry `source_assessment_id`, add it from the
same per-branch sources used in Task 2.2 (Illuminate populates `assessment_id`;
others NULL).

- [ ] **Step 5: Update properties.yml**

- Add `test_type` column with `description`, `data_type: string`,
  `config.meta.contains_pii: false`.
- If `source_assessment_id` is added, document it (with `description` explaining
  it's an Illuminate-branch discriminator).
- Update the model `description:` to note the hash composition change.

- [ ] **Step 6: Verify the file builds**

Wait until Task 2.2 completes (downstream consumers may break view validation if
dim_assessments builds before dim_assessment_administrations under the new
schema). Build comes in Task 2.6.

- [ ] **Step 7: Commit (do not push yet)**

```bash
git add src/dbt/kipptaf/models/marts/dimensions/dim_assessments.sql \
        src/dbt/kipptaf/models/marts/dimensions/properties/dim_assessments.yml
git commit -m "feat(dbt): add test_type to dim_assessments; prune assessment_key hash

Adds test_type column ('Official'/'Practice'/NULL) to dim_assessments and
includes it in assessment_key. Prunes title, subject_area, scope, and
grade_level from assessment_key (functionally determined by module_code).

Hash composition changes per marts/CLAUDE.md hash-change discipline rule
3 (composition).

Refs #3787."
```

### Task 2.2: Update `dim_assessment_administrations`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/dim_assessment_administrations.sql`
- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_assessment_administrations.yml`

This is the largest single edit. Multiple coupled changes; do them in one
commit.

- [ ] **Step 1: Read current SQL and properties**

- [ ] **Step 2: Make all SQL changes in one Edit pass**

Apply these structural changes:

1. **Drop the `illuminate_deduped` CTE** (lines 19-33 of current file). Update
   the `illuminate_administrations` CTE to read from `illuminate_unnested`
   directly.

2. **Add `assessment_id as source_assessment_id` to `illuminate_unnested`**
   (carry through from `int_assessments__assessments`).

3. **Add a `practice_administrations` CTE** unioning
   `int_assessments__college_assessment_practice`, mirroring the existing
   `college_administrations` CTE structure. Set `'Practice' as test_type` on
   Practice rows and `'Official' as test_type` on the existing
   `college_administrations`.

4. **Replace `administration_round`, `season`, `administration_window` with
   single `administration_period`**, populated per-branch:
   - Illuminate: `cast(null as string) as administration_period`
   - State NJ: `if(\`period\` = 'FallBlock', 'Fall', \`period\`) as
     administration_period`
   - State FL: per G3 outcome (either `season as administration_period` or
     `concat(season, ' ', administration_window) as administration_period`)
   - College (Official + Practice):
     `administration_round as administration_period`
   - AP: `cast(null as string) as administration_period`

   Drop the three original columns from each CTE's select. If G3 said retain FL
   `season`/`administration_window` as descriptive columns, keep those two on
   the FL CTE only and NULL on others.

5. **Add `source_assessment_id` to every CTE select**. Illuminate →
   `assessment_id`. All others → `cast(null as int64) as source_assessment_id`
   (match the `assessment_id` type from `int_assessments__assessments`).

6. **Add `test_type` to every CTE select**. College Official → `'Official'`.
   College Practice → `'Practice'`. All others →
   `cast(null as string) as test_type`.

7. **Rename AP `assessment_type` from `'college'` to `'ap'`** in the
   `ap_administrations` CTE.

8. **Replace the final `generate_surrogate_key` calls** with:

```sql
{{
    dbt_utils.generate_surrogate_key([
        "assessment_type",
        "module_code",
        "administered_date",
        "academic_year",
        "region",
        "administration_period",
        "source_assessment_id",
        "test_type",
    ])
}} as assessment_administration_key,

{{
    dbt_utils.generate_surrogate_key([
        "assessment_type",
        "module_code",
        "source_assessment_id",
        "test_type",
    ])
}} as assessment_key,
```

9. **Update the final `select` column list** — replace `administration_round`,
   `season`, `administration_window` outputs with `administration_period` (and
   `season`/`administration_window` if G3 retains them). Add
   `source_assessment_id` and `test_type` as degenerate output columns.

- [ ] **Step 3: Update properties.yml**

- Remove `administration_round`, `season`, `administration_window` columns (or
  only `administration_round` if G3 retained the others).
- Add `administration_period` column with description, `data_type: string`.
- Add `source_assessment_id` column with description ("Illuminate-branch
  discriminator carrying source assessment_id; NULL elsewhere"),
  `data_type: int64`.
- Add `test_type` column with description ("'Official' / 'Practice' for college;
  NULL elsewhere"), `data_type: string`.
- Update model `description:` to note the new hash composition and the
  Illuminate one-row-per-`assessment_id` semantics.
- Update `accepted_values` test on `assessment_type` (if present) to add `'ap'`
  and confirm `'college'` still applies.

- [ ] **Step 4: Commit (do not push yet)**

```bash
git add src/dbt/kipptaf/models/marts/dimensions/dim_assessment_administrations.sql \
        src/dbt/kipptaf/models/marts/dimensions/properties/dim_assessment_administrations.yml
git commit -m "feat(dbt): redefine assessment_administration_key; add Practice rows

Major changes to dim_assessment_administrations:
- Drop illuminate_deduped CTE — region-copies are distinct assessments
  in the source and must remain distinct admin rows.
- Add source_assessment_id as Illuminate-branch discriminator
  (one admin row per Illuminate assessment_id).
- Add practice_administrations CTE for SAT/ACT Practice scores.
- Collapse administration_round/season/administration_window into single
  administration_period column.
- Rename AP assessment_type from 'college' to 'ap' to prevent hash
  collision under pruned hash inputs.
- Prune assessment_administration_key from 12 to 8 inputs:
  drop title, subject_area, scope, grade_level (functionally determined
  by module_code/source_assessment_id).
- Prune assessment_key from 6 to 4 inputs.

Hash composition changes per marts/CLAUDE.md hash-change discipline
rules 3 (composition) and 5 (structural add).

Refs #3782, #3787, #3788."
```

### Task 2.3: Update `fct_assessment_scores_student_scoped`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_student_scoped.sql`
- Modify:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_assessment_scores_student_scoped.yml`

- [ ] **Step 1: Read current files**

- [ ] **Step 2: Identify per-branch admin-key construction**

The fact computes `assessment_administration_key` by re-hashing the same inputs
as the dim. Locate every `generate_surrogate_key` call and trace each branch's
input source.

- [ ] **Step 3: Add Practice CTE**

Mirror the existing Official college CTE for
`int_assessments__college_assessment_practice`. Set `'Practice' as test_type`;
existing Official sets `'Official' as test_type`.

- [ ] **Step 4: Rebuild the admin-key hash to 8 inputs**

Replace the existing call with:

```sql
{{
    dbt_utils.generate_surrogate_key([
        "assessment_type",
        "module_code",
        "administered_date",
        "academic_year",
        "region",
        "administration_period",
        "source_assessment_id",
        "test_type",
    ])
}} as assessment_administration_key,
```

Wrap in the nullable-FK `if(...)` pattern only if the inputs may be NULL in
their entirety; otherwise leave bare.

- [ ] **Step 5: Rebuild the assessment-key hash to 4 inputs (if present)**

Same pattern as the dim.

- [ ] **Step 6: Update the final select column list**

If the fact previously selected
`administration_round`/`season`/`administration_window` for any reason
(degenerate columns), drop or replace per G3.

- [ ] **Step 7: Update properties.yml**

Adjust column list, descriptions, and any `accepted_values` tests.

- [ ] **Step 8: Commit**

```bash
git add src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_student_scoped.sql \
        src/dbt/kipptaf/models/marts/facts/properties/fct_assessment_scores_student_scoped.yml
git commit -m "feat(dbt): rebuild fct_assessment_scores_student_scoped admin-key; add Practice

Adds Practice CTE (int_assessments__college_assessment_practice) and
rebuilds assessment_administration_key with the new 8-input hash to
match dim_assessment_administrations.

Refs #3787."
```

### Task 2.4: Update `fct_assessment_scores_enrollment_scoped`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_enrollment_scoped.sql`
- Modify:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_assessment_scores_enrollment_scoped.yml`

- [ ] **Step 1: Read current files**

- [ ] **Step 2: Locate the `dbt_utils.deduplicate` workaround on
      `int_assessments__response_rollup`**

Per the spec, this is the workaround inserted by PR #3770 that should now be
removed. Identify the CTE and the relation it dedupes.

- [ ] **Step 3: Remove the workaround**

Replace the
`dbt_utils.deduplicate(relation="int_assessments__response_rollup", ...)` macro
call with a plain `select * from {{ ref("int_assessments__response_rollup") }}`
(or directly inline if the CTE was only used for the dedup). Trust the upstream
grain fix from Task 1.1+1.2.

- [ ] **Step 4: Rebuild the admin-key hash with `source_assessment_id`**

The Illuminate branch must pass `assessment_id` (from
`int_assessments__response_rollup`) as `source_assessment_id` into the hash.
Locate the existing `generate_surrogate_key` call and update inputs to:

```sql
{{
    dbt_utils.generate_surrogate_key([
        "assessment_type",
        "module_code",
        "administered_date",
        "academic_year",
        "region",
        "administration_period",
        "source_assessment_id",
        "test_type",
    ])
}} as assessment_administration_key,
```

Source per branch identical to dim and student_scoped fact.

- [ ] **Step 5: Update properties.yml**

- [ ] **Step 6: Commit**

```bash
git add src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_enrollment_scoped.sql \
        src/dbt/kipptaf/models/marts/facts/properties/fct_assessment_scores_enrollment_scoped.yml
git commit -m "feat(dbt): rebuild fct_assessment_scores_enrollment_scoped admin-key

Removes dbt_utils.deduplicate workaround on int_assessments__response_rollup
(grain fixed upstream by Tasks 1.1/1.2). Rebuilds
assessment_administration_key with new 8-input hash including
source_assessment_id from response_rollup.

Refs #3782, #3787."
```

### Task 2.5: Update `bridge_assessment_expectations_student_scoped` and `bridge_assessment_expectations_enrollment_scoped`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/bridges/bridge_assessment_expectations_student_scoped.sql`
- Modify:
  `src/dbt/kipptaf/models/marts/bridges/bridge_assessment_expectations_enrollment_scoped.sql`
- Modify:
  `src/dbt/kipptaf/models/marts/bridges/properties/bridge_assessment_expectations_student_scoped.yml`
- Modify:
  `src/dbt/kipptaf/models/marts/bridges/properties/bridge_assessment_expectations_enrollment_scoped.yml`

- [ ] **Step 1: Read all four files**

- [ ] **Step 2: Rebuild each bridge's admin-key hash**

Apply the same 8-input pattern. Each branch in each bridge populates
`source_assessment_id` and `test_type` per the dim's per-branch null pattern.

- [ ] **Step 3: Update properties.yml files**

- [ ] **Step 4: Commit**

```bash
git add src/dbt/kipptaf/models/marts/bridges/bridge_assessment_expectations_*.sql \
        src/dbt/kipptaf/models/marts/bridges/properties/bridge_assessment_expectations_*.yml
git commit -m "feat(dbt): rebuild bridge admin-keys to match new 8-input hash

Refs #3787."
```

### Task 2.6: Build full assessment lineage in dev

- [ ] **Step 1: Clone parent dims fresh from prod (defer-shadow guard)**

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-batch-i-assessment-admin-integrity
uv run dbt clone --select dim_assessments dim_assessment_administrations dim_dates dim_students dim_locations \
  --project-dir src/dbt/kipptaf --target dev --state src/dbt/kipptaf/target/prod/
```

Per `src/dbt/CLAUDE.md` "Stale dev tables shadow `--defer`" — clone parents
before testing FK relationships.

- [ ] **Step 2: Build the full lineage**

```bash
uv run dbt build \
  --select +fct_assessment_scores_student_scoped +fct_assessment_scores_enrollment_scoped \
           +bridge_assessment_expectations_student_scoped +bridge_assessment_expectations_enrollment_scoped \
  --project-dir src/dbt/kipptaf --target dev --defer --state src/dbt/kipptaf/target/prod/
```

Expected: builds succeed; relationships tests run.

- [ ] **Step 3: Capture the relationships WARN/ERROR set**

Note any test failures. Specifically expect:

- `fct_assessment_scores_enrollment_scoped.assessment_administration_key → dim_assessment_administrations`
  — should drop from 43 toward 0 if cross-region orphans were Ops-fixable
  post-merge; persistent residual is the soft-gate set.
- `bridge_assessment_expectations_*.assessment_administration_key → dim_assessment_administrations`
  — should be 0 after Task 1.3.
- Uniqueness on `assessment_administration_key` — must PASS in
  `dim_assessment_administrations` (no dupes after the discriminator fix).

If uniqueness FAILS: the new hash composition still has collisions. Stop and
diagnose with:

```sql
select assessment_administration_key, count(*) n
from `<dev_schema>.dim_assessment_administrations`
group by 1 having count(*) > 1
```

- [ ] **Step 4: Generate the bucketed cross-region orphan report**

```sql
with orphans as (
  select f.assessment_administration_key, f.region as student_region,
         f.title, f.assessment_type, f.module_code, f.administered_date,
         f.academic_year, f.student_number,
  from `<dev_schema>.fct_assessment_scores_enrollment_scoped` as f
  left join `<dev_schema>.dim_assessment_administrations` as d
    on f.assessment_administration_key = d.assessment_administration_key
  where d.assessment_administration_key is null
),
-- For each orphan, find what regions ARE declared for the same assessment
declared as (
  select d.module_code, d.administered_date, d.academic_year, d.assessment_type,
         array_agg(distinct d.region ignore nulls) as declared_regions,
  from `<dev_schema>.dim_assessment_administrations` as d
  group by 1,2,3,4
)
select o.*, dc.declared_regions
from orphans as o
left join declared as dc
  on o.module_code = dc.module_code
  and o.administered_date = dc.administered_date
  and o.academic_year = dc.academic_year
  and o.assessment_type = dc.assessment_type
order by o.assessment_type, o.module_code, o.student_region
```

Save report (deidentified — no `student_number` to issue body, only counts and
bucketing) to `.claude/scratch/3774-orphan-report.md`. PII goes only to local
artifacts per project conventions.

- [ ] **Step 5: Commit and push Phase 2**

```bash
.trunk/tools/trunk check --ci
git push
```

---

## Phase 3 — dbt Cloud CI verification

### Task 3.1: Trigger dbt Cloud CI run on the PR branch

The push from Task 2.6 triggers CI automatically via the GitHub webhook. Verify
it's running.

- [ ] **Step 1: Find the run**

Use `mcp__dbt__list_jobs_runs` (or similar) to get the latest run on the branch.
If no run, push an empty commit to retrigger:

```bash
git commit --allow-empty -m "ci: retrigger" && git push
```

- [ ] **Step 2: Wait for completion**

dbt Cloud CI runs `dbt build --select state:modified+ --full-refresh` against
staging. Expected runtime: 30-90 min for this blast radius.

- [ ] **Step 3: Capture warnings**

Use `mcp__dbt__get_job_run_error` with `warning_only=true` to surface any test
warnings (status=Success doesn't mean warning-free).

Save the WARN list to `.claude/scratch/3774-ci-warnings.md`.

---

## Phase 4 — Pre-merge issue-resolution audit

Implements spec section "Pre-merge issue-resolution audit" (A1-A4).

### Task 4.1: A1 — closure confirmation

- [ ] **Step 1: For each of #3774, #3775, #3782, #3787, #3788**

Walk the issue's acceptance checklist (use `mcp__github__issue_read` to fetch).
For each checkbox item, mark Met / Met-with-residual / Not-met with evidence.

- [ ] **Step 2: Assemble closure table**

Format as markdown table; save to `.claude/scratch/3774-closure-audit.md`. This
becomes part of the PR description.

- [ ] **Step 3: Halt if any "Not met"**

If any acceptance item is unmet without explicit waiver, do not proceed to
merge. Either fix or document waiver rationale in the PR description.

### Task 4.2: A2 — dbt CI WARN review

- [ ] **Step 1: Pull last `main` CI run for comparison**

Same job, last run on `main` branch. Diff against the PR-branch WARN list
captured in Task 3.1 Step 3.

- [ ] **Step 2: Categorize each WARN**

| WARN | New / Unchanged / Cleared | Action |
| ---- | ------------------------- | ------ |

Append to `.claude/scratch/3774-closure-audit.md`.

- [ ] **Step 3: Triage new WARNs**

Each new WARN: fix in this PR, or open a follow-up issue and reference it.

### Task 4.3: A3 — follow-up issues

- [ ] **Step 1: List residuals from spec gates**

If G4 split out, file follow-up for #3775. If G2 dropped Task 1.3, file
follow-up referencing #3633.

- [ ] **Step 2: List newly-surfaced problems**

Anything Phase 2 / Phase 3 surfaced that isn't fixable inline.

- [ ] **Step 3: File issues via `mcp__github__issue_write`**

Each issue uses conventional-commit-typed labels and references this PR.

### Task 4.4: A4 — bonus closure scan

- [ ] **Step 1: Search the project board for keyword matches**

Use `mcp__github__search_issues` for: `assessment_administration_key`,
`assessment_key`, `int_assessments__response_rollup`,
`int_illuminate__agg_student_responses`, `int_people__location_crosswalk`.

- [ ] **Step 2: For each candidate**

Verify resolution against the issue's acceptance. If resolved, add to PR
description as `Bonus closes #NNNN — <reason>` and add `Closes #NNNN` to PR
body.

---

## Phase 5 — Pull request

### Task 5.1: Open PR

- [ ] **Step 1: Final trunk check**

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-batch-i-assessment-admin-integrity
.trunk/tools/trunk check --ci
```

- [ ] **Step 2: Compose PR body**

Use `.github/pull_request_template.md` as scaffold. Populate sections from the
audit artifacts:

- Summary: 3 bullets — hash redefinition, atomic batch I closure, soft-gate
  residual.
- Test plan: dbt build outputs, relationships test counts (before/after),
  uniqueness verification.
- Closure list: `Closes #3774, #3775, #3782, #3787, #3788` plus any A4 bonus
  closures.
- A1 audit table.
- A2 WARN diff.
- Cross-region orphan summary (counts only, no PII) with link to local report.
- Note: dbt Cloud CI requires `--full-refresh` for hash change.

- [ ] **Step 3: Open PR**

```bash
gh pr create --title "feat(dbt): batch I — assessment-administration integrity umbrella" \
  --body-file .claude/scratch/3774-pr-body.md
```

- [ ] **Step 4: Post bucketed cross-region orphan report as comment on #3774**

Use `mcp__github__add_issue_comment` to post the deidentified bucketed report to
#3774 (the PR description should reference it). PII (student_number) stays
local; comment posts (assessment_type, module_code, declared_regions,
student_region) tuples with counts only.

- [ ] **Step 5: Verify PR body**

Per the project's "verify tool-call results for resource creation" rule — read
back the PR body and confirm it matches intent, especially the `Closes #` lines
(hash mistakes here lose closure links).

---

## Self-review

After all tasks complete:

1. **Spec coverage** — every spec section has a corresponding task: hash
   redefinitions (Tasks 2.1, 2.2, 2.3, 2.4, 2.5), per-branch null pattern (Task
   2.2 Step 2.5/2.6/2.7), AP rename (Task 2.2 Step 2.7), 3 additive upstream
   items (Tasks 1.1, 1.2, 1.3), G1-G4 (Tasks 0.1-0.4), pre-merge audit A1-A4
   (Tasks 4.1-4.4), Ops handoff (Task 5.1 Step 4 — orphan report).

2. **No placeholders** — every step has a concrete command or code block.

3. **Type consistency** — `source_assessment_id int64` matches the source
   `int_assessments__assessments.assessment_id` type (verify in Task 2.2).
   `test_type string` consistent across dim, fact, bridge.

4. **Conditional task gating** — Task 1.3 conditional on G2; Task 1.4
   conditional on G4. Both gates have explicit branch points.

5. **Worktree discipline** — every Bash command starts with
   `cd /workspaces/teamster/.worktrees/cbini/feat/claude-batch-i-assessment-admin-integrity`
   (or assumes prior `cd` in same task block).
