# ES Writing Bridge Coverage — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the FK gap that excludes ES Writing assessment expectations from
both expectation bridges, while incidentally fixing a cross-district
student-number dedup collision risk and migrating
`student_section_enrollment_key` to a region-only hash.

**Architecture:** Three layered changes upstream → downstream: (1) promote
`_dbt_source_project = regexp_extract(_dbt_source_relation, r'(kipp\w+)_')` as a
materialized column on two base union models; (2) recompose
`student_section_enrollment_key` on both producer
(`dim_student_section_enrollments`) and consumer
(`bridge_assessment_expectations_enrollment_scoped`) to hash
`(cc_dcid, _dbt_source_project)`; (3) widen
`bridge_assessment_expectations_student_scoped` to admit ES Writing rows
alongside replacements.

**Tech Stack:** dbt 1.11 + BigQuery; `uv run` for all dbt invocations;
trunk-managed sqlfluff/yamllint at commit/push time.

**Spec:**
[docs/superpowers/specs/2026-05-12-es-writing-bridge-coverage-design.md](../specs/2026-05-12-es-writing-bridge-coverage-design.md)

**Worktree:**
`/workspaces/teamster/.worktrees/cbini/fix/claude-es-writing-bridge-coverage`.
All commands below assume this path. Use `git -C <worktree>` on every git call
and `--project-dir <worktree>/src/dbt/kipptaf` on every dbt call (per
`CLAUDE.md` worktree-commands rule).

**Build flag conventions** (per `src/dbt/CLAUDE.md`):

- Dev builds depending on Google Sheets externals require
  `--defer --state=src/dbt/kipptaf/target/prod/` (path is relative to
  `--project-dir`).
- If the prod manifest is stale, regenerate:
  `uv run dbt parse --target prod --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-es-writing-bridge-coverage/src/dbt/kipptaf --target-path target/prod`
- Before trusting any FK relationships warning on a dev build, clone the parent
  dim from prod:
  `uv run dbt clone --select <parent> --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-es-writing-bridge-coverage/src/dbt/kipptaf --state src/dbt/kipptaf/target/prod/`

---

## Task 1: Promote `_dbt_source_project` to `base_powerschool__course_enrollments`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/powerschool/base/base_powerschool__course_enrollments.sql`
- Check:
  `src/dbt/kipptaf/models/powerschool/base/properties/base_powerschool__course_enrollments.yml`
  (only edit if it currently lists all output columns — otherwise the new column
  is auto-discovered since the model is intermediate-tier, contract-disabled by
  default)

- [ ] **Step 1: Read the existing model and YAML**

Read both files in full. Confirm the model is `dbt_utils.union_relations` over 4
district sources and selects `ur.* except (...)` plus joined columns. Confirm
there is no existing `_dbt_source_project` column.

- [ ] **Step 2: Add `_dbt_source_project` to the SELECT**

In `base_powerschool__course_enrollments.sql`, add the column to the trailing
SELECT. Place it adjacent to the existing `region` derivation (line 54) for
readability — both come from the same regex source:

```sql
regexp_extract(ur._dbt_source_relation, r'(kipp\w+)_') as _dbt_source_project,

initcap(regexp_extract(ur._dbt_source_relation, r'kipp(\w+)_')) as region,
```

Note: the new regex uses `(kipp\w+)_` (capturing `kippnewark`), not `kipp(\w+)_`
(capturing `newark`). Keep both — `region` is the user-facing short form,
`_dbt_source_project` is the full code-location plumbing per #3142.

- [ ] **Step 3: If properties YAML enumerates all columns, add
      `_dbt_source_project`**

If `properties/base_powerschool__course_enrollments.yml` lists every column
under `columns:`, add an entry:

```yaml
- name: _dbt_source_project
  description: |
    Region prefix extracted from `_dbt_source_relation` via
    `regexp_extract(..., r'(kipp\w+)_')`. Used as a region discriminator
    in downstream surrogate keys, consistent across all upstream union
    tables. See #3142.
```

If the YAML only lists a few columns with tests (typical for intermediate base
models), no YAML change is needed — the column is contract-free.

- [ ] **Step 4: Build the model and verify**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-es-writing-bridge-coverage
uv run dbt build \
  --select base_powerschool__course_enrollments \
  --project-dir src/dbt/kipptaf \
  --defer --state=src/dbt/kipptaf/target/prod/
```

Expected: 1 model created, all tests pass. If the model has no per-column tests
on the new column, only the upstream uniqueness test runs — that's fine.

- [ ] **Step 5: Verify column is populated**

```bash
uv run dbt show \
  --inline "select _dbt_source_project, count(*) as n from {{ ref('base_powerschool__course_enrollments') }} group by 1" \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-es-writing-bridge-coverage/src/dbt/kipptaf
```

Expected: rows like `kippnewark | <n>`, `kippcamden | <n>`, etc. No NULL bucket.

- [ ] **Step 6: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-es-writing-bridge-coverage add -u
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-es-writing-bridge-coverage commit -m "feat(dbt): add _dbt_source_project to base_powerschool__course_enrollments

Scoped slice of #3142. Materializes the region-prefix discriminator so
downstream marts can hash on it directly instead of regex-extracting
from _dbt_source_relation at every join. Refs #3777 #3142."
```

---

## Task 2: Promote `_dbt_source_project` to `base_powerschool__student_enrollments`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/powerschool/base/base_powerschool__student_enrollments.sql`
- Check:
  `src/dbt/kipptaf/models/powerschool/base/properties/base_powerschool__student_enrollments.yml`

This model already has a `code_location` column (line 34) using the identical
`(kipp\w+)_` regex. The plan is to **add `_dbt_source_project` as a parallel
column with the same value** and leave `code_location` in place for existing
consumers. Collapsing the two is deferred to full #3142.

- [ ] **Step 1: Read both files**

Confirm `code_location` is present at the same regex spec we'd use. Confirm no
`_dbt_source_project` column yet.

- [ ] **Step 2: Add `_dbt_source_project` alongside `code_location`**

In `base_powerschool__student_enrollments.sql`, add immediately above the
existing `code_location` line:

```sql
regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as _dbt_source_project,
regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as code_location,
```

(Yes, the two expressions are identical. This is intentional —
`_dbt_source_project` is the #3142 canonical name; `code_location` stays for now
to avoid touching existing consumers. The duplicate disappears under full
#3142.)

- [ ] **Step 3: If properties YAML enumerates all columns, add
      `_dbt_source_project`**

Same logic as Task 1 Step 3. The description text should match Task 1's.

- [ ] **Step 4: Build the model and verify**

```bash
uv run dbt build \
  --select base_powerschool__student_enrollments \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-es-writing-bridge-coverage/src/dbt/kipptaf \
  --defer --state=src/dbt/kipptaf/target/prod/
```

Expected: 1 model created, all tests pass.

- [ ] **Step 5: Verify column populated and equal to `code_location`**

```bash
uv run dbt show \
  --inline "select countif(_dbt_source_project = code_location) as n_match, countif(_dbt_source_project != code_location) as n_mismatch, countif(_dbt_source_project is null) as n_null from {{ ref('base_powerschool__student_enrollments') }}" \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-es-writing-bridge-coverage/src/dbt/kipptaf
```

Expected: `n_match = total`, `n_mismatch = 0`, `n_null = 0`.

- [ ] **Step 6: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-es-writing-bridge-coverage add -u
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-es-writing-bridge-coverage commit -m "feat(dbt): add _dbt_source_project to base_powerschool__student_enrollments

Parallel to the existing code_location column for now; full #3142 will
collapse both names into one. Refs #3777 #3142."
```

---

## Task 3: Use `_dbt_source_project` in `int_assessments__course_enrollments` and close the dedup collision

**Files:**

- Modify:
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__course_enrollments.sql`
- Check:
  `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__course_enrollments.yml`

- [ ] **Step 1: Read the model and YAML**

Confirm two `union all` branches: K-12 (from
`base_powerschool__course_enrollments`, lines ~4-36) and ES Writing (from
`base_powerschool__student_enrollments`, lines ~40-64). Confirm the trailing
`dbt_utils.deduplicate` (lines ~67-72) partitions by
`(powerschool_student_number, illuminate_academic_year, illuminate_subject_area, cc_dateenrolled)`.

- [ ] **Step 2: Add `_dbt_source_project` to both branches**

K-12 branch — add adjacent to the existing `ce._dbt_source_relation` (line 14):

```sql
ce.cc_dcid,
ce._dbt_source_relation,
ce._dbt_source_project,
```

ES Writing branch — replace line 55
(`cast(null as string) as _dbt_source_relation,`) with two lines:

```sql
cast(null as int64) as cc_dcid,
cast(null as string) as _dbt_source_relation,
co._dbt_source_project,
```

Leave `cc_dcid` NULL (no PS course-enrollment row exists). Leave
`_dbt_source_relation` NULL (the value would be
`..._base_powerschool__student_enrollments`, which is asymmetric vs K-12's
`..._base_powerschool__course_enrollments`; downstream consumers that want a
region discriminator should use `_dbt_source_project`).

Verify ST06 column-order rule (plain refs grouped, then literals, then casts) —
keep `co._dbt_source_project` in the plain-refs cluster, not after the
`cast(null...)` lines. Adjust ordering if sqlfluff would complain.

- [ ] **Step 3: Add `_dbt_source_project` to the trailing dedup `partition_by`**

Change:

```sql
{{
    dbt_utils.deduplicate(
        relation="enrollments_union",
        partition_by="powerschool_student_number, illuminate_academic_year, illuminate_subject_area, cc_dateenrolled",
        order_by="cc_dateleft desc",
    )
}}
```

to:

```sql
{{
    dbt_utils.deduplicate(
        relation="enrollments_union",
        partition_by="_dbt_source_project, powerschool_student_number, illuminate_academic_year, illuminate_subject_area, cc_dateenrolled",
        order_by="cc_dateleft desc",
    )
}}
```

- [ ] **Step 4: Update the properties YAML if it enumerates columns**

If the YAML has a full `columns:` list, add `_dbt_source_project` with the
description from Task 1 Step 3. If it only carries uniqueness / data tests, no
change.

- [ ] **Step 5: Build the model + downstream uniqueness check**

```bash
uv run dbt build \
  --select int_assessments__course_enrollments \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-es-writing-bridge-coverage/src/dbt/kipptaf \
  --defer --state=src/dbt/kipptaf/target/prod/
```

Expected: model builds, uniqueness test passes. Row count should be **≥** prior
baseline (collapsed cross-district duplicates are now preserved).

- [ ] **Step 6: Spot-check row count delta**

```bash
uv run dbt show \
  --inline "select count(*) as n from {{ ref('int_assessments__course_enrollments') }}" \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-es-writing-bridge-coverage/src/dbt/kipptaf
```

Compare against prod for the same model (BigQuery MCP, table
`teamster-332318.kipptaf_assessments.int_assessments__course_enrollments`). Net
delta should be small (most cross-district student_number collisions don't
actually overlap on AY+subject+date), or zero. A negative delta means a
regression — stop and investigate.

- [ ] **Step 7: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-es-writing-bridge-coverage add -u
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-es-writing-bridge-coverage commit -m "fix(dbt): plumb _dbt_source_project through int_assessments__course_enrollments

Carries the region discriminator on both K-12 and ES Writing branches
and includes it in the trailing dedup partition. Closes a silent
cross-district student-number collision risk in the ES Writing branch
where the prior all-NULL plumbing left the partition blind. Refs #3777."
```

---

## Task 4: Rename `cc_source_relation` → `cc_source_project` in `int_assessments__scaffold`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__scaffold.sql`
- Modify:
  `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__scaffold.yml`

- [ ] **Step 1: Read both files**

Confirm `cc_source_relation` appears at lines 74 (K-8 internal branch), 124 (HS
branch), 168 (final SELECT pass-through), 213 (replacement branch hardcodes
NULL), 271 (external branch hardcodes NULL). Confirm the YAML has a
`cc_source_relation` column entry with
`source_column: int_assessments__course_enrollments._dbt_source_relation`.

- [ ] **Step 2: Update SQL — replace `_dbt_source_relation` reads with
      `_dbt_source_project` reads, and rename the alias to `cc_source_project`**

K-8 branch (line 74):

```sql
ce._dbt_source_project as cc_source_project,
```

HS branch (line 124):

```sql
ce._dbt_source_project as cc_source_project,
```

Final SELECT (line 168) — rename the pass-through:

```sql
ia.cc_source_project,
```

Replacement branch (line 213) and external branch (line 271):

```sql
cast(null as string) as cc_source_project,
```

- [ ] **Step 3: Update properties YAML**

Rename the column entry from `cc_source_relation` to `cc_source_project`. Update
`config.meta.source_column` to
`int_assessments__course_enrollments._dbt_source_project`. Rewrite the
description to describe the new semantics (region prefix, not the full
source-relation).

- [ ] **Step 4: Build the model**

```bash
uv run dbt build \
  --select int_assessments__scaffold \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-es-writing-bridge-coverage/src/dbt/kipptaf \
  --defer --state=src/dbt/kipptaf/target/prod/
```

Expected: parses, builds, tests pass.

- [ ] **Step 5: Verify column rename**

```bash
uv run dbt show \
  --inline "select cc_source_project, count(*) as n from {{ ref('int_assessments__scaffold') }} where is_internal_assessment group by 1 order by 2 desc" \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-es-writing-bridge-coverage/src/dbt/kipptaf
```

Expected: buckets like `kippnewark`, `kippcamden`, `kippmiami`, `kipppaterson`,
plus a NULL bucket for replacement-branch rows.

- [ ] **Step 6: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-es-writing-bridge-coverage add -u
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-es-writing-bridge-coverage commit -m "refactor(dbt): rename int_assessments__scaffold.cc_source_relation to cc_source_project

Carries the region prefix instead of the full _dbt_source_relation,
preparing the downstream hash swap on student_section_enrollment_key.
Refs #3777 #3820."
```

---

## Task 5: Swap `student_section_enrollment_key` hash on both producer and consumer (atomic)

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/dim_student_section_enrollments.sql`
- Modify:
  `src/dbt/kipptaf/models/marts/bridges/bridge_assessment_expectations_enrollment_scoped.sql`
- Check:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_student_section_enrollments.yml`
  and
  `src/dbt/kipptaf/models/marts/bridges/properties/bridge_assessment_expectations_enrollment_scoped.yml`

**Atomicity:** Both files commit together. Between the two changes the FK
relationships test would fail; do not commit half the change.

- [ ] **Step 1: Read both SQL files and any properties YAMLs**

Confirm:

- `dim_student_section_enrollments.sql:74` hashes
  `student_section_enrollment_key` from `(cc_dcid, _dbt_source_relation)`.
- `bridge_assessment_expectations_enrollment_scoped.sql:42-43` hashes from
  `(cc_dcid, cc_source_relation)`.

- [ ] **Step 2: Swap hash composition on `dim_student_section_enrollments`**

Replace lines 73-75:

```sql
{{ dbt_utils.generate_surrogate_key(["cc_dcid", "_dbt_source_project"]) }}
    as student_section_enrollment_key,
```

The CTE `course_enrollments_joined` already selects `cc._dbt_source_relation`
(line 18); ALSO select `cc._dbt_source_project` there so it is available at the
outer SELECT:

```sql
cc.cc_dcid,
cc.sections_dcid,
cc._dbt_source_project,
cc.cc_academic_year,
```

(`_dbt_source_relation` stays on the CTE because it's still used by the
`replace()` workaround on `course_section_key` at lines 86-90 — that workaround
is #3820's broader sweep and stays for now.)

Leave the `// TODO` comment block above `course_section_key` (lines 77-81) but
add a sentence noting `student_section_enrollment_key` has been migrated to
`_dbt_source_project` and the remaining keys await full #3820.

- [ ] **Step 3: Swap hash composition on
      `bridge_assessment_expectations_enrollment_scoped`**

The bridge currently selects `sc.cc_source_relation` from
`int_assessments__scaffold`. Task 4 already renamed that to `cc_source_project`.
Update the bridge:

- Line 10: `sc.cc_source_project,` (replacing `sc.cc_source_relation,`)
- Line 25-27 comment: rewrite to reference the student-scoped bridge as the home
  for NULL-cc_dcid rows:

  ```sql
  -- ES Writing and other NULL-cc_dcid rows are excluded here because
  -- cc_dcid + _dbt_source_project form the student_section_enrollment_key
  -- and NULL cc_dcid would collide on the placeholder hash. Those rows
  -- live in bridge_assessment_expectations_student_scoped instead.
  ```

- Line 31-32: rename the filter from `cc_source_relation is not null` to
  `cc_source_project is not null` (combined with `cc_dcid is not null`, ES
  Writing rows still excluded).
- Line 38: hash input list becomes
  `["cc_dcid", "_dbt_source_project", "assessment_id", "administered_at"]` for
  `assessment_expectation_key`. **Critical:** this changes
  `assessment_expectation_key` hash composition too. Verify the bridge's PK
  uniqueness test still passes; downstream consumers of
  `assessment_expectation_key` need the same migration if any — grep for it (see
  Step 4 below).
- Line 42: hash input list becomes `["cc_dcid", "_dbt_source_project"]` for
  `student_section_enrollment_key`.

The new name is `_dbt_source_project` (not `cc_source_project`) in the hash
input because that matches the producer dim's column name. The bridge's local
alias `cc_source_project` becomes a pass-through; consider dropping the `cc_`
prefix and using `_dbt_source_project` directly throughout the bridge for
symmetry — verify column-order rules first.

- [ ] **Step 4: Check for downstream consumers of `assessment_expectation_key`**

```bash
grep -rn "assessment_expectation_key" /workspaces/teamster/.worktrees/cbini/fix/claude-es-writing-bridge-coverage/src/dbt/kipptaf/models
```

If anything OTHER than the two bridges references this key, the migration scope
expands — stop and flag to user. Both bridges produce the key as a PK; nothing
should FK to it. Expected: only model-internal references.

- [ ] **Step 5: Update properties YAMLs**

If either bridge or dim YAML has a `description` mentioning the hash inputs,
update to reference `_dbt_source_project`. No column-name changes in the YAMLs
for these models (the columns are surrogate keys, opaque to consumers).

- [ ] **Step 6: Build both models and run their tests together**

```bash
uv run dbt build \
  --select dim_student_section_enrollments bridge_assessment_expectations_enrollment_scoped \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-es-writing-bridge-coverage/src/dbt/kipptaf \
  --defer --state=src/dbt/kipptaf/target/prod/
```

Expected: both build, PK uniqueness passes on both, FK relationships test
`bridge_assessment_expectations_enrollment_scoped.student_section_enrollment_key → dim_student_section_enrollments.student_section_enrollment_key`
passes (both sides now hash identically on `_dbt_source_project`).

If the relationships test reports orphans, the most likely cause is the
`replace()` workaround on `course_section_key` still using the old composition —
verify the producer/consumer **on the `_section_enrollment_key` only**, not
`course_section_key`.

- [ ] **Step 7: Spot-check via BigQuery MCP that row counts are unchanged on the
      dim**

```sql
select count(*) as n_pre
from `teamster-332318.kipptaf_marts.dim_student_section_enrollments`
```

vs. the PR-branch schema (`dbt_cloud_pr_<ci_id>_<pr_num>_marts` once CI runs, or
the dev schema for local).

Expected: identical row counts. Hash change is a value change, not a row change.

- [ ] **Step 8: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-es-writing-bridge-coverage add -u
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-es-writing-bridge-coverage commit -m "refactor(dbt): migrate student_section_enrollment_key to region-prefix hash

Both producer (dim_student_section_enrollments) and consumer
(bridge_assessment_expectations_enrollment_scoped) now hash
(cc_dcid, _dbt_source_project) instead of (cc_dcid, _dbt_source_relation).
First wave of #3820; other surrogate keys in dim_courses,
dim_course_sections, and the course_section_key replace() workaround
stay deferred. Refs #3777 #3820."
```

---

## Task 6: Widen `bridge_assessment_expectations_student_scoped` to admit ES Writing

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/bridges/bridge_assessment_expectations_student_scoped.sql`
- Check:
  `src/dbt/kipptaf/models/marts/bridges/properties/bridge_assessment_expectations_student_scoped.yml`

- [ ] **Step 1: Read the model and YAML**

Confirm the current `WHERE` (line 31) is
`sc.is_replacement and sc.powerschool_student_number is not null` with no
`is_internal_assessment` filter.

- [ ] **Step 2: Widen the WHERE clause**

Replace line 31:

```sql
where
    sc.is_internal_assessment
    and (sc.is_replacement or sc.cc_dcid is null)
    and sc.powerschool_student_number is not null
```

- [ ] **Step 3: Update model description in properties YAML**

Set the model description to:

```yaml
description: |
  Bridges internal assessment expectations that cannot be attributed to
  a student section enrollment to their student and assessment
  administration. Covers two classes: replacement assessments (which
  have no enrollment by definition) and ES Writing in grades K-4
  Newark/Camden (where no PowerSchool course-enrollment row exists for
  the writing program). Rows whose expectations can be attributed to a
  section enrollment live in `bridge_assessment_expectations_enrollment_scoped`.
```

Also update `bridge_assessment_expectations_enrollment_scoped`'s YAML
description to mirror — state it only covers rows with a resolvable section
enrollment; ES Writing and replacements live in the student-scoped bridge.

- [ ] **Step 4: Build and test**

```bash
uv run dbt build \
  --select bridge_assessment_expectations_student_scoped bridge_assessment_expectations_enrollment_scoped \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-es-writing-bridge-coverage/src/dbt/kipptaf \
  --defer --state=src/dbt/kipptaf/target/prod/
```

Expected: both build; uniqueness tests pass; FK tests pass with expanded row set
on student-scoped bridge.

- [ ] **Step 5: Verify row-count delta and ES Writing coverage**

```bash
uv run dbt show --inline "
  select
      (select count(*) from {{ ref('bridge_assessment_expectations_student_scoped') }}) as n_student_scoped,
      (
          select count(*)
          from {{ ref('bridge_assessment_expectations_student_scoped') }} b
          inner join {{ ref('int_assessments__scaffold') }} sc using (assessment_id)
          where sc.is_internal_assessment and not sc.is_replacement and sc.cc_dcid is null
      ) as n_es_writing_in_bridge
" --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-es-writing-bridge-coverage/src/dbt/kipptaf
```

Expected: `n_student_scoped` ≈ 116,776; `n_es_writing_in_bridge` ≈ 116,776 (≈
the previously-excluded class). Compare against the prod baseline (1,856 rows) —
net delta should be ≈ +114,920.

- [ ] **Step 6: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-es-writing-bridge-coverage add -u
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-es-writing-bridge-coverage commit -m "fix(dbt): include ES Writing in bridge_assessment_expectations_student_scoped

Widens the bridge filter from is_replacement-only to admit any
internal-assessment row that the enrollment-scoped bridge cannot
represent (replacements OR ES Writing). Closes #3777."
```

---

## Task 7: Pre-merge verification and PR-branch CI confirmation

**Files:** no SQL/YAML changes — verification only.

- [ ] **Step 1: Build the full subgraph end-to-end**

```bash
uv run dbt build \
  --select +bridge_assessment_expectations_student_scoped +bridge_assessment_expectations_enrollment_scoped +dim_student_section_enrollments \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-es-writing-bridge-coverage/src/dbt/kipptaf \
  --defer --state=src/dbt/kipptaf/target/prod/
```

Expected: all upstream + the three targets build, all tests pass.

- [ ] **Step 2: Diamond-path and R1-R10 scan**

Re-read each changed mart file. For each, confirm:

- No new diamond paths introduced (per `marts/CLAUDE.md` "Strict-chain
  traversal").
- No new mart columns violate R1-R10 (`_dbt_source_project` and
  `cc_source_project` are plumbing per R8 — stays in intermediate, not surfaced
  in any mart SELECT).

- [ ] **Step 3: Push the branch and wait for dbt Cloud CI**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-es-writing-bridge-coverage push
```

dbt Cloud CI runs `dbt build --select state:modified+ --full-refresh` on target
staging.

- [ ] **Step 4: Pull marts warnings from the CI run**

After CI completes, use `mcp__dbt__get_job_run_error` with `warning_only=true`.
Confirm:

- The previously-WARNing
  `bridge_assessment_expectations_enrollment_scoped.assessment_administration_key → dim_assessment_administrations`
  test (or whichever was warning, per the issue body) is unchanged or improved.
- No new bridge / dim / scaffold warnings surfaced.
- No new orphans on `student_section_enrollment_key` FK.

- [ ] **Step 5: Project board scan**

Visit https://github.com/orgs/TEAMSchools/projects/4/views/1. For each open
issue, check the title against changed models; close any incidentally resolved
(none expected besides #3777, but #3142 and #3820 deserve a comment noting
wave-1 progress).

- [ ] **Step 6: Run BigQuery sizing query against the PR-branch schema**

Once CI has materialized the PR-branch schema
(`dbt_cloud_pr_<ci_id>_<pr_num>_marts`), run via BigQuery MCP:

```sql
select count(*) as n_student_scoped
from `teamster-332318.dbt_cloud_pr_<ci_id>_<pr_num>_marts.bridge_assessment_expectations_student_scoped`
```

Expected: ≈ 116,776 (was 1,856 in prod).

- [ ] **Step 7: Open the PR**

Use `.github/pull_request_template.md` as the body. Title:
`fix(dbt): include ES Writing in student-scoped expectations bridge (#3777)`.
Body references #3777 (closes), #3142 (partial), #3820 (partial).

```bash
gh pr create --title "fix(dbt): include ES Writing in student-scoped expectations bridge" --body "$(cat <<'EOF'
## Summary
- Adds `_dbt_source_project` materialized column to two base PowerSchool union models (slice of #3142).
- Migrates `student_section_enrollment_key` on both producer and consumer to hash `(cc_dcid, _dbt_source_project)` (slice of #3820).
- Widens `bridge_assessment_expectations_student_scoped` filter to admit ES Writing rows alongside replacements.

## Test plan
- [ ] dbt Cloud CI passes on the full subgraph.
- [ ] `bridge_assessment_expectations_student_scoped` row count ≈ 116,776 (was 1,856).
- [ ] `dim_student_section_enrollments` row count unchanged; PK uniqueness passes.
- [ ] `bridge_assessment_expectations_enrollment_scoped → dim_student_section_enrollments` relationships test orphan count unchanged.
- [ ] No new bridge / dim / scaffold warnings on the latest CI run.

Closes #3777. Partial progress on #3142 and #3820.
EOF
)"
```

---

## Spec Coverage Map

| Spec section                                                                     | Plan task                  |
| -------------------------------------------------------------------------------- | -------------------------- |
| Promote `_dbt_source_project` on `base_powerschool__course_enrollments`          | Task 1                     |
| Promote `_dbt_source_project` on `base_powerschool__student_enrollments`         | Task 2                     |
| Update `int_assessments__course_enrollments` (both branches + dedup)             | Task 3                     |
| Rename `cc_source_relation` → `cc_source_project` in `int_assessments__scaffold` | Task 4                     |
| Hash swap on `dim_student_section_enrollments`                                   | Task 5                     |
| Hash swap + filter rename on `bridge_assessment_expectations_enrollment_scoped`  | Task 5                     |
| Widen `bridge_assessment_expectations_student_scoped` WHERE clause               | Task 6                     |
| YAML description updates on both bridges                                         | Task 6 (description block) |
| Pre-merge checklist (warnings sweep, project board, sizing)                      | Task 7                     |

## Notes for the engineer

- **Trunk:** Don't run `trunk fmt` or `trunk check` manually — pre-commit hooks
  format SQL/YAML at commit time. If a hook reports issues at commit time, fix
  and re-commit (do not `--no-verify`).
- **Stale dev tables:** If a relationships test reports orphans on
  `student_section_enrollment_key` after Task 5, the parent dim may have
  stale-defer data. `dbt clone --select dim_student_section_enrollments` from
  staging before re-running.
- **No production consumers:** per `marts/CLAUDE.md` "Spec authoring context",
  hash churn is free — no compat shims needed.
- **Properties YAML reads:** before modifying any model, read its properties
  YAML in full (per `src/dbt/CLAUDE.md` YAML conventions). Copy-paste rot is the
  most common gotcha.
- **Worktree commands:** always `git -C <worktree>` and
  `--project-dir <worktree>/src/dbt/kipptaf`. Bare `git` from the main repo
  silently commits to `main`.
