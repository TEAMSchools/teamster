# Strand-level assessment scores Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface DIBELS subtest and i-Ready domain scores in
`fct_assessment_scores_enrollment_scoped`, and unify `response_type` across
every source so `overall` means one thing and the not-taken population becomes
addressable.

**Architecture:** Breakdown rows populate the existing `response_type` family
with `response_type = 'group'`, keeping `module_code` anchored to the summary
grain so the FK to `dim_assessment_administrations` still resolves. Summary rows
across all sources are promoted from NULL to `'overall'`, and Illuminate's
expected-but-not-taken rows get a `'not_taken'` token, making `response_type`
non-nullable and an `accepted_values` test enforceable. The vendor surrogate key
gains `response_type_code` as an eighth input.

**Tech Stack:** dbt (BigQuery), Cube semantic layer, `dbt_utils`
(`generate_surrogate_key`, `deduplicate`).

**Spec:**
[`docs/superpowers/specs/2026-08-03-assessment-strand-level-scores-design.md`](../specs/2026-08-03-assessment-strand-level-scores-design.md)

## Global Constraints

- **Worktree.** All work happens in
  `/workspaces/teamster/.worktrees/anthonygwalters/feat/claude-assessment-strand-scores`
  on branch `anthonygwalters/feat/claude-assessment-strand-scores`. Use
  `git -C <worktree>` on every git call and
  `uv run dbt ... --project-dir <worktree>/src/dbt/kipptaf` on every dbt call.
  Never edit the main-checkout copy of a file.
- **Python and dbt always run under `uv run`.** Never bare `python`, `dbt`.
- **The unified `response_type` vocabulary is exactly** `not_taken`, `overall`,
  `group`, `standard`. No other value may appear in
  `fct_assessment_scores_enrollment_scoped`, and no row may be NULL.
- **Scope boundary.** `response_type` changes only in the fact's UNION branches.
  Do NOT modify `int_assessments__response_rollup` or the CARAT lineage —
  roughly fifteen downstream models filter the current vocabulary.
- **`module_code` stays anchored.** DIBELS rows use the literal `'Composite'`;
  i-Ready domain rows use `subject`. Never let `measure_standard` or
  `domain_name` flow into `module_code` — it orphans the FK to
  `dim_assessment_administrations`.
- **The vendor surrogate key hashes `response_type_code`, never
  `response_type_description`.** `measure_name` is coarser than
  `measure_standard`, so keying on the description collides NWF-WRC with
  NWF-CLS.
- **Never add a `not_null` test to `generate_surrogate_key` output** — it never
  returns NULL. Repo convention, `src/dbt/CLAUDE.md`.
- **Excluded rows:** `relative_placement = 'Not Assessed'` and
  `domain_name = 'comprehension_overall'` never enter the fact.
- **Do not run `trunk fmt` or `trunk check` manually except** on `.md` files
  before pushing, per `src/dbt/CLAUDE.md`. The pre-commit hook formats; the
  pre-push hook checks.
- **Verified prod baselines** (2026-08-28) that later assertions compare
  against: fact total 14,569,177; `response_type IS NULL` 1,441,444, of which
  Illuminate 1,073,422, i-Ready 240,749, DIBELS 57,546, state 62,378, STAR
  7,349. `int_iready__domain_unpivot` 1,635,032 rows; 1,572,858 after the
  `Not Assessed` and null filters; 1,453,102 after excluding
  `comprehension_overall`. DIBELS Benchmark rows: 58,124 Composite, 255,144
  subtest.

---

## File Structure

| File                                                                             | Responsibility                                            |
| -------------------------------------------------------------------------------- | --------------------------------------------------------- |
| `src/dbt/kipptaf/models/iready/intermediate/int_iready__domain_unpivot.sql`      | Add `illuminate_subject` pass-through                     |
| `.../iready/intermediate/properties/int_iready__domain_unpivot.yml`              | Column entry, `accepted_values`, unit-test fixture        |
| `src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_enrollment_scoped.sql` | All CTE, union, final-SELECT and surrogate-key changes    |
| `.../marts/facts/properties/fct_assessment_scores_enrollment_scoped.yml`         | `accepted_values` on `response_type`, column descriptions |
| `src/cube/model/cubes/student_assessments/student_assessment_scores.yml`         | Measure filters, rollup dimension, comments, pre-agg name |
| `src/cube/model/views/student_assessments/student_assessment_scores_view.yml`    | View description                                          |
| `src/cube/mcp/project_knowledge/assessment-cube-reference.md`                    | Eight vocabulary and per-source locations                 |
| `src/cube/mcp/project_knowledge/assessment-cube-orchestrator.md`                 | Filter protocol                                           |
| `src/cube/mcp/project_knowledge/README.md`                                       | Filter protocol restated                                  |
| `docs/superpowers/plans/2026-08-28-strand-scores-baseline.md`                    | Captured pre-change baseline (new)                        |
| `docs/superpowers/plans/2026-08-28-strand-scores-rollback.md`                    | Rollback runbook (new)                                    |

Task order matters: Task 1 unblocks Task 4; Task 2 must complete before any
model change merges; Task 5 must precede Task 7's measure filter.

---

### Task 1: Add `illuminate_subject` to `int_iready__domain_unpivot`

The vendor branch joins the resolver on
`va.illuminate_subject = sr.subject_area`. Without this column every i-Ready
domain row drops at the INNER JOIN.

**Files:**

- Modify:
  `src/dbt/kipptaf/models/iready/intermediate/int_iready__domain_unpivot.sql`
- Modify:
  `src/dbt/kipptaf/models/iready/intermediate/properties/int_iready__domain_unpivot.yml`

**Interfaces:**

- Produces: `int_iready__domain_unpivot.illuminate_subject` (STRING), values
  `'Text Study'` and `'Mathematics'`, consumed by Task 4.

- [ ] **Step 1: Add the column to both select lists**

In the `domain_unpivot` CTE select list (after `` `subject` ``) and in the final
`SELECT` (same relative position), add:

```sql
    illuminate_subject,
```

The column already exists on `int_iready__diagnostic_results`, derived there as
`case wc.subject when 'Reading' then 'Text Study' when 'Math' then 'Mathematics' end`.
Do NOT re-derive it here.

- [ ] **Step 2: Add the properties entry**

In `properties/int_iready__domain_unpivot.yml`, under `columns:`:

```yaml
- name: illuminate_subject
  data_type: string
  description: >-
    Illuminate course-subject mapping for the diagnostic's subject, passed
    through from int_iready__diagnostic_results. Required by
    fct_assessment_scores_enrollment_scoped, whose vendor branch joins
    int_assessments__resolved_section_enrollments on subject_area.
```

- [ ] **Step 3: Add `illuminate_subject` to the unit-test `given` block**

The `given` block is `format: sql` and is used verbatim, so the model's new
reference fails to resolve unless the mock supplies it. Add `illuminate_subject`
to the fixture's `SELECT` list.

- [ ] **Step 4: Add `illuminate_subject` to ALL twelve `expect` rows**

dbt derives the compared column set from `expected_rows[0].keys()`, so omitting
it from every row compiles and passes with the column silently uncompared — that
is a coverage hole, not a pass. Add it to all twelve, **in the same key order in
every row**: BigQuery unions positionally, and the neighboring columns are all
STRING, so an inconsistent order lands values in the wrong columns without
error.

- [ ] **Step 5: Run the unit test**

```bash
uv run dbt test --project-dir /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-assessment-strand-scores/src/dbt/kipptaf \
  --select int_iready__domain_unpivot
```

Expected: PASS.

- [ ] **Step 6: Build the model and confirm the column populates**

```bash
uv run dbt build --project-dir /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-assessment-strand-scores/src/dbt/kipptaf \
  --select int_iready__domain_unpivot
```

Expected: success, and `illuminate_subject` non-null on every row (values
`Text Study` / `Mathematics`).

- [ ] **Step 7: Commit**

```bash
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-assessment-strand-scores add -u
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-assessment-strand-scores commit -m "feat(dbt): pass illuminate_subject through int_iready__domain_unpivot

Refs #4708"
```

---

### Task 2: Capture the rollback baseline

Must complete before any model change merges. A rollback nobody can verify is
not a rollback.

**Files:**

- Create: `docs/superpowers/plans/2026-08-28-strand-scores-baseline.md`

**Interfaces:**

- Produces: the captured numbers Task 9 asserts against.

> **Dependency:** requires warehouse access. The BigQuery MCP was disconnected
> as of 2026-08-28 — reconnect it, or run these in the dbt Cloud IDE / `bq`,
> before starting.

- [ ] **Step 1: Run the four baseline queries**

```sql
-- 1. rows by source x response_type
select a.type as assessment_type, coalesce(f.response_type, '<null>') as response_type, count(*) as n
from kipptaf_marts.fct_assessment_scores_enrollment_scoped as f
inner join kipptaf_marts.dim_assessment_administrations as d
  on f.assessment_administration_key = d.assessment_administration_key
inner join kipptaf_marts.dim_assessments as a on d.assessment_key = a.assessment_key
group by 1, 2 order by 1, 2;

-- 2. proficiency by source
select a.type as assessment_type, count(*) as count_scores,
       countif(f.is_mastery) as sum_proficient,
       round(100 * countif(f.is_mastery) / nullif(count(*), 0), 2) as pct_proficient
from kipptaf_marts.fct_assessment_scores_enrollment_scoped as f
inner join kipptaf_marts.dim_assessment_administrations as d
  on f.assessment_administration_key = d.assessment_administration_key
inner join kipptaf_marts.dim_assessments as a on d.assessment_key = a.assessment_key
group by 1 order by 1;

-- 3. key sample for vendor rows (no PII -- keys are hashes)
select assessment_score_key from kipptaf_marts.fct_assessment_scores_enrollment_scoped
where response_type is null order by assessment_score_key limit 20;

-- 4. FK health
select countif(d.assessment_administration_key is null) as orphans, count(*) as n
from kipptaf_marts.fct_assessment_scores_enrollment_scoped as f
left join kipptaf_marts.dim_assessment_administrations as d
  on f.assessment_administration_key = d.assessment_administration_key;
```

- [ ] **Step 2: Record results in the baseline doc**

Write the four result sets into
`docs/superpowers/plans/2026-08-28-strand-scores-baseline.md` under headings
`Rows by source and response_type`, `Proficiency by source`,
`Vendor key sample`, `FK health`, each with the capture timestamp. Keys are
hashes and carry no PII; do not include `student_number` in any output.

- [ ] **Step 3: Capture the pre-aggregation state**

Record `proficiency_rollup`'s current partition count and total bytes, per the
`JOBS_BY_PROJECT` method in `src/cube/CLAUDE.md`. Add under `Pre-aggregation`.

- [ ] **Step 4: Commit**

```bash
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-assessment-strand-scores add -u
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-assessment-strand-scores commit -m "docs: capture pre-change baseline for strand-scores rollback

Refs #4708"
```

---

### Task 3: DIBELS subtests and the discriminator plumbing

Establishes the column plumbing through the whole vendor branch, and lands the
surrogate-key change. i-Ready summary rows keep NULL until Task 5; only DIBELS
gains breakdown rows here.

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_enrollment_scoped.sql`

**Interfaces:**

- Produces: `vendor_all.response_type`, `.response_type_code`,
  `.response_type_description`, consumed by Tasks 4 and 5.
- Produces: the eight-input vendor `assessment_score_key`.

- [ ] **Step 1: Rewrite the `dibels_scores` CTE**

Replace the CTE with the block in the spec's _DIBELS_ section. Key points:
`module_code` becomes the literal `'Composite'`; only
`and measure_standard = 'Composite'` leaves the `where` clause;
`assessment_type = 'Benchmark'` stays. Delete the now-inaccurate
`-- DIBELS benchmark composites are unique at this grain upstream` comment and
replace it with:

```sql
    -- Unique at the (student, year, period, date, measure_standard) grain --
    -- re-verified 2026-08-28 at the widened grain: 313,268 rows, 313,268
    -- distinct eight-input keys. No dedupe needed.
```

- [ ] **Step 2: Add the three columns to all three `vendor_all` branches**

`vendor_all` has explicit column lists. Add `response_type`,
`response_type_code`, `response_type_description` to the i-Ready, STAR and
DIBELS branches in the same position in each. The i-Ready and STAR branches have
no such columns upstream, so they take literals:

```sql
            cast(null as string) as response_type,
            cast(null as string) as response_type_code,
            cast(null as string) as response_type_description,
```

- [ ] **Step 3: Source the columns in the vendor final `SELECT`**

Replace the hardcoded NULLs (currently `cast(null as string) as response_type`
and `... as response_type_description`) with:

```sql
    va.response_type,
    va.response_type_code,
    va.response_type_description,
    cast(null as string) as response_type_root_description,
```

`response_type_root_description` stays NULL for every vendor row.

- [ ] **Step 4: Append `response_type_code` to the vendor surrogate key**

The key currently hashes exactly seven inputs. Add `"va.response_type_code"` as
the eighth and **last** entry. Position is load-bearing: the macro joins inputs
with `'-'`, and `'Reading Accuracy (ORF-Accu)'` contains that delimiter, which
is harmless only in final position.

- [ ] **Step 5: Build the model**

```bash
uv run dbt build --project-dir /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-assessment-strand-scores/src/dbt/kipptaf \
  --select fct_assessment_scores_enrollment_scoped
```

Expected: success, `unique` on `assessment_score_key` passes.

- [ ] **Step 6: Assert the DIBELS row counts**

```sql
select response_type, count(*) as n
from <target>.fct_assessment_scores_enrollment_scoped as f
inner join <target>.dim_assessment_administrations as d using (assessment_administration_key)
inner join <target>.dim_assessments as a using (assessment_key)
where a.type = 'dibels' group by 1;
```

Expected: `overall` ≈ 57,546 (unchanged from baseline) and `group` > 0. The
`overall` count must not move — a change means the `module_code` re-anchoring
altered summary rows.

- [ ] **Step 7: Commit**

```bash
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-assessment-strand-scores add -u
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-assessment-strand-scores commit -m "feat(dbt): add DIBELS subtest rows to the assessment scores fact

Refs #4708"
```

---

### Task 4: i-Ready domain rows

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_enrollment_scoped.sql`

**Interfaces:**

- Consumes: `int_iready__domain_unpivot.illuminate_subject` (Task 1),
  `vendor_all`'s three discriminator columns (Task 3).

- [ ] **Step 1: Add `iready_domain_scores_raw`**

Insert the CTE exactly as written in the spec's _The domain CTE_ section,
immediately after `iready_scores_raw`. Both exclusions are required:
`relative_placement != 'Not Assessed'` and
`domain_name != 'comprehension_overall'`.

- [ ] **Step 2: Add the three discriminator literals to `iready_scores_raw`**

Append to the anchor CTE, in a position you will mirror exactly in Step 3:

```sql
        cast(null as string) as response_type,
        cast(null as string) as response_type_code,
        cast(null as string) as response_type_description,
```

- [ ] **Step 3: Add `iready_all_raw`**

Union the anchor and the domain CTE with **explicit, identical column lists in
the same order in both branches**. Do not use `select *` — the two CTEs carry
different natural orders, and a positional union would swap `score_source` with
a discriminator silently before erroring one column later. Drop
`rn_subject_test`, which `int_iready__domain_unpivot` emits and the anchor
lacks.

- [ ] **Step 4: Re-target the dedupe and add the discriminator to its
      partition**

Change `relation="iready_scores_raw"` to `relation="iready_all_raw"` and add
`response_type_code` to `partition_by`, per the spec's block. Leave `order_by`
unchanged. Add to the existing `TODO(#4387)` comment:

```sql
    -- response_type_code joins the partition because domain rows deliberately
    -- share module_code with the subject-level anchor; without it all domains
    -- plus the anchor collapse to one row. NULL groups cleanly for anchors.
    -- Verified 2026-08-28: this partition still collapses 319,380 of 1,572,858
    -- eligible domain rows, 95.8% of which are fiscal-year re-pulls differing
    -- only in academic_year -- the intended #4387 behavior.
```

- [ ] **Step 5: Build and assert**

```bash
uv run dbt build --project-dir /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-assessment-strand-scores/src/dbt/kipptaf \
  --select fct_assessment_scores_enrollment_scoped
```

Expected: success, `unique` passes. Then assert i-Ready `overall` ≈ 240,749
(unchanged from baseline), `group` > 0, and that **no row** has
`response_type_code = 'comprehension_overall'`.

- [ ] **Step 6: Commit**

```bash
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-assessment-strand-scores add -u
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-assessment-strand-scores commit -m "feat(dbt): add i-Ready domain rows to the assessment scores fact

Refs #4708"
```

---

### Task 5: Unify `response_type` across every source

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_enrollment_scoped.sql`
- Modify:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_assessment_scores_enrollment_scoped.yml`

**Interfaces:**

- Produces: a non-nullable `response_type` over the vocabulary
  `[not_taken, overall, group, standard]`, consumed by Task 7's measure filter.

- [ ] **Step 1: Promote vendor summary rows to `'overall'`**

In `dibels_scores`, the `if(...)` already emits `'overall'` for Composite from
Task 3. In `iready_scores_raw` and the `vendor_all` STAR branch, change the
`response_type` literal from `cast(null as string)` to `'overall'`. Leave
`response_type_code` and `response_type_description` NULL on all three.

- [ ] **Step 2: Promote state rows to `'overall'`**

In the state final `SELECT`, change `cast(null as string) as response_type` to
`'overall' as response_type`. The other three `response_type*` columns stay
NULL.

- [ ] **Step 3: Split the internal branch**

In the `internal_assessments` CTE, `response_type` passes through from
`int_assessments__response_rollup`, where a scaffold row with no matching
response carries NULL. Replace the pass-through with:

```sql
            -- int_assessments__scaffold is the "expected to take" grain and
            -- response_rollup LEFT JOINs responses onto it, so a NULL
            -- response_type is a deliberate assigned-but-not-taken record,
            -- not a join defect. It gets its own token so the population is
            -- addressable and response_type stays non-nullable.
            coalesce(rr.response_type, 'not_taken') as response_type,
```

- [ ] **Step 4: Add the `accepted_values` test**

In the fact's properties file, under the `response_type` column:

```yaml
data_tests:
  - accepted_values:
      arguments:
        values: [not_taken, overall, group, standard]
  - not_null
```

`not_null` is correct here — `response_type` is a plain column, not
`generate_surrogate_key` output, and non-nullability is the invariant that makes
the vocabulary a contract.

- [ ] **Step 5: Build and assert the migration**

```bash
uv run dbt build --project-dir /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-assessment-strand-scores/src/dbt/kipptaf \
  --select fct_assessment_scores_enrollment_scoped
```

Expected: success; `accepted_values` and `not_null` pass. Then assert against
the Task 2 baseline, per `score_source`: `count(response_type = 'overall')`
after == `count(response_type is null)` before, and
`count(response_type = 'not_taken')` == 1,073,422.

- [ ] **Step 6: Commit**

```bash
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-assessment-strand-scores add -u
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-assessment-strand-scores commit -m "feat(dbt): unify response_type across every assessment source

Refs #4708"
```

---

### Task 6: Fact and upstream documentation

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_assessment_scores_enrollment_scoped.yml`
- Modify:
  `src/dbt/kipptaf/models/iready/intermediate/properties/int_iready__domain_unpivot.yml`

- [ ] **Step 1: Update the model description**

Change the grain sentence to state the response-type axis and the widened DIBELS
scope: one row per student × assessment × administration × response type, and
DIBELS covering Composite plus subtests.

- [ ] **Step 2: Rewrite the four `response_type*` column descriptions**

Each currently ends "Null for state assessments", which becomes false. Describe
the unified vocabulary, state that `response_type` is non-nullable, and note
that `response_type_code` carries `domain_name` for i-Ready and
`measure_standard` for DIBELS while `response_type_description` carries the
human label.

- [ ] **Step 3: Document the `is_mastery` null on subtests**

On the `is_mastery` column, add: `measure_standard_level_int` is null on 5,565
DIBELS subtest rows (0 on Composite), concentrated in the K-2 phonics measures,
so `is_mastery` is null there and those rows count in a proficiency denominator
without ever entering the numerator.

- [ ] **Step 4: Add `accepted_values` on `relative_placement`**

In `properties/int_iready__domain_unpivot.yml`:

```yaml
data_tests:
  - accepted_values:
      arguments:
        values:
          - 1 Grade Level Below
          - 2 Grade Levels Below
          - 3 or More Grade Levels Below
          - Early On Grade Level
          - Mid or Above Grade Level
          - Not Assessed
```

Without this, a reworded vendor label reads as _not proficient_ rather than
_unknown_, silently, across ~1.5M rows.

- [ ] **Step 5: Run the tests**

```bash
uv run dbt test --project-dir /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-assessment-strand-scores/src/dbt/kipptaf \
  --select fct_assessment_scores_enrollment_scoped int_iready__domain_unpivot
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-assessment-strand-scores add -u
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-assessment-strand-scores commit -m "docs(dbt): document the unified response_type vocabulary and guard the i-Ready labels

Refs #4708"
```

---

### Task 7: Cube model changes

**Files:**

- Modify:
  `src/cube/model/cubes/student_assessments/student_assessment_scores.yml`
- Modify:
  `src/cube/model/views/student_assessments/student_assessment_scores_view.yml`

- [ ] **Step 1: Filter `not_taken` out of the proficiency measures**

Add to `count_scores`, `_sum_proficient`, `_sum_proficient_formative`,
`_count_scores_formative`, `_sum_proficient_crq` and `_count_scores_crq`:

```yaml
- sql: "{CUBE}.response_type != 'not_taken'"
```

Update `count_scores`' description to say it counts scored responses and
excludes not-taken rows. Expected effect on the global unfiltered
`pct_proficient`: roughly 45.4% → 49.0%.

- [ ] **Step 2: Add `assessment_type` to `proficiency_rollup`**

Add `- student_assessments.assessment_type` to the rollup's `dimensions:` list,
with the comment that it is near-functionally-determined by `module_code`
(already present) so it adds close to zero rows, and that without it no
source-scoped query — the documented way to select i-Ready or DIBELS — can hit
the rollup.

- [ ] **Step 3: Rewrite the functional-determination comment**

The existing comment claims `response_type` and `response_type_description` are
determined by `response_type_code` with zero added rows. With the code populated
on breakdown rows that becomes true for the first time; say so, and note that
`overall` and `not_taken` rows share a NULL code and a NULL description, so the
mapping holds.

- [ ] **Step 4: Amend the `avg_scale_score` Grain clause**

Change "meaningful only within a single assessment source/subject/grade" to add
"and response type" — scoping to DIBELS and one subject now pools a Composite
score with an ORF words-per-minute rate.

- [ ] **Step 5: Bump the pre-aggregation name**

Rename `proficiency_rollup` to `proficiency_rollup_v2`. This forces one clean
rebuild. Without it, the ~12 yearly partitions rebuild independently and can
serve the old and new vocabulary simultaneously, so a multi-year query filtering
`response_type = 'overall'` returns partial history with no error.

- [ ] **Step 6: Update the view description**

`student_assessment_scores_view.yml` asserts the breakdown is Illuminate only.
Replace with the unified vocabulary and note that vendor breakdowns are
`'group'`.

- [ ] **Step 7: Validate on a branch staging deployment**

Per `src/cube/CLAUDE.md`, build the pre-aggregation on a branch staging
deployment before merge. Confirm partition count matches the baseline's and that
a `response_type = 'group'` + `assessment_type = 'iready'` query hits the rollup
— `/sql` should show `FROM prod_pre_aggregations.<rollup>`, not the fact.

- [ ] **Step 8: Commit**

```bash
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-assessment-strand-scores add -u
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-assessment-strand-scores commit -m "feat(cube): exclude not-taken rows from proficiency and add assessment_type to the rollup

Refs #4708"
```

---

### Task 8: Knowledge-base documentation

The knowledge docs are the primary consumer contract, and they deploy by
**manual re-upload** — merging does not publish them.

**Files:**

- Modify: `src/cube/mcp/project_knowledge/assessment-cube-reference.md`
- Modify: `src/cube/mcp/project_knowledge/assessment-cube-orchestrator.md`
- Modify: `src/cube/mcp/project_knowledge/README.md`

- [ ] **Step 1: Rewrite the eight `assessment-cube-reference.md` locations**

The global vocabulary block; the `notSet` instruction; the
`response_type_root_description` rationale; and the five per-source lines for
i-Ready, DIBELS, STAR, NJ state and FL state. Every one of them currently
asserts these sources carry `response_type = null`. Replace the `notSet` idiom
with `response_type = 'overall'` throughout.

- [ ] **Step 2: Correct the hard-coded row count**

The line asserting `null on all 302,907 i-Ready, DIBELS, and STAR rows` is stale
in both the number and the claim. Replace with a description of the vocabulary
rather than a count that will drift again.

- [ ] **Step 3: Fix the i-Ready dedup recipe**

The recipe instructs analysts to reduce to "one row per student per window",
which at the new grain collapses fourteen rows into one and destroys the feature
silently. Add that the dedup applies to `response_type = 'overall'` rows only.

- [ ] **Step 4: Update the two protocol files**

`assessment-cube-orchestrator.md` and `project_knowledge/README.md` both state
the explicit-`response_type`-filter protocol. Update both to the new vocabulary.

- [ ] **Step 5: Lint the markdown**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-assessment-strand-scores && \
  /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/cube/mcp/project_knowledge/*.md </dev/null
```

Fix anything but MD060 table padding and prettier reflow, which the commit hook
resolves.

- [ ] **Step 6: Commit**

```bash
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-assessment-strand-scores add -u
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-assessment-strand-scores commit -m "docs(cube): update the assessment knowledge base for the unified response_type

Refs #4708"
```

---

### Task 9: Rollback runbook and the merge gate

**Files:**

- Create: `docs/superpowers/plans/2026-08-28-strand-scores-rollback.md`

- [ ] **Step 1: Write the runbook**

Five numbered steps, each `1.` (markdownlint MD029 — fenced blocks restart the
list): revert the implementation commit range; full rebuild
(`uv run dbt build --select fct_assessment_scores_enrollment_scoped+`);
re-upload the prior knowledge-doc versions; rename the pre-aggregation back;
assert against the Task 2 baseline.

- [ ] **Step 2: Document what rollback does NOT undo**

`assessment_score_key` values for vendor rows do not return to their pre-change
values — the revert restores the seven-input key, while any external system that
persisted the eight-input values holds neither. State this plainly.

- [ ] **Step 3: Record the merge gate in the PR body**

The knowledge-doc re-upload must precede the model merge and must have a named
owner. The fact rebuilds on `0 0,10,13,15,17 * * *`, so the data change lands
within hours of merge; if the re-upload lags, every agent following the
published `notSet` protocol returns zero rows for i-Ready, DIBELS, STAR and both
states, silently.

- [ ] **Step 4: Record the saved-consumer audit as a prerequisite**

#4708 follow-up 3 (Superset charts, Tableau workbooks on the Cube SQL API,
direct API callers, ad-hoc BigQuery) cannot be enumerated from the repo and no
dbt exposure covers it. An announcement to that audience is the only available
mitigation and must happen before merge.

- [ ] **Step 5: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-assessment-strand-scores && \
  /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  docs/superpowers/plans/2026-08-28-strand-scores-rollback.md </dev/null
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-assessment-strand-scores add -u
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-assessment-strand-scores commit -m "docs: add the strand-scores rollback runbook and merge gate

Refs #4708"
```

---

## Known deferrals

Carried from the spec, recorded so a reviewer does not read them as omissions:

- The i-Ready ingestion stall (both regions last materialized 2026-07-18,
  pending the FY27 export renames in PR #4951). The i-Ready half ships against a
  source not currently ingesting current-year data.
- The 5,565 DIBELS subtest rows with a null `measure_standard_level_int`.
  Documented, not fixed.
- `int_assessments__resolved_section_enrollments` still filters DIBELS to
  Composite and i-Ready to `overall_scale_score is not null`, so the enrollment
  gate is asymmetric between anchor and breakdown rows.
- No uniqueness test on `int_iready__domain_unpivot` — pre-existing.
- The DIBELS subtest vocabulary is governed by a hand-maintained Google Sheet
  with no uniqueness test and no declared columns.
