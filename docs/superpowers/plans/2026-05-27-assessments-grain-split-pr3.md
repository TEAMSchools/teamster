# Assessments grain split — PR 3 implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Drop `canonical_title`, `canonical_administered_at`,
`canonical_grade_level_id`, `administered_date`, and `grade_level` from
`int_assessments__assessments_members`, and migrate consumers to join
`int_assessments__assessments_canonical` for those values.

**Architecture:** PR 1 added `int_assessments__assessments_canonical`
(canonical-grain). PR 2 renamed the member model. PR 3 finishes the grain split
by removing the denormalized `canonical_*` pass-through columns from `_members`;
consumers that need canonical attrs now traverse the FK chain via
`canonical_assessment_id` → `assessments_canonical`. Hash-stable for all 4 mart
surrogate keys that previously hashed `cast(canonical_administered_at as date)`
/ `administered_date` from members.

**Tech stack:** dbt 1.11 (BigQuery adapter), `dbt_utils` package,
sqlfluff/trunk-fmt.

**Spec:**
[`docs/superpowers/specs/2026-05-27-assessments-grain-split-design.md`](../specs/2026-05-27-assessments-grain-split-design.md)

**Tracking issue:** [#3800](https://github.com/TEAMSchools/teamster/issues/3800)
(closed by this PR).

**Worktree:** `.worktrees/cbini/refactor/claude-assessments-grain-split-pr3/`.
Every `git` command uses `git -C <worktree>`; every `dbt` command uses
`--project-dir <worktree>/src/dbt/kipptaf`.

---

## File Structure

| File                                                                                                  | Action | Responsibility                                                                                                                                                  |
| ----------------------------------------------------------------------------------------------------- | ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__assessments_members.sql`            | Modify | Drop 5 columns from canonical CTE + final SELECT.                                                                                                               |
| `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__assessments_members.yml` | Modify | Remove 5 column entries; update model description to drop "Computes the canonical-attribute window" prose.                                                      |
| `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__scaffold.sql`                       | Modify | Stop reading/projecting `canonical_title`, `canonical_administered_at`, `canonical_grade_level_id`. Keep `canonical_assessment_id` (still on members as FK).    |
| `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__scaffold.yml`            | Modify | Drop the 3 canonical\_\* column entries + source_column pointers.                                                                                               |
| `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__response_rollup.sql`                | Modify | Join `assessments_canonical` to recover the 3 attrs; replace `canonical_title as title` aliases with direct reads from canonical.                               |
| `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__response_rollup.yml`     | Modify | Update column descriptions: source*column pointers move from `int_assessments\_\_assessments_members.canonical*_`→`int_assessments\_\_assessments_canonical._`. |
| `src/dbt/kipptaf/models/marts/bridges/bridge_assessment_administration_members.sql`                   | Modify | Join `assessments_canonical`; replace `cast(canonical_administered_at as date)` with direct `administered_date` read.                                           |
| `src/dbt/kipptaf/models/marts/bridges/bridge_assessment_expectations_enrollment_scoped.sql`           | Modify | Same pattern.                                                                                                                                                   |
| `src/dbt/kipptaf/models/marts/bridges/bridge_assessment_expectations_student_scoped.sql`              | Modify | Same pattern.                                                                                                                                                   |
| `src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_enrollment_scoped.sql`                      | Modify | Join `assessments_canonical` instead of reading `a.administered_date` from members.                                                                             |
| `src/dbt/kipptaf/models/marts/dimensions/dim_assessments.sql`                                         | Modify | Join `assessments_canonical` for `grade_level` in `illuminate_assessments` CTE.                                                                                 |
| `src/dbt/kipptaf/models/extracts/google/appsheet/rpt_appsheet__assessments.sql`                       | Modify | Switch from `select * except (regions_assessed_array)` to explicit column list excluding the 5 dropped cols.                                                    |
| `src/dbt/kipptaf/models/extracts/google/appsheet/properties/rpt_appsheet__assessments.yml`            | Modify | Drop the 5 dropped col entries from the contract.                                                                                                               |

Untouched (do NOT modify):

- `int_assessments__assessments_canonical.sql` / its YAML — already produces the
  correct shape (PR 1).
- `int_assessments__performance_bands.sql` — uses `canonical_assessment_id`
  (stays) only, no canonical-attr reads.
- `rpt_tableau__ddi_audit.sql` / `rpt_tableau__assessment_tag_audit.sql` — their
  `grade_level` use is from staging or sourced from members raw `grade_level_id`
  (not from the dropped `grade_level` derivation).

---

## Migration order

Each consumer migration is independent — they all join `assessments_canonical`
directly. Order Task 1–6 (consumers) before Task 7 (drop columns) so dbt parse
stays green at every step. Compile after each task.

---

## Task 1: Migrate `int_assessments__scaffold`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__scaffold.sql`
- Modify:
  `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__scaffold.yml`

- [ ] **Step 1: Remove `canonical_title`, `canonical_administered_at`,
      `canonical_grade_level_id` reads from `assessment_region_scaffold` CTE**

In `int_assessments__scaffold.sql`, locate the `assessment_region_scaffold` CTE
(lines 2–28). Remove these 3 lines:

```sql
            a.canonical_title,
            a.canonical_administered_at,
            a.canonical_grade_level_id,
```

Keep `a.canonical_assessment_id,` (it remains on members).

- [ ] **Step 2: Remove the same 3 column references from `internal_assessments`
      CTE (both K-8 and HS branches)**

In `internal_assessments`, two SELECT branches (lines 47–91 K-8 and lines 96–135
HS). In each branch, remove:

```sql
            a.canonical_title,
            a.canonical_administered_at,
            a.canonical_grade_level_id,
```

Keep `a.canonical_assessment_id,`. (Two occurrences total — once per branch.)

- [ ] **Step 3: Remove the 3 outputs from the final SELECT and the two UNION ALL
      branches**

Three top-level SELECTs exist (the `from deduplicate as ia` at line 181
outputting `ia.canonical_*`, plus two UNION ALL branches at lines 190 and 250
outputting `a.canonical_*`).

In the first top-level SELECT (line 151), remove:

```sql
    ia.canonical_title,
    ia.canonical_administered_at,
    ia.canonical_grade_level_id,
```

In the second UNION ALL branch (line 190), remove:

```sql
    a.canonical_title,
    a.canonical_administered_at,
    a.canonical_grade_level_id,
```

In the third UNION ALL branch (line 250), remove:

```sql
    a.canonical_title,
    a.canonical_administered_at,
    a.canonical_grade_level_id,
```

Keep all three `canonical_assessment_id` lines.

- [ ] **Step 4: Update `int_assessments__scaffold.yml`**

Remove these column entries from the `columns:` list:

```yaml
      - name: canonical_title
        ...
      - name: canonical_administered_at
        ...
      - name: canonical_grade_level_id
        ...
```

If the model `description:` field references these columns, update it to
describe scaffold as forwarding `canonical_assessment_id` only (consumers join
`int_assessments__assessments_canonical` for canonical attrs).

- [ ] **Step 5: Verify dbt parse succeeds**

From `/workspaces/teamster`:

```bash
uv run dbt parse --project-dir .worktrees/cbini/refactor/claude-assessments-grain-split-pr3/src/dbt/kipptaf --no-partial-parse
```

Expected: parse succeeds. Some downstream consumers (response_rollup, etc.) may
now compile-fail at later tasks — that's fine, they'll be migrated next. Parse
only validates manifest correctness.

- [ ] **Step 6: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-assessments-grain-split-pr3 add -u \
  src/dbt/kipptaf/models/assessments/intermediate/int_assessments__scaffold.sql \
  src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__scaffold.yml
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-assessments-grain-split-pr3 commit -m "$(cat <<'EOF'
refactor(dbt): drop canonical_* passthrough from int_assessments__scaffold

Scaffold no longer denormalizes canonical_title/administered_at/grade_level_id
from members. Consumers join int_assessments__assessments_canonical via
canonical_assessment_id when canonical attrs are needed.

Refs #3800
EOF
)"
```

---

## Task 2: Migrate `int_assessments__response_rollup`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__response_rollup.sql`
- Modify:
  `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__response_rollup.yml`

- [ ] **Step 1: Add `assessments_canonical` join to `scaffold_responses` CTE**

In `int_assessments__response_rollup.sql`, the `scaffold_responses` CTE (lines
2–48) currently reads `s.canonical_title`, `s.canonical_administered_at`,
`s.canonical_grade_level_id` from scaffold. After Task 1, scaffold no longer
exposes these. Replace those 3 reads with joins to canonical.

Replace lines 22–25 (the 3 canonical\_\* reads from `s.`):

```sql
            s.canonical_assessment_id,
            s.canonical_title,
            s.canonical_administered_at,
            s.canonical_grade_level_id,
```

With (read only `canonical_assessment_id` from scaffold; canonical attrs come
from new join, aliased to preserve downstream usage):

```sql
            s.canonical_assessment_id,

            c.title as canonical_title,
            c.administered_date as canonical_administered_at,
            c.grade_level_id as canonical_grade_level_id,
```

Add the new join after the existing
`left join {{ ref("int_assessments__performance_bands") }} as pb ...` block
(i.e., as another `inner join` since every internal scaffold row has a
`canonical_assessment_id`):

```sql
        inner join
            {{ ref("int_assessments__assessments_canonical") }} as c
            on s.canonical_assessment_id = c.canonical_assessment_id
```

Important: keep the downstream column NAMES `canonical_title`,
`canonical_administered_at`, `canonical_grade_level_id` (aliased in this SELECT)
so the rest of the file — `tiebroken_attrs`, `internal_assessment_rollup`,
`response_union` — continues to reference them by those names. This minimizes
blast radius within the file.

Note: `canonical_administered_at` was renamed to `administered_date` on
canonical (PR 1). The alias `c.administered_date as canonical_administered_at`
preserves the column name response_rollup expects. The underlying value is
identical (both DATE, same canonical row).

- [ ] **Step 2: Verify dbt parse succeeds**

```bash
uv run dbt parse --project-dir .worktrees/cbini/refactor/claude-assessments-grain-split-pr3/src/dbt/kipptaf --no-partial-parse
```

Expected: parse succeeds.

- [ ] **Step 3: Compile response_rollup to confirm SQL resolves**

```bash
uv run dbt compile \
  --select int_assessments__response_rollup \
  --project-dir .worktrees/cbini/refactor/claude-assessments-grain-split-pr3/src/dbt/kipptaf
```

Read the compiled SQL at
`.worktrees/cbini/refactor/claude-assessments-grain-split-pr3/src/dbt/kipptaf/target/compiled/kipptaf/models/assessments/intermediate/int_assessments__response_rollup.sql`
and verify:

- The `scaffold_responses` CTE now `inner join`s the canonical view.
- `canonical_title`, `canonical_administered_at`, `canonical_grade_level_id`
  appear in the output of `scaffold_responses` (aliased from `c.*`).
- The remaining file (`tiebroken_attrs`, `internal_assessment_rollup`,
  `response_union`, final SELECT) is byte-identical to before.

- [ ] **Step 4: Update `int_assessments__response_rollup.yml`**

Find any column entries with
`source_column: int_assessments__assessments_members.canonical_*` and update
them to `source_column: int_assessments__assessments_canonical.*`. Specifically:

- `int_assessments__assessments_members.canonical_title` →
  `int_assessments__assessments_canonical.title`
- `int_assessments__assessments_members.canonical_administered_at` →
  `int_assessments__assessments_canonical.administered_date`
- `int_assessments__assessments_members.canonical_grade_level_id` →
  `int_assessments__assessments_canonical.grade_level_id`

Update prose descriptions that mention the old source if any.

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-assessments-grain-split-pr3 add -u \
  src/dbt/kipptaf/models/assessments/intermediate/int_assessments__response_rollup.sql \
  src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__response_rollup.yml
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-assessments-grain-split-pr3 commit -m "$(cat <<'EOF'
refactor(dbt): response_rollup joins canonical for canonical attrs

scaffold_responses now inner-joins int_assessments__assessments_canonical via
canonical_assessment_id and aliases c.title/administered_date/grade_level_id
back to canonical_title/canonical_administered_at/canonical_grade_level_id so
downstream CTEs (tiebroken_attrs, internal_assessment_rollup, response_union)
need no further changes.

Refs #3800
EOF
)"
```

---

## Task 3: Migrate `bridge_assessment_administration_members`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/bridges/bridge_assessment_administration_members.sql`

- [ ] **Step 1: Replace the file body**

Read current contents to confirm shape, then rewrite. Current file reads
`a.canonical_administered_at` from members and casts to date (a no-op since the
source is DATE). Post-PR-3, `canonical_administered_at` is dropped from members;
the value comes from `assessments_canonical.administered_date` (same DATE
column).

Replace the file with:

```sql
with
    members_unnested as (
        select
            a.assessment_id as member_assessment_id,
            a.canonical_assessment_id,
            a.module_code,
            a.academic_year,

            c.administered_date as canonical_administered_date,

            region,

            concat('kipp', lower(region)) as _dbt_source_project,
        from {{ ref("int_assessments__assessments_members") }} as a
        inner join
            {{ ref("int_assessments__assessments_canonical") }} as c
            on a.canonical_assessment_id = c.canonical_assessment_id
        cross join unnest(a.regions_assessed_array) as region
        where a.is_internal_assessment
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "'illuminate'",
                "module_code",
                "canonical_administered_date",
                "academic_year",
                "_dbt_source_project",
                "null",
                "canonical_assessment_id",
                "null",
            ]
        )
    }} as assessment_administration_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "'illuminate'",
                "module_code",
                "member_assessment_id",
                "null",
            ]
        )
    }} as assessment_key,
from members_unnested
```

Changes vs prior:

- Added
  `inner join int_assessments__assessments_canonical as c on a.canonical_assessment_id = c.canonical_assessment_id`
- Replaced
  `cast(a.canonical_administered_at as date) as canonical_administered_date`
  with `c.administered_date as canonical_administered_date`
- The hash input column name `canonical_administered_date` is preserved (no hash
  change)
- The VALUE is identical: `canonical_administered_at` and `c.administered_date`
  are byte-identical (both sourced from the same canonical pick, both DATE)

- [ ] **Step 2: Compile to verify**

```bash
uv run dbt compile \
  --select bridge_assessment_administration_members \
  --project-dir .worktrees/cbini/refactor/claude-assessments-grain-split-pr3/src/dbt/kipptaf
```

Expected: clean compile.

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-assessments-grain-split-pr3 add -u \
  src/dbt/kipptaf/models/marts/bridges/bridge_assessment_administration_members.sql
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-assessments-grain-split-pr3 commit -m "$(cat <<'EOF'
refactor(dbt): bridge_assessment_administration_members joins canonical

Replaces cast(canonical_administered_at as date) read-from-members with
direct administered_date read from int_assessments__assessments_canonical
joined on canonical_assessment_id. Hash inputs unchanged.

Refs #3800
EOF
)"
```

---

## Task 4: Migrate `bridge_assessment_expectations_enrollment_scoped`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/bridges/bridge_assessment_expectations_enrollment_scoped.sql`

- [ ] **Step 1: Add canonical join and update hash input**

In the `expectations` CTE (lines 7–32), the SELECT reads
`a.canonical_administered_at`. Replace that read with a value from the canonical
model.

Inside the SELECT (lines 8–18), change:

```sql
        select
            sc.cc_dcid,
            sc.cc_source_project,
            sc.assessment_id,
            sc.administered_at,
            sc._dbt_source_project,

            a.module_code,
            a.academic_year,
            a.canonical_assessment_id,
            a.canonical_administered_at,
```

To:

```sql
        select
            sc.cc_dcid,
            sc.cc_source_project,
            sc.assessment_id,
            sc.administered_at,
            sc._dbt_source_project,

            a.module_code,
            a.academic_year,
            a.canonical_assessment_id,

            c.administered_date as canonical_administered_at,
```

Add the canonical join after the existing
`inner join {{ ref("int_assessments__assessments_members") }} as a` block:

```sql
        inner join
            {{ ref("int_assessments__assessments_canonical") }} as c
            on a.canonical_assessment_id = c.canonical_assessment_id
```

(Place it before the `where` clause.)

The surrogate-key hash input `"cast(canonical_administered_at as date)"` stays —
the aliased `canonical_administered_at` is already DATE (from
`c.administered_date`), so the cast remains a no-op but preserves the hash-input
string verbatim for stability.

- [ ] **Step 2: Compile to verify**

```bash
uv run dbt compile \
  --select bridge_assessment_expectations_enrollment_scoped \
  --project-dir .worktrees/cbini/refactor/claude-assessments-grain-split-pr3/src/dbt/kipptaf
```

Expected: clean compile.

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-assessments-grain-split-pr3 add -u \
  src/dbt/kipptaf/models/marts/bridges/bridge_assessment_expectations_enrollment_scoped.sql
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-assessments-grain-split-pr3 commit -m "$(cat <<'EOF'
refactor(dbt): bridge_assessment_expectations_enrollment_scoped joins canonical

Replaces a.canonical_administered_at read from members with c.administered_date
from int_assessments__assessments_canonical joined on canonical_assessment_id.
Hash inputs unchanged.

Refs #3800
EOF
)"
```

---

## Task 5: Migrate `bridge_assessment_expectations_student_scoped`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/bridges/bridge_assessment_expectations_student_scoped.sql`

- [ ] **Step 1: Add canonical join and update hash input**

Same shape as Task 4. In the `expectations` CTE (lines 2–33), change the
`a.canonical_administered_at` read to an alias from the canonical model, and add
the canonical join.

Replace the SELECT contents (lines 3–14):

```sql
        select
            sc.powerschool_student_number,
            sc.assessment_id,
            sc.administered_at,
            sc.region,
            sc.powerschool_school_id,
            sc._dbt_source_project,

            a.module_code,
            a.academic_year,
            a.canonical_assessment_id,
            a.canonical_administered_at,
```

With:

```sql
        select
            sc.powerschool_student_number,
            sc.assessment_id,
            sc.administered_at,
            sc.region,
            sc.powerschool_school_id,
            sc._dbt_source_project,

            a.module_code,
            a.academic_year,
            a.canonical_assessment_id,

            c.administered_date as canonical_administered_at,
```

Add the canonical join after the existing
`inner join {{ ref("int_assessments__assessments_members") }} as a ...`:

```sql
        inner join
            {{ ref("int_assessments__assessments_canonical") }} as c
            on a.canonical_assessment_id = c.canonical_assessment_id
```

(Place before the `left join` to `stg_google_sheets__reporting__terms`.)

- [ ] **Step 2: Compile to verify**

```bash
uv run dbt compile \
  --select bridge_assessment_expectations_student_scoped \
  --project-dir .worktrees/cbini/refactor/claude-assessments-grain-split-pr3/src/dbt/kipptaf
```

Expected: clean compile.

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-assessments-grain-split-pr3 add -u \
  src/dbt/kipptaf/models/marts/bridges/bridge_assessment_expectations_student_scoped.sql
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-assessments-grain-split-pr3 commit -m "$(cat <<'EOF'
refactor(dbt): bridge_assessment_expectations_student_scoped joins canonical

Same pattern as enrollment-scoped sibling: replaces a.canonical_administered_at
read from members with c.administered_date from
int_assessments__assessments_canonical. Hash inputs unchanged.

Refs #3800
EOF
)"
```

---

## Task 6: Migrate `fct_assessment_scores_enrollment_scoped`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_enrollment_scoped.sql`

- [ ] **Step 1: Add canonical join, replace member's `administered_date` read**

In the `internal_assessments` CTE (lines 6–39), the SELECT reads
`a.academic_year`, `a.module_code`, `a.administered_date` from members.
Post-PR-3, `administered_date` is dropped from members but available on
canonical as the same DATE column.

In the SELECT, change the column block (lines 25–28):

```sql
            a.academic_year,
            a.module_code,
            a.administered_date,
```

To:

```sql
            a.academic_year,
            a.module_code,

            c.administered_date,
```

Add the canonical join after the existing
`left join {{ ref("int_assessments__assessments_members") }} as a ...` block.
Note this is a `left join` (members is optional for response_rollup rows), so
canonical must also be left-joined:

```sql
        left join
            {{ ref("int_assessments__assessments_canonical") }} as c
            on a.canonical_assessment_id = c.canonical_assessment_id
```

This requires `a.canonical_assessment_id` to exist — it stays on members
post-PR-3.

The hash input `"ia.administered_date"` is unchanged (still references the
same-named column in the outer SELECT).

- [ ] **Step 2: Compile to verify**

```bash
uv run dbt compile \
  --select fct_assessment_scores_enrollment_scoped \
  --project-dir .worktrees/cbini/refactor/claude-assessments-grain-split-pr3/src/dbt/kipptaf
```

Expected: clean compile.

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-assessments-grain-split-pr3 add -u \
  src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_enrollment_scoped.sql
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-assessments-grain-split-pr3 commit -m "$(cat <<'EOF'
refactor(dbt): fct_assessment_scores_enrollment_scoped joins canonical

Replaces a.administered_date read from members with c.administered_date from
int_assessments__assessments_canonical joined on canonical_assessment_id.
Hash inputs unchanged.

Refs #3800
EOF
)"
```

---

## Task 7: Migrate `dim_assessments`

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_assessments.sql`

- [ ] **Step 1: Add canonical join, replace `grade_level` read**

In `dim_assessments.sql`, the `illuminate_assessments` CTE (lines 6–26) reads
`grade_level` directly from members. Post-PR-3, that derivation moves to
canonical.

Change the `illuminate_assessments` CTE — replace the existing block:

```sql
    illuminate_assessments as (
        select
            assessment_id as source_assessment_id,
            title,
            subject_area,
            scope,
            module_code,
            module_type,
            grade_level,
            is_internal_assessment,

            'illuminate' as assessment_type,
            'enrollment' as assessment_scope,

            cast(null as string) as combined_academic_subject,
            cast(null as string) as aligned_academic_subject,
            cast(null as string) as credit_category,
            cast(null as string) as test_type,
        from {{ ref("int_assessments__assessments_members") }}
        where is_internal_assessment
    ),
```

With:

```sql
    illuminate_assessments as (
        select
            m.assessment_id as source_assessment_id,
            m.title,
            m.subject_area,
            m.scope,
            m.module_code,
            m.module_type,
            m.is_internal_assessment,

            c.grade_level,

            'illuminate' as assessment_type,
            'enrollment' as assessment_scope,

            cast(null as string) as combined_academic_subject,
            cast(null as string) as aligned_academic_subject,
            cast(null as string) as credit_category,
            cast(null as string) as test_type,
        from {{ ref("int_assessments__assessments_members") }} as m
        inner join
            {{ ref("int_assessments__assessments_canonical") }} as c
            on m.canonical_assessment_id = c.canonical_assessment_id
        where m.is_internal_assessment
    ),
```

This:

- Aliases members as `m` (was unaliased)
- Adds inner join to canonical
- Reads `m.*` for member-grain attrs (assessment_id, title, subject_area, scope,
  module_code, module_type, is_internal_assessment) — these stay on members
- Reads `c.grade_level` from canonical (this is the canonical-pick
  `grade_level_id - 1`)
- Note: `title` here is the **member's raw title**, not canonical —
  `dim_assessments` exposes member-grain rows, so each row's `title` is the
  member's own raw title (as before)

- [ ] **Step 2: Compile to verify**

```bash
uv run dbt compile \
  --select dim_assessments \
  --project-dir .worktrees/cbini/refactor/claude-assessments-grain-split-pr3/src/dbt/kipptaf
```

Expected: clean compile.

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-assessments-grain-split-pr3 add -u \
  src/dbt/kipptaf/models/marts/dimensions/dim_assessments.sql
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-assessments-grain-split-pr3 commit -m "$(cat <<'EOF'
refactor(dbt): dim_assessments joins canonical for grade_level

illuminate_assessments CTE now inner-joins int_assessments__assessments_canonical
on canonical_assessment_id and reads c.grade_level (canonical pick) instead of
the dropped grade_level pass-through column on members.

Refs #3800
EOF
)"
```

---

## Task 8: Migrate `rpt_appsheet__assessments`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/google/appsheet/rpt_appsheet__assessments.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/google/appsheet/properties/rpt_appsheet__assessments.yml`

Per user decision: drop the 5 canonical\_\* columns from the AppSheet contract.
AppSheet app must not depend on them; this dropping is acceptable.

- [ ] **Step 1: Rewrite the SQL as explicit column list**

Replace the entire body of `rpt_appsheet__assessments.sql` with:

```sql
select
    assessment_id,
    title,
    academic_year,
    academic_year_clean,
    scope,
    creator_first_name,
    creator_last_name,
    performance_band_set_id,
    assessment_type,
    tags,
    module_code,
    module_type,
    module_sequence,
    illuminate_grade_level_id,
    regions_assessed,
    regions_report_card,
    regions_progress_report,
    administered_at,
    subject_area,
    grade_level_id,
    is_internal_assessment,
    canonical_assessment_id,
from {{ ref("int_assessments__assessments_members") }}
```

Columns dropped vs prior `select *`: `regions_assessed_array` (already dropped
via `except`), `canonical_title`, `canonical_administered_at`,
`canonical_grade_level_id`, `administered_date`, `grade_level`.

- [ ] **Step 2: Update the YAML contract**

Remove these column entries from `rpt_appsheet__assessments.yml`:

```yaml
- name: canonical_title
  data_type: string
- name: canonical_administered_at
  data_type: date
- name: canonical_grade_level_id
  data_type: int64
- name: administered_date
  data_type: date
- name: grade_level
  data_type: int64
```

Read the full YAML first to locate the exact lines.

- [ ] **Step 3: Compile to verify**

```bash
uv run dbt compile \
  --select rpt_appsheet__assessments \
  --project-dir .worktrees/cbini/refactor/claude-assessments-grain-split-pr3/src/dbt/kipptaf
```

Expected: clean compile.

- [ ] **Step 4: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-assessments-grain-split-pr3 add -u \
  src/dbt/kipptaf/models/extracts/google/appsheet/rpt_appsheet__assessments.sql \
  src/dbt/kipptaf/models/extracts/google/appsheet/properties/rpt_appsheet__assessments.yml
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-assessments-grain-split-pr3 commit -m "$(cat <<'EOF'
refactor(dbt): rpt_appsheet__assessments explicit column list, drops canonical

Switches from select * except to explicit column enumeration. Drops the 5
columns being removed from int_assessments__assessments_members
(canonical_title, canonical_administered_at, canonical_grade_level_id,
administered_date, grade_level). AppSheet contract updated to match.

Refs #3800
EOF
)"
```

---

## Task 9: Drop columns from `int_assessments__assessments_members`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__assessments_members.sql`
- Modify:
  `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__assessments_members.yml`

- [ ] **Step 1: Remove the 3 `canonical_*` window outputs from the `canonical`
      CTE**

In `int_assessments__assessments_members.sql`, find the `canonical` CTE. It
currently computes `canonical_assessment_id`, `canonical_title`,
`canonical_administered_at`, `canonical_grade_level_id` via
`first_value(... order by assessment_id) over canonical_w`.

Keep `canonical_assessment_id` (still needed by all consumers as the FK).

Remove these three `if(... first_value ...)` blocks:

```sql
            if(
                is_internal_assessment, first_value(title) over canonical_w, title
            ) as canonical_title,

            if(
                is_internal_assessment,
                first_value(administered_at) over canonical_w,
                administered_at
            ) as canonical_administered_at,

            if(
                is_internal_assessment,
                first_value(grade_level_id) over canonical_w,
                grade_level_id
            ) as canonical_grade_level_id,
```

- [ ] **Step 2: Remove the 3 `canonical_*` + 2 derived columns from the final
      SELECT**

In the final SELECT (after the `canonical` CTE), remove these column outputs:

```sql
    canonical_title,
    canonical_administered_at,
    canonical_grade_level_id,
```

And these derived columns:

```sql
    cast(canonical_administered_at as date) as administered_date,

    canonical_grade_level_id - 1 as grade_level,
```

Keep `canonical_assessment_id`.

- [ ] **Step 3: Update `int_assessments__assessments_members.yml`**

Remove these column entries:

```yaml
      - name: canonical_title
        ...
      - name: canonical_administered_at
        ...
      - name: canonical_grade_level_id
        ...
      - name: administered_date
        ...
      - name: grade_level
        ...
```

Update the model `description:` to drop the prose about "Computes the
canonical-attribute window (`canonical_assessment_id`, `canonical_title`,
`canonical_administered_at`, `canonical_grade_level_id`)". Replace with a brief
note that `canonical_assessment_id` is computed via the window as the FK to
`int_assessments__assessments_canonical`.

- [ ] **Step 4: Compile full graph to verify no broken refs**

```bash
uv run dbt parse --project-dir .worktrees/cbini/refactor/claude-assessments-grain-split-pr3/src/dbt/kipptaf --no-partial-parse
```

Then:

```bash
uv run dbt compile \
  --select int_assessments__assessments_members+ \
  --project-dir .worktrees/cbini/refactor/claude-assessments-grain-split-pr3/src/dbt/kipptaf
```

Expected: clean parse + compile. Any "column X not found" error means a consumer
migration was missed in earlier tasks.

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-assessments-grain-split-pr3 add -u \
  src/dbt/kipptaf/models/assessments/intermediate/int_assessments__assessments_members.sql \
  src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__assessments_members.yml
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-assessments-grain-split-pr3 commit -m "$(cat <<'EOF'
refactor(dbt): drop canonical_* passthrough columns from members

Removes canonical_title, canonical_administered_at, canonical_grade_level_id,
administered_date, grade_level from int_assessments__assessments_members.
canonical_assessment_id stays as the FK to int_assessments__assessments_canonical.

Closes #3800.

Refs #3800
EOF
)"
```

---

## Task 10: Full build + hash stability verification

**Files:** none modified — just dbt runs and SQL audits.

- [ ] **Step 1: Build the full downstream lineage**

```bash
uv run dbt build \
  --select int_assessments__assessments_members+ \
  --project-dir .worktrees/cbini/refactor/claude-assessments-grain-split-pr3/src/dbt/kipptaf \
  --defer \
  --state target/prod
```

Expected: all models build and tests pass. The pre-existing warn-level
`relationships` tests (#4016) on bridges/fact may still warn — that's expected
and unrelated.

If a model fails with "column X not found", a consumer migration was missed.
Identify the file from the error and add a follow-up task.

If a `unique` or `relationships` test on a mart fails (NOT warn — fails), the
hash is unstable. Stop and investigate.

- [ ] **Step 2: Hash stability check — `dim_assessment_administrations`**

Use BigQuery MCP to compare the dim's keys between dev (PR branch) and prod. Dev
schema: `zz_cbini_kipptaf_marts` (per Task 5 of PR 1 plan pattern).

```sql
with dev as (
    select assessment_administration_key, source_assessment_id, _dbt_source_project,
    from `teamster-332318.zz_cbini_kipptaf_marts.dim_assessment_administrations`
    where source_assessment_id is not null
),
prod as (
    select assessment_administration_key, source_assessment_id, _dbt_source_project,
    from `teamster-332318.kipptaf_marts.dim_assessment_administrations`
    where source_assessment_id is not null
)
select
    countif(d.assessment_administration_key is null) as n_in_prod_not_dev,
    countif(p.assessment_administration_key is null) as n_in_dev_not_prod,
    countif(d.assessment_administration_key = p.assessment_administration_key) as n_keys_match,
    countif(d.assessment_administration_key != p.assessment_administration_key
            and d.assessment_administration_key is not null
            and p.assessment_administration_key is not null) as n_keys_differ,
from dev as d
full outer join prod as p
    on d.source_assessment_id = p.source_assessment_id
    and d._dbt_source_project = p._dbt_source_project
```

Expected: `n_keys_differ == 0`. (`n_in_prod_not_dev` and `n_in_dev_not_prod` may
be small due to upstream lag; that's OK.) PR 3 did not modify
`dim_assessment_administrations`, so its keys MUST be byte-identical to prod.

- [ ] **Step 3: Hash stability check —
      `bridge_assessment_administration_members`**

```sql
with dev as (
    select assessment_administration_key, assessment_key,
    from `teamster-332318.zz_cbini_kipptaf_marts.bridge_assessment_administration_members`
),
prod as (
    select assessment_administration_key, assessment_key,
    from `teamster-332318.kipptaf_marts.bridge_assessment_administration_members`
)
select
    countif(d.assessment_key is null) as n_in_prod_not_dev,
    countif(p.assessment_key is null) as n_in_dev_not_prod,
    countif(d.assessment_administration_key = p.assessment_administration_key
            and d.assessment_key = p.assessment_key) as n_pairs_match,
    countif(
        d.assessment_key = p.assessment_key
        and d.assessment_administration_key != p.assessment_administration_key
    ) as n_admin_keys_differ,
from dev as d
full outer join prod as p on d.assessment_key = p.assessment_key
```

Expected: `n_admin_keys_differ == 0`. The bridge's `assessment_key` is unchanged
(still hashed from `member_assessment_id` + `module_code`). The
`assessment_administration_key` is the value we restructured — must match prod
row-for-row.

- [ ] **Step 4: Spot-check fact + expectation bridges**

```sql
-- Spot-check fct_assessment_scores_enrollment_scoped on Illuminate-only rows
with dev as (
    select assessment_administration_key, assessment_score_key,
    from `teamster-332318.zz_cbini_kipptaf_marts.fct_assessment_scores_enrollment_scoped`
    where assessment_administration_key in (
        select assessment_administration_key
        from `teamster-332318.zz_cbini_kipptaf_marts.dim_assessment_administrations`
        where source_assessment_id is not null
    )
),
prod as (
    select assessment_administration_key, assessment_score_key,
    from `teamster-332318.kipptaf_marts.fct_assessment_scores_enrollment_scoped`
    where assessment_administration_key in (
        select assessment_administration_key
        from `teamster-332318.kipptaf_marts.dim_assessment_administrations`
        where source_assessment_id is not null
    )
)
select
    countif(
        d.assessment_administration_key != p.assessment_administration_key
    ) as n_admin_keys_differ,
    countif(d.assessment_score_key = p.assessment_score_key) as n_pairs_match,
from dev as d
inner join prod as p on d.assessment_score_key = p.assessment_score_key
```

Expected: `n_admin_keys_differ == 0`.

- [ ] **Step 5: Spot-check `dim_assessments.grade_level`**

```sql
with dev as (
    select assessment_key, grade_level_tested,
    from `teamster-332318.zz_cbini_kipptaf_marts.dim_assessments`
    where source_assessment_id is not null
),
prod as (
    select assessment_key, grade_level_tested,
    from `teamster-332318.kipptaf_marts.dim_assessments`
    where source_assessment_id is not null
)
select
    countif(d.grade_level_tested != p.grade_level_tested) as n_grade_level_differ,
    countif(d.grade_level_tested = p.grade_level_tested) as n_match,
    countif(d.grade_level_tested is null and p.grade_level_tested is not null) as n_dev_null_prod_not,
    countif(d.grade_level_tested is not null and p.grade_level_tested is null) as n_prod_null_dev_not,
from dev as d
inner join prod as p on d.assessment_key = p.assessment_key
```

Expected: `n_grade_level_differ == 0` and `n_dev_null_prod_not == 0` and
`n_prod_null_dev_not == 0`. `grade_level_tested` for Illuminate assessments is
now sourced from `c.grade_level` instead of `members.grade_level` — both derive
from `canonical_grade_level_id - 1`, so values match.

If any of the above checks show non-zero differences, stop and investigate the
relevant migration.

---

## Task 11: Lint, push, open PR

**Files:** all touched in PR 3.

- [ ] **Step 1: Run trunk check on touched files**

From inside the worktree:

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-assessments-grain-split-pr3 && \
  /workspaces/teamster/.trunk/tools/trunk check --force \
    src/dbt/kipptaf/models/assessments/intermediate/int_assessments__assessments_members.sql \
    src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__assessments_members.yml \
    src/dbt/kipptaf/models/assessments/intermediate/int_assessments__scaffold.sql \
    src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__scaffold.yml \
    src/dbt/kipptaf/models/assessments/intermediate/int_assessments__response_rollup.sql \
    src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__response_rollup.yml \
    src/dbt/kipptaf/models/marts/bridges/bridge_assessment_administration_members.sql \
    src/dbt/kipptaf/models/marts/bridges/bridge_assessment_expectations_enrollment_scoped.sql \
    src/dbt/kipptaf/models/marts/bridges/bridge_assessment_expectations_student_scoped.sql \
    src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_enrollment_scoped.sql \
    src/dbt/kipptaf/models/marts/dimensions/dim_assessments.sql \
    src/dbt/kipptaf/models/extracts/google/appsheet/rpt_appsheet__assessments.sql \
    src/dbt/kipptaf/models/extracts/google/appsheet/properties/rpt_appsheet__assessments.yml
```

Expected: no issues, or `Formatting applied` (then accept and re-stage if any
files changed).

If trunk reformats any files, run `git -C <worktree> add -u` and
`git -C <worktree> commit --amend --no-edit` ONLY for the most recent commit's
files; otherwise create a new `style(dbt): apply trunk fmt` commit.

- [ ] **Step 2: Push**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-assessments-grain-split-pr3 push
```

Expected: push succeeds. `trunk-check-pre-push` runs and must pass.

- [ ] **Step 3: Open PR 3**

Use `mcp__github__create_pull_request` with:

- `owner: TEAMSchools`
- `repo: teamster`
- `base: main`
- `head: cbini/refactor/claude-assessments-grain-split-pr3`
- `title: refactor(dbt): drop canonical_* passthrough from assessments_members (closes #3800)`
- `body:` populate per `.github/pull_request_template.md`, with `Closes #3800`
  (this PR finishes the three-PR sequence).

PR body must mention:

- Summary: PR 3 of three; closes #3800.
- Hash impact: hash-stable across all 4 affected mart surrogate keys; verified
  via Task 10 BQ queries.
- Migration list: per the file structure table at the top of this plan.
- AppSheet contract change: 5 columns removed from `rpt_appsheet__assessments`;
  AppSheet app config does not depend on them (decision made during PR 3
  design).

---

## Verification before claiming complete

Before marking PR 3 done:

- [ ] `uv run dbt build --select int_assessments__assessments_members+ --project-dir <worktree>/src/dbt/kipptaf --defer --state target/prod`
      exits 0 (or only with pre-existing warn-level orphans from #4016).
- [ ] All hash-stability checks in Task 10 show 0 differences.
- [ ] `trunk check --force` on all touched files exits 0.
- [ ] dbt Cloud CI on the PR is green (modulo the pre-existing warnings tracked
      in #4016 and #3819).
- [ ] PR body links to the design spec.
