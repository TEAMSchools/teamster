# Assessments grain split — PR 1 implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `int_assessments__assessments_canonical` (canonical-grain) and
migrate `dim_assessment_administrations.illuminate_administrations` to read from
it, removing the `SELECT DISTINCT` workaround.

**Architecture:** New intermediate model groups `int_assessments__assessments`
by `canonical_assessment_id`, picking attrs via
`dbt_utils.deduplicate(partition_by="canonical_assessment_id", order_by="assessment_id")`
and unioning member regions via `array_agg(distinct region)`. Dim's
`illuminate_administrations` CTE becomes a plain SELECT over the new model with
`cross join unnest(regions_array)`. Existing `int_assessments__assessments` is
unchanged; consumers untouched.

**Tech stack:** dbt 1.11 (BigQuery adapter), `dbt_utils` package,
sqlfluff/trunk-fmt.

**Spec:**
[docs/superpowers/specs/2026-05-27-assessments-grain-split-design.md](../specs/2026-05-27-assessments-grain-split-design.md)

**Tracking issue:** [#3800](https://github.com/TEAMSchools/teamster/issues/3800)

**Worktree:** `.worktrees/cbini/refactor/claude-assessments-grain-split/`. Every
`git` command uses `git -C <worktree>`; every `dbt` command uses
`--project-dir <worktree>/src/dbt/kipptaf`.

---

## File Structure

| File                                                                                                    | Action | Responsibility                                                                                                                                                     |
| ------------------------------------------------------------------------------------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__assessments_canonical.sql`            | Create | Canonical-grain model: one row per `canonical_assessment_id`, joining canonical-pick attrs to union-of-member-regions array.                                       |
| `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__assessments_canonical.yml` | Create | Contract types, column descriptions, uniqueness test on `canonical_assessment_id`, `relationships` test to `int_assessments__assessments.canonical_assessment_id`. |
| `src/dbt/kipptaf/models/marts/dimensions/dim_assessment_administrations.sql`                            | Modify | Drop `canonical_regions` CTE. Rewrite `illuminate_administrations` as plain SELECT from canonical model. Remove `TODO(#3800)` comment.                             |

`int_assessments__assessments` is untouched in PR 1.

---

## Task 1: Create the canonical model SQL

**Files:**

- Create:
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__assessments_canonical.sql`

- [ ] **Step 1: Create the SQL file**

Create
`.worktrees/cbini/refactor/claude-assessments-grain-split/src/dbt/kipptaf/models/assessments/intermediate/int_assessments__assessments_canonical.sql`
with this content:

```sql
with
    canonical_picks as (
        {{
            dbt_utils.deduplicate(
                relation=ref("int_assessments__assessments"),
                partition_by="canonical_assessment_id",
                order_by="assessment_id",
            )
        }}
    ),

    canonical_regions as (
        select
            canonical_assessment_id,
            array_agg(distinct region) as regions_array,
        from {{ ref("int_assessments__assessments") }}, unnest(regions_assessed_array) as region
        where is_internal_assessment
        group by canonical_assessment_id
    )

select
    p.canonical_assessment_id,
    p.canonical_title as title,
    p.canonical_administered_at as administered_at,
    p.subject_area,
    p.scope,
    p.module_code,
    p.academic_year,
    p.academic_year_clean,
    p.canonical_grade_level_id as grade_level_id,

    r.regions_array,

    cast(p.canonical_administered_at as date) as administered_date,

    p.canonical_grade_level_id - 1 as grade_level,
from canonical_picks as p
inner join canonical_regions as r on p.canonical_assessment_id = r.canonical_assessment_id
where p.is_internal_assessment
```

**Notes for the implementing engineer:**

- The existing `int_assessments__assessments` already exposes `canonical_title`,
  `canonical_administered_at`, `canonical_grade_level_id` as pass-through
  columns (computed via
  `first_value(... order by assessment_id) over canonical_w`). The
  `dbt_utils.deduplicate(partition_by="canonical_assessment_id", order_by="assessment_id")`
  macro picks the same row (lowest `assessment_id` in each group) as the
  existing window's `first_value`, so the canonical attr values match by
  construction.
- We read `canonical_*` columns from the deduplicated picks and rename them to
  drop the `canonical_` prefix (since the model name signals grain).
- `is_internal_assessment` filter is applied in two places defensively: (a)
  inside `canonical_regions` to avoid blowing the array with non-internal
  regions, (b) in the final WHERE to filter any non-internal rows that slipped
  through `canonical_picks`. The INNER JOIN to `canonical_regions` would also
  implicitly filter, but the explicit WHERE is clearer.
- SQL column ordering follows sqlfluff ST06: plain refs grouped by source CTE (p
  then r), separated by blank lines, then nested/computed expressions.

- [ ] **Step 2: Verify the file parses**

Run from `/workspaces/teamster`:

```bash
uv run dbt parse --project-dir .worktrees/cbini/refactor/claude-assessments-grain-split/src/dbt/kipptaf --no-partial-parse
```

Expected: parse succeeds. New model `int_assessments__assessments_canonical`
appears in the manifest.

If parse fails on a missing yml (the contract isn't strictly required for
intermediates but other intermediates in this dir have YAMLs), proceed to Task 2
— the yml is added next. The parse error message should distinguish syntax
errors from missing-yml warnings.

---

## Task 2: Create the canonical model properties YAML

**Files:**

- Create:
  `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__assessments_canonical.yml`

- [ ] **Step 1: Create the properties YAML**

Create
`.worktrees/cbini/refactor/claude-assessments-grain-split/src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__assessments_canonical.yml`
with this content:

```yaml
models:
  - name: int_assessments__assessments_canonical
    description: >-
      Canonical-grain projection of `int_assessments__assessments`. One row per
      `canonical_assessment_id` — the logical assessment that may span multiple
      regional members (e.g., the four regional copies of the same Q2 ELA module
      collapse to one canonical row). Canonical attrs (`title`,
      `administered_at`, `grade_level_id`) are picked from the member with the
      lowest `assessment_id` in the canonical group via
      `dbt_utils.deduplicate(partition_by="canonical_assessment_id",
      order_by="assessment_id")`, matching the `first_value(... order by
      assessment_id) over canonical_w` window in the upstream model.
      `regions_array` is the union of `regions_assessed_array` across all
      internal members of the group. Internal assessments only
      (`is_internal_assessment` filter applied upstream).
    columns:
      - name: canonical_assessment_id
        data_tests:
          - unique
          - not_null
          - relationships:
              arguments:
                to: ref('int_assessments__assessments')
                field: canonical_assessment_id
        data_type: int64
        description: >-
          Primary key. The lowest `assessment_id` within the canonical partition
          `(academic_year, scope, subject_area, module_code, grade_level_id)`.
          Members of `int_assessments__assessments` FK here via their own
          `canonical_assessment_id` column.
      - name: title
        data_type: string
        description: >-
          `title` from the canonical member (lowest `assessment_id` in the
          group). Equivalent to `int_assessments__assessments.canonical_title`.
      - name: administered_at
        data_type: date
        description: >-
          `administered_at` from the canonical member. Equivalent to
          `int_assessments__assessments.canonical_administered_at`.
      - name: administered_date
        data_type: date
        description: >-
          `administered_at` cast to date. Convenience for downstream consumers
          that join on date keys.
      - name: grade_level_id
        data_type: int64
        description: >-
          `grade_level_id` from the canonical member. Equivalent to
          `int_assessments__assessments.canonical_grade_level_id`.
      - name: grade_level
        data_type: int64
        description: >-
          `grade_level_id - 1` (upstream uses 1-indexed grade IDs).
      - name: subject_area
        data_type: string
        description: >-
          Constant within the canonical partition. Picked from the canonical
          member.
      - name: scope
        data_type: string
        description: >-
          Constant within the canonical partition. Picked from the canonical
          member.
      - name: module_code
        data_type: string
        description: >-
          Constant within the canonical partition. Picked from the canonical
          member.
      - name: academic_year
        data_type: int64
        description: >-
          Constant within the canonical partition. Picked from the canonical
          member.
      - name: academic_year_clean
        data_type: int64
        description: >-
          Constant within the canonical partition. Picked from the canonical
          member.
      - name: regions_array
        data_type: array<string>
        description: >-
          Union of `regions_assessed_array` across all internal members of the
          canonical group, computed via `array_agg(distinct region)` after
          `unnest`. Consumers `cross join unnest(regions_array) as region` to
          fan out to one row per (canonical assessment, region).
```

**Notes:**

- Per `src/dbt/CLAUDE.md` "All intermediate models must": uniqueness test on
  `canonical_assessment_id` (single-column `unique`) + a `not_null`. The model
  is not consumed directly by external tools (only by other dbt models),
  satisfying the second requirement.
- The `relationships` test points from canonical → members (every
  `canonical_assessment_id` in this model must exist as a
  `canonical_assessment_id` value in the parent member model). Since both
  columns are populated from the same window in upstream, this should always
  hold.
- `is_internal_assessment` is not exposed as a column in the canonical model
  (always TRUE given the upstream filter — would add no signal).
- Column ordering: columns with per-column `data_tests:` go first per
  `src/dbt/CLAUDE.md` YAML conventions. Only `canonical_assessment_id` has
  per-column tests.

- [ ] **Step 2: Re-parse to validate the YAML**

```bash
uv run dbt parse --project-dir .worktrees/cbini/refactor/claude-assessments-grain-split/src/dbt/kipptaf --no-partial-parse
```

Expected: parse succeeds with no warnings about the new model. Any deprecation
warning about test syntax means the `arguments:` nesting is wrong — re-check
`src/dbt/CLAUDE.md` "Generic test syntax (dbt 1.11+)".

---

## Task 3: Build canonical model and verify tests pass

**Files:** none modified — just run dbt.

- [ ] **Step 1: Build the canonical model**

From `/workspaces/teamster`:

```bash
uv run dbt build \
  --select int_assessments__assessments_canonical \
  --project-dir .worktrees/cbini/refactor/claude-assessments-grain-split/src/dbt/kipptaf \
  --defer \
  --state target/prod
```

Expected: model builds, all three tests (`unique`, `not_null`, `relationships`)
pass.

If `--state target/prod` fails with "Could not find manifest", the prod manifest
needs regeneration. Run:

```bash
uv run dbt parse --target prod \
  --project-dir src/dbt/kipptaf \
  --target-path target/prod
```

Then retry the build with `--state target/prod`.

- [ ] **Step 2: Sanity-check row count and grain**

Use the BigQuery MCP (or `bq` CLI fallback) to verify the new model's row count
and grain. Determine the dev schema from `<repo-root>/.dbt/profiles.yml`
(`<username>_kipptaf` convention).

Query:

```sql
select
  count(*) as n_rows,
  count(distinct canonical_assessment_id) as n_distinct_canonical,
from `teamster-332318.<dev_schema>.int_assessments__assessments_canonical`
```

Expected: `n_rows == n_distinct_canonical` (one row per
canonical_assessment_id).

Cross-check against prod members:

```sql
select count(distinct canonical_assessment_id) as n_canonical_groups
from `teamster-332318.kipptaf.int_assessments__assessments`
where is_internal_assessment
```

Expected: `n_canonical_groups` (from prod members) `== n_rows` (from dev
canonical) ± any rows added since the last prod refresh.

---

## Task 4: Migrate `dim_assessment_administrations` to read canonical

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/dim_assessment_administrations.sql`

- [ ] **Step 1: Replace the `canonical_regions` and `illuminate_administrations`
      CTEs**

In
`.worktrees/cbini/refactor/claude-assessments-grain-split/src/dbt/kipptaf/models/marts/dimensions/dim_assessment_administrations.sql`,
replace lines 1–46 (the `with` keyword through the closing paren of the
`illuminate_administrations` CTE, ending just before
`state_nj_parcc_administrations as (`) with this:

```sql
with
    illuminate_administrations as (
        select
            subject_area,
            scope,
            module_code,
            academic_year,
            administered_date,
            grade_level,

            title,

            'illuminate' as assessment_type,

            canonical_assessment_id as source_assessment_id,

            cast(null as string) as administration_period,
            cast(null as string) as test_type,

            concat('kipp', lower(region)) as _dbt_source_project,
        from {{ ref("int_assessments__assessments_canonical") }}
        cross join unnest(regions_array) as region
    ),
```

**Notes:**

- `canonical_regions` CTE is dropped — its logic now lives in
  `int_assessments__assessments_canonical`.
- `SELECT DISTINCT` is gone. One row per `(canonical_assessment_id, region)`
  falls out naturally from the cross-join unnest.
- The `TODO(#3800):` comment is removed.
- Column ordering follows ST06: plain refs (`subject_area`, `scope`,
  `module_code`, `academic_year`, `administered_date`, `grade_level`, `title`)
  first; then literals (`'illuminate' as assessment_type`); then refs that are
  aliased (`canonical_assessment_id as source_assessment_id`); then casts and
  computed (`cast(null...)`, `concat(...)`). Use blank lines per the convention.
- `title` comes through directly from canonical (the canonical model already
  exposes `title` rather than `canonical_title`).
  `canonical_assessment_id as source_assessment_id` is aliased here for symmetry
  with the other administration CTEs in this dim.

The rest of the file (lines 47 onward, `state_nj_parcc_administrations` through
end) is unchanged.

- [ ] **Step 2: Verify the file parses**

```bash
uv run dbt parse --project-dir .worktrees/cbini/refactor/claude-assessments-grain-split/src/dbt/kipptaf --no-partial-parse
```

Expected: parse succeeds. `dim_assessment_administrations` now depends on
`int_assessments__assessments_canonical` instead of
`int_assessments__assessments`.

- [ ] **Step 3: Compile to inspect resolved SQL**

```bash
uv run dbt compile \
  --select dim_assessment_administrations \
  --project-dir .worktrees/cbini/refactor/claude-assessments-grain-split/src/dbt/kipptaf
```

Read the compiled SQL at
`.worktrees/cbini/refactor/claude-assessments-grain-split/src/dbt/kipptaf/target/compiled/kipptaf/models/marts/dimensions/dim_assessment_administrations.sql`.

Verify the `illuminate_administrations` CTE: no `SELECT DISTINCT`, no
`canonical_regions` CTE, surrogate-key inputs unchanged from prod (the columns
going into `dbt_utils.generate_surrogate_key([...])` later in the file should
still resolve to the same expressions).

---

## Task 5: Build dim and verify hash stability

**Files:** none modified — just run dbt and SQL.

- [ ] **Step 1: Build the dim and downstream**

```bash
uv run dbt build \
  --select int_assessments__assessments_canonical+ \
  --project-dir .worktrees/cbini/refactor/claude-assessments-grain-split/src/dbt/kipptaf \
  --defer \
  --state target/prod
```

Expected: `int_assessments__assessments_canonical` (re)builds,
`dim_assessment_administrations` builds, all uniqueness/relationships tests on
`dim_assessment_administrations` pass (including the existing `unique` on
`assessment_administration_key`).

The `+` selector pulls every downstream consumer of the new canonical model —
currently just `dim_assessment_administrations` itself plus anything that reads
from the dim. If a downstream test fails, read its message before assuming hash
drift.

- [ ] **Step 2: Compare dev dim to prod dim — row count**

Via BigQuery MCP. The dev schema is `<username>_kipptaf` (check
`<repo-root>/.dbt/profiles.yml` if unsure).

```sql
with dev as (
    select count(*) as n_dev,
    from `teamster-332318.<dev_schema>.dim_assessment_administrations`
    where source_assessment_id is not null
      -- Illuminate rows have source_assessment_id populated;
      -- state assessments have null
),
prod as (
    select count(*) as n_prod,
    from `teamster-332318.kipptaf.dim_assessment_administrations`
    where source_assessment_id is not null
)
select dev.n_dev, prod.n_prod, dev.n_dev - prod.n_prod as delta
from dev cross join prod
```

Expected: `delta == 0` (or a small positive number if prod is stale relative to
the source data).

- [ ] **Step 3: Compare dev dim to prod dim — key sample**

Verify hash stability by sampling Illuminate administration keys from dev vs
prod:

```sql
with dev_keys as (
    select assessment_administration_key, source_assessment_id, _dbt_source_project,
    from `teamster-332318.<dev_schema>.dim_assessment_administrations`
    where source_assessment_id is not null
),
prod_keys as (
    select assessment_administration_key, source_assessment_id, _dbt_source_project,
    from `teamster-332318.kipptaf.dim_assessment_administrations`
    where source_assessment_id is not null
)
select
    countif(d.assessment_administration_key is null) as n_in_prod_not_dev,
    countif(p.assessment_administration_key is null) as n_in_dev_not_prod,
    countif(d.assessment_administration_key is not null and p.assessment_administration_key is not null) as n_matching,
from dev_keys as d
full outer join prod_keys as p
    on d.source_assessment_id = p.source_assessment_id
    and d._dbt_source_project = p._dbt_source_project
```

Expected: `n_in_prod_not_dev == 0`, `n_in_dev_not_prod == 0` (modulo stale-prod
drift). Same keys on both sides → hash is stable.

If keys differ, the surrogate-key composition has changed inadvertently. Read
the compiled SQL (Task 4 Step 3) and diff against prod to find the change.

---

## Task 6: Lint, format, commit

**Files:** all touched in PR 1.

- [ ] **Step 1: Run trunk check on touched files**

```bash
/workspaces/teamster/.trunk/tools/trunk check --force \
  .worktrees/cbini/refactor/claude-assessments-grain-split/src/dbt/kipptaf/models/assessments/intermediate/int_assessments__assessments_canonical.sql \
  .worktrees/cbini/refactor/claude-assessments-grain-split/src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__assessments_canonical.yml \
  .worktrees/cbini/refactor/claude-assessments-grain-split/src/dbt/kipptaf/models/marts/dimensions/dim_assessment_administrations.sql
```

Expected: no issues. If sqlfluff flags ST03 on the deduplicate input, add the
`# trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below`
directive above the `canonical_picks` CTE per `src/dbt/CLAUDE.md`. (The
deduplicate input here is `ref(...)` not a CTE, so ST03 should not fire — but if
it does, that's the fix.)

- [ ] **Step 2: Stage the changes**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-assessments-grain-split add \
  src/dbt/kipptaf/models/assessments/intermediate/int_assessments__assessments_canonical.sql \
  src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__assessments_canonical.yml
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-assessments-grain-split add -u \
  src/dbt/kipptaf/models/marts/dimensions/dim_assessment_administrations.sql
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-assessments-grain-split status
```

Expected `git status` output: three files staged — two new (the canonical
model + its yml) and one modified (the dim). Nothing else.

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-assessments-grain-split commit -m "$(cat <<'EOF'
refactor(dbt): add canonical-grain assessments model, drop DISTINCT in dim

Adds int_assessments__assessments_canonical at canonical-grain (one row per
canonical_assessment_id) and migrates
dim_assessment_administrations.illuminate_administrations to read from it as a
plain SELECT, removing the SELECT DISTINCT workaround introduced in #3798.
int_assessments__assessments unchanged; PR 2 of #3800 renames it to
int_assessments__assessments_members.

Refs #3800

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Expected: commit succeeds; pre-commit hook (`trunk-fmt-pre-commit`) reformats if
needed. If commit message is rejected by `check-sensitive.sh` for keyword
false-positive, fall back to writing the message to
`.claude/scratch/commit-msg.txt` and committing with `-F` per
`.claude/CLAUDE.md`.

- [ ] **Step 4: Push**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-assessments-grain-split push
```

Expected: push succeeds. `trunk-check-pre-push` runs and must pass. If it blocks
on a sqlfluff/yamllint error not surfaced by Task 6 Step 1's `--force` run, fix
the underlying issue and re-commit (no `--amend` — make a new commit).

---

## Task 7: Open PR 1

**Files:** none — just `gh`.

- [ ] **Step 1: Open the PR**

```bash
gh pr create \
  --repo TEAMSchools/teamster \
  --base main \
  --head cbini/refactor/claude-assessments-grain-split \
  --title "refactor(dbt): add canonical-grain assessments model, drop DISTINCT in dim" \
  --body "$(cat <<'EOF'
## Summary

PR 1 of the three-PR grain-split refactor tracked in #3800.

- Adds `int_assessments__assessments_canonical` at canonical-grain (one row per `canonical_assessment_id`), built by deduplicating `int_assessments__assessments` on `canonical_assessment_id` (ordered by `assessment_id`, matching the existing `first_value` window) and unioning `regions_assessed_array` across members.
- Migrates `dim_assessment_administrations.illuminate_administrations` to a plain SELECT from the new model. No DISTINCT, no inline `canonical_regions` CTE, no `TODO(#3800)` comment.
- `int_assessments__assessments` is unchanged. PR 2 of #3800 renames it to `int_assessments__assessments_members`.

Hash-stable: dim's surrogate-key inputs (`assessment_type`, `module_code`, `administered_date`, `academic_year`, `_dbt_source_project`, `administration_period`, `source_assessment_id`, `test_type`) are unchanged. `source_assessment_id` still equals `canonical_assessment_id` in both old and new code.

Refs #3800.
Design: [`docs/superpowers/specs/2026-05-27-assessments-grain-split-design.md`](docs/superpowers/specs/2026-05-27-assessments-grain-split-design.md).

## Test plan

- [ ] `uv run dbt build --select int_assessments__assessments_canonical+ --project-dir src/dbt/kipptaf` passes locally (run during PR 1 Task 5)
- [ ] Row-count diff vs prod for `dim_assessment_administrations` (Illuminate-only subset) = 0
- [ ] Sample of `(assessment_administration_key, source_assessment_id, _dbt_source_project)` matches prod (Task 5 Step 3 query)
- [ ] dbt Cloud CI passes
EOF
)"
```

Expected: PR is created and URL is returned. Verify the PR shows on issue #3800
(auto-linked via `Refs #3800` in the body).

---

## Verification before claiming complete

Before marking PR 1 done:

- [ ] `uv run dbt build --select int_assessments__assessments_canonical+ --project-dir <worktree>/src/dbt/kipptaf`
      exits 0
- [ ] Row-count diff query (Task 5 Step 2) returns `delta == 0` (or small
      positive due to stale prod)
- [ ] Key-match query (Task 5 Step 3) returns `n_in_prod_not_dev == 0` and
      `n_in_dev_not_prod == 0`
- [ ] `trunk check --force <touched files>` exits 0
- [ ] dbt Cloud CI on the PR is green

Per project CLAUDE.md "Check dbt Cloud CI state before pushing fixes": if any of
these fail and a fix-push is needed, confirm dbt Cloud is in terminal state
before pushing the fix, or bundle multiple fixes into one push.
