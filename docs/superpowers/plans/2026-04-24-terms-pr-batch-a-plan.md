# PR batch A (terms) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate 37M null-composite `term_key` orphans across six `marts/`
consumers of `stg_google_sheets__reporting__terms`, drop `dim_terms.region_key`
diamond FK, and close #3677 / #3717.

**Architecture:** Five targeted dbt model edits (SQL + YAML). Correct a bad
filter literal and broken join predicates in two grades facts, add the
nullable-FK wrapper around every `term_key` derivation, remove the `region_key`
diamond from `dim_terms`. No schema migrations, no new intermediates.

**Tech Stack:** dbt 1.11 (BigQuery adapter), `dbt_utils.generate_surrogate_key`,
dbt relationships/unique tests, dbt Cloud CI
(`dbt build --select state:modified+ --full-refresh`, target `staging`).

**Spec:**
[`docs/superpowers/specs/2026-04-24-terms-pr-batch-a-design.md`](../specs/2026-04-24-terms-pr-batch-a-design.md)

**Branch / worktree:** `cbini/fix/claude-dim-terms-orphans` at
`.worktrees/cbini/fix/claude-dim-terms-orphans/`. All paths in this plan are
relative to that worktree root. Run all commands from there.

---

## Task 1: Fix `fct_grades_assignments.sql`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/facts/fct_grades_assignments.sql:41, 69-80`

- [ ] **Step 1: Replace the `'quarter'` filter with `'RT'`**

Edit `src/dbt/kipptaf/models/marts/facts/fct_grades_assignments.sql:41`:

Old:

```sql
        from {{ ref("stg_google_sheets__reporting__terms") }}
        where `type` = 'quarter'
    )
```

New:

```sql
        from {{ ref("stg_google_sheets__reporting__terms") }}
        where `type` = 'RT'
    )
```

- [ ] **Step 2: Wrap `term_key` in nullable-FK pattern**

Edit `src/dbt/kipptaf/models/marts/facts/fct_grades_assignments.sql:69-80`:

Old:

```sql
    {{
        dbt_utils.generate_surrogate_key(
            [
                "rt.type",
                "rt.code",
                "rt.name",
                "rt.start_date",
                "rt.region",
                "rt.school_id",
            ]
        )
    }} as term_key,
```

New:

```sql
    if(
        rt.code is not null,
        {{
            dbt_utils.generate_surrogate_key(
                [
                    "rt.type",
                    "rt.code",
                    "rt.name",
                    "rt.start_date",
                    "rt.region",
                    "rt.school_id",
                ]
            )
        }},
        cast(null as string)
    ) as term_key,
```

- [ ] **Step 3: Parse-check the model**

Run: `cd src/dbt/kipptaf && uv run dbt parse` Expected: exits 0 with no error
for `fct_grades_assignments`.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/kipptaf/models/marts/facts/fct_grades_assignments.sql
git -c commit.gpgsign=false commit -m "fix(dbt): correct fct_grades_assignments term join (refs #3717)"
```

---

## Task 2: Fix `fct_grades_category.sql`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/facts/fct_grades_category.sql:27, 45-56, 79-82`

- [ ] **Step 1: Replace the `'quarter'` filter with `'RT'`**

Edit `src/dbt/kipptaf/models/marts/facts/fct_grades_category.sql:27`:

Old:

```sql
        from {{ ref("stg_google_sheets__reporting__terms") }}
        where `type` = 'quarter'
    )
```

New:

```sql
        from {{ ref("stg_google_sheets__reporting__terms") }}
        where `type` = 'RT'
    )
```

- [ ] **Step 2: Wrap `term_key` in nullable-FK pattern**

Edit `src/dbt/kipptaf/models/marts/facts/fct_grades_category.sql:45-56`:

Old:

```sql
    {{
        dbt_utils.generate_surrogate_key(
            [
                "rt.type",
                "rt.code",
                "rt.name",
                "rt.start_date",
                "rt.region",
                "rt.school_id",
            ]
        )
    }} as term_key,
```

New:

```sql
    if(
        rt.code is not null,
        {{
            dbt_utils.generate_surrogate_key(
                [
                    "rt.type",
                    "rt.code",
                    "rt.name",
                    "rt.start_date",
                    "rt.region",
                    "rt.school_id",
                ]
            )
        }},
        cast(null as string)
    ) as term_key,
```

- [ ] **Step 3: Fix the `storecode` and `yearid` join predicates**

Edit `src/dbt/kipptaf/models/marts/facts/fct_grades_category.sql:78-82`:

Old:

```sql
left join
    reporting_terms as rt
    on cg.storecode = rt.code
    and cg.schoolid = rt.school_id
    and ce.region = rt.region
    and cg.yearid = rt.powerschool_year_id - 1990
```

New:

```sql
left join
    reporting_terms as rt
    on cg.storecode = rt.name
    and cg.schoolid = rt.school_id
    and ce.region = rt.region
    and cg.yearid = rt.powerschool_year_id
```

- [ ] **Step 4: Parse-check the model**

Run: `cd src/dbt/kipptaf && uv run dbt parse` Expected: exits 0.

- [ ] **Step 5: Commit**

```bash
git add src/dbt/kipptaf/models/marts/facts/fct_grades_category.sql
git -c commit.gpgsign=false commit -m "fix(dbt): correct fct_grades_category term join (refs #3717)"
```

---

## Task 3: Fix `fct_grades_term.sql`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/facts/fct_grades_term.sql:24, 48-59, 93-98`

- [ ] **Step 1: Replace the `'quarter'` filter with `'RT'`**

Edit `src/dbt/kipptaf/models/marts/facts/fct_grades_term.sql:24`:

Old:

```sql
        from {{ ref("stg_google_sheets__reporting__terms") }}
        where `type` = 'quarter'
    )
```

New:

```sql
        from {{ ref("stg_google_sheets__reporting__terms") }}
        where `type` = 'RT'
    )
```

- [ ] **Step 2: Wrap `term_key` in nullable-FK pattern**

Edit `src/dbt/kipptaf/models/marts/facts/fct_grades_term.sql:48-59`:

Old:

```sql
    {{
        dbt_utils.generate_surrogate_key(
            [
                "rt.type",
                "rt.code",
                "rt.name",
                "rt.start_date",
                "rt.region",
                "rt.school_id",
            ]
        )
    }} as term_key,
```

New:

```sql
    if(
        rt.code is not null,
        {{
            dbt_utils.generate_surrogate_key(
                [
                    "rt.type",
                    "rt.code",
                    "rt.name",
                    "rt.start_date",
                    "rt.region",
                    "rt.school_id",
                ]
            )
        }},
        cast(null as string)
    ) as term_key,
```

- [ ] **Step 3: Fix the `storecode` and `yearid` join predicates**

Edit `src/dbt/kipptaf/models/marts/facts/fct_grades_term.sql:93-98`:

Old:

```sql
left join
    reporting_terms as rt
    on fg.storecode = rt.code
    and fg.schoolid = rt.school_id
    and initcap(regexp_extract(fg._dbt_source_relation, r'kipp(\w+)_')) = rt.region
    and fg.yearid = rt.powerschool_year_id - 1990
```

New:

```sql
left join
    reporting_terms as rt
    on fg.storecode = rt.name
    and fg.schoolid = rt.school_id
    and initcap(regexp_extract(fg._dbt_source_relation, r'kipp(\w+)_')) = rt.region
    and fg.yearid = rt.powerschool_year_id
```

- [ ] **Step 4: Parse-check the model**

Run: `cd src/dbt/kipptaf && uv run dbt parse` Expected: exits 0.

- [ ] **Step 5: Commit**

```bash
git add src/dbt/kipptaf/models/marts/facts/fct_grades_term.sql
git -c commit.gpgsign=false commit -m "fix(dbt): correct fct_grades_term term join (refs #3717)"
```

---

## Task 4: Wrap `term_key` on `fct_staff_observations.sql`

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/facts/fct_staff_observations.sql:65-76`

This model assigns per-row `t_*` variables from the LEFT JOIN in its CTE, so the
guard column is `t_code` (not `rt.code`). Preserve the existing alias scheme —
do not rename `t_*` to `rt.*`.

- [ ] **Step 1: Wrap `term_key` in nullable-FK pattern**

Edit `src/dbt/kipptaf/models/marts/facts/fct_staff_observations.sql:65-76`:

Old:

```sql
    {{
        dbt_utils.generate_surrogate_key(
            [
                "t_type",
                "t_code",
                "t_name",
                "t_start_date",
                "t_region",
                "t_school_id",
            ]
        )
    }} as term_key,
```

New:

```sql
    if(
        t_code is not null,
        {{
            dbt_utils.generate_surrogate_key(
                [
                    "t_type",
                    "t_code",
                    "t_name",
                    "t_start_date",
                    "t_region",
                    "t_school_id",
                ]
            )
        }},
        cast(null as string)
    ) as term_key,
```

- [ ] **Step 2: Parse-check the model**

Run: `cd src/dbt/kipptaf && uv run dbt parse` Expected: exits 0.

- [ ] **Step 3: Commit**

```bash
git add src/dbt/kipptaf/models/marts/facts/fct_staff_observations.sql
git -c commit.gpgsign=false commit -m "fix(dbt): wrap fct_staff_observations term_key nullable (refs #3717)"
```

---

## Task 5: Wrap `term_key` on `dim_student_section_enrollments.sql`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/dim_student_section_enrollments.sql:35-46`

- [ ] **Step 1: Wrap `term_key` in nullable-FK pattern**

Edit
`src/dbt/kipptaf/models/marts/dimensions/dim_student_section_enrollments.sql:35-46`:

Old:

```sql
    {{
        dbt_utils.generate_surrogate_key(
            [
                "rt.type",
                "rt.code",
                "rt.name",
                "rt.start_date",
                "rt.region",
                "rt.school_id",
            ]
        )
    }} as term_key,
```

New:

```sql
    if(
        rt.code is not null,
        {{
            dbt_utils.generate_surrogate_key(
                [
                    "rt.type",
                    "rt.code",
                    "rt.name",
                    "rt.start_date",
                    "rt.region",
                    "rt.school_id",
                ]
            )
        }},
        cast(null as string)
    ) as term_key,
```

- [ ] **Step 2: Parse-check the model**

Run: `cd src/dbt/kipptaf && uv run dbt parse` Expected: exits 0.

- [ ] **Step 3: Commit**

```bash
git add src/dbt/kipptaf/models/marts/dimensions/dim_student_section_enrollments.sql
git -c commit.gpgsign=false commit -m "fix(dbt): wrap dim_student_section_enrollments term_key nullable (refs #3717)"
```

---

## Task 6: Wrap `term_key` on `dim_student_assessment_expectations.sql`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/dim_student_assessment_expectations.sql:44-55`

- [ ] **Step 1: Wrap `term_key` in nullable-FK pattern**

Edit
`src/dbt/kipptaf/models/marts/dimensions/dim_student_assessment_expectations.sql:44-55`:

Old:

```sql
    {{
        dbt_utils.generate_surrogate_key(
            [
                "rt.type",
                "rt.code",
                "rt.name",
                "rt.start_date",
                "rt.region",
                "rt.school_id",
            ]
        )
    }} as term_key,
```

New:

```sql
    if(
        rt.code is not null,
        {{
            dbt_utils.generate_surrogate_key(
                [
                    "rt.type",
                    "rt.code",
                    "rt.name",
                    "rt.start_date",
                    "rt.region",
                    "rt.school_id",
                ]
            )
        }},
        cast(null as string)
    ) as term_key,
```

- [ ] **Step 2: Parse-check the model**

Run: `cd src/dbt/kipptaf && uv run dbt parse` Expected: exits 0.

- [ ] **Step 3: Commit**

```bash
git add src/dbt/kipptaf/models/marts/dimensions/dim_student_assessment_expectations.sql
git -c commit.gpgsign=false commit -m "fix(dbt): wrap dim_student_assessment_expectations term_key nullable (refs #3717)"
```

---

## Task 7: Drop `region_key` from `dim_terms`

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_terms.sql:26-30`
- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_terms.yml:12-40`

- [ ] **Step 1: Remove the `region_key` SELECT block**

Edit `src/dbt/kipptaf/models/marts/dimensions/dim_terms.sql:26-30`:

Old:

```sql
    }} as term_key,

    if(
        t.city is not null,
        {{ dbt_utils.generate_surrogate_key(["t.city"]) }},
        cast(null as string)
    ) as region_key,

    if(
        ll.location_name is not null,
        {{ dbt_utils.generate_surrogate_key(["ll.location_name"]) }},
        cast(null as string)
    ) as location_key,
```

New:

```sql
    }} as term_key,

    if(
        ll.location_name is not null,
        {{ dbt_utils.generate_surrogate_key(["ll.location_name"]) }},
        cast(null as string)
    ) as location_key,
```

- [ ] **Step 2: Remove the `region_key` YAML entry and update the `term_key`
      description**

Edit `src/dbt/kipptaf/models/marts/dimensions/properties/dim_terms.yml:11-40`:

Old:

```yaml
- name: term_key
  data_type: string
  description: >-
    Surrogate key for this dimension. Hash composition uses term type, code,
    name, start date, region, and school ID as internal inputs; region and
    school ID are not exposed as mart columns (reachable via region_key and
    location_key FK traversal).
  constraints:
    - type: primary_key
      warn_unsupported: false
  data_tests:
    - unique
    - not_null

- name: region_key
  data_type: string
  description: >-
    Foreign key to dim_regions. Surrogate key derived from the canonical region.
    Nullable for org-wide periods and for terms whose school is not mapped to a
    region.
  constraints:
    - type: foreign_key
      to: ref('dim_regions')
      to_columns: [region_key]
      warn_unsupported: false
  data_tests:
    - relationships:
        arguments:
          to: ref('dim_regions')
          field: region_key
```

New:

```yaml
- name: term_key
  data_type: string
  description: >-
    Surrogate key for this dimension. Hash composition uses term type, code,
    name, start date, region, and school ID as internal inputs; region and
    school ID are not exposed as mart columns. Region attributes reach via
    dim_terms → dim_locations → dim_regions.
  constraints:
    - type: primary_key
      warn_unsupported: false
  data_tests:
    - unique
    - not_null
```

- [ ] **Step 3: Parse-check**

Run: `cd src/dbt/kipptaf && uv run dbt parse` Expected: exits 0.

- [ ] **Step 4: Confirm no mart consumes `dim_terms.region_key`**

Run:

```bash
grep -rn "dim_terms" src/dbt/kipptaf/models | grep -i region_key
```

Expected: no output. (If any file matches, halt and flag to the user.)

- [ ] **Step 5: Commit**

```bash
git add src/dbt/kipptaf/models/marts/dimensions/dim_terms.sql \
        src/dbt/kipptaf/models/marts/dimensions/properties/dim_terms.yml
git -c commit.gpgsign=false commit -m "refactor(dbt): drop dim_terms.region_key diamond FK (refs #3717)"
```

---

## Task 8: Append surrogate-key audit entry

**Files:**

- Modify: `docs/superpowers/specs/2026-04-15-column-naming-audit.md:364` (append
  row after `fct_grades_gpa.term_key`)

- [ ] **Step 1: Append a new row to the surrogate-key changes table**

Edit `docs/superpowers/specs/2026-04-15-column-naming-audit.md` — append a row
directly below the existing `fct_grades_gpa.term_key` row:

Insert after the line beginning ``| `fct_grades_gpa.term_key```:

```markdown
| `fct_grades_assignments.term_key` / `fct_grades_category.term_key` /
`fct_grades_term.term_key` / `fct_staff_observations.term_key` /
`dim_student_section_enrollments.term_key` /
`dim_student_assessment_expectations.term_key` |
`generate_surrogate_key([...6-tuple...])` — unwrapped; all unmatched LEFT JOIN
rows hashed to the all-NULLs placeholder (`eb66153e09d138b38fc979bff5b437d5`),
producing ~37M relationships-test orphans across the six consumers | Same
derivation, wrapped:
`if(rt.code is not null, generate_surrogate_key([...6-tuple...]), cast(null as string))`.
Grades facts also corrected: `fct_grades_assignments` filter `type='quarter'` →
`'RT'`; `fct_grades_category` and `fct_grades_term` filter `'quarter'` → `'RT'`,
join `storecode=rt.name` (was `rt.code`), `yearid=rt.powerschool_year_id` (was
`powerschool_year_id - 1990`) | Null handling changes (rule 4) — plus predicate
corrections that migrate grades-facts rows from placeholder-hash to real
`term_key` |
```

- [ ] **Step 2: Add a bullet to "Unchanged surrogate keys (explicit
      confirmation)"**

Edit `docs/superpowers/specs/2026-04-15-column-naming-audit.md` around line 379
(the existing bullet list). Append a bullet at the end of the list:

```markdown
- `dim_terms.term_key` — hash inputs and derivation unchanged. The `region_key`
  FK was dropped from `dim_terms` in this batch per the strict-chain traversal
  rule, but `term_key` composition is untouched.
```

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-04-15-column-naming-audit.md
git -c commit.gpgsign=false commit -m "docs(spec): log term_key nullable-wrap in surrogate-key audit"
```

---

## Task 9: Trunk check and push

- [ ] **Step 1: Run trunk check in CI mode**

Trunk git hooks aren't installed in worktrees, so lint manually before push.

Run: `/workspaces/teamster/.trunk/tools/trunk check --ci` Expected: exits 0 with
no issues. If sqlfluff flags ST06 column ordering or line length >88, fix inline
and re-run until clean.

- [ ] **Step 2: Push the branch**

Run: `git push` Expected: `remote: Resolving deltas: …` with no errors.

---

## Task 10: Open the PR

- [ ] **Step 1: Create the PR using `mcp__github__create_pull_request`**

Invoke with:

- `owner`: `TEAMSchools`
- `repo`: `teamster`
- `head`: `cbini/fix/claude-dim-terms-orphans`
- `base`: `main`
- `title`:
  `fix(dbt): eliminate 37M term_key orphans, drop region_key diamond (closes #3677, #3717)`
- `body`: use `.github/pull_request_template.md` structure. Minimum:

```markdown
## Summary

- Fix 37M null-composite `term_key` orphans across six `marts/` consumers
- Correct `'quarter'` → `'RT'` filter in three grades facts
- Fix `cg.storecode = rt.name` (was `rt.code`) and
  `yearid = powerschool_year_id` (was `- 1990`) in `fct_grades_category` /
  `fct_grades_term`
- Wrap every fact-side `term_key` in the nullable-FK pattern
- Drop `dim_terms.region_key` (strict-chain traversal, reachable via
  `dim_locations.region_key`)

Closes #3677 (sheet duplicate already cleaned in source) and #3717.

Spec: `docs/superpowers/specs/2026-04-24-terms-pr-batch-a-design.md`

## Test plan

- [ ] dbt Cloud CI (`dbt build --select state:modified+ --full-refresh`,
      staging) passes
- [ ] `unique_dim_terms_term_key` clean
- [ ] Six fact-side `term_key` relationships tests clean
- [ ] Post-merge BigQuery spot check:
      `count(*) where term_key is not null and term_key not in (select term_key from dim_terms)`
      returns 0 for all six consumers
- [ ] No mart/rpt references `dim_terms.region_key` (verified via grep)
```

- [ ] **Step 2: Verify the returned PR title and body match the intent**

After the tool returns, check the `title` and `body` fields in the response
match what was requested (per CLAUDE.md: verify tool-call results for resource
creation).

- [ ] **Step 3: Return the PR URL to the user for review**

Paste the PR URL in the response.

---

## Task 11: Post-PR follow-up issues

Open three follow-up issues referencing #3717. All three are residual
sheet-coverage / upstream-scaffold work that is out of scope for this PR.

- [ ] **Step 1: File the sheet-backfill issue**

Use `mcp__github__issue_write` with:

- `owner`: `TEAMSchools`
- `repo`: `teamster`
- `method`: `create`
- `title`:
  `fix(dbt): backfill pre-AY24 per-region RT rows in reporting terms sheet`
- `body`: explain that after PR batch A, pre-AY24 Newark/Camden/Miami facts get
  `term_key = NULL` because the sheet's per-region RT rows start 2024-07-01
  (2025-07-01 for Paterson). Two paths: backfill historical per-region rows in
  the sheet, or document the NULL as intentional in `dim_terms.description`.
  Link to #3717.
- `labels`: `["fix", "dbt"]`

- [ ] **Step 2: File the scaffold-region issue**

Use `mcp__github__issue_write` with:

- `title`: `fix(dbt): int_assessments__scaffold.region IS NULL for 1.6M rows`
- `body`: 1.6M rows in `int_assessments__scaffold` have `region IS NULL`, 273K
  of those also have `administered_at IS NULL`. These cannot match any term via
  `region` / date. Investigate upstream region population. Link to #3717.
- `labels`: `["fix", "dbt"]`

- [ ] **Step 3: File the Paterson coverage issue**

Use `mcp__github__issue_write` with:

- `title`:
  `fix(dbt): dim_student_assessment_expectations Paterson 2026-02-02 term gap (105 rows)`
- `body`: 105 Paterson assessments dated 2026-02-02 fail to match any RT row —
  likely a `school_id` mismatch in the sheet's Paterson RT coverage.
  Investigate. Link to #3717.
- `labels`: `["fix", "dbt"]`

- [ ] **Step 4: Close #3677**

Use `mcp__github__issue_write` with:

- `method`: `update`
- `issue_number`: `3677`
- `state`: `closed`
- `state_reason`: `completed`

Then comment on #3677 via `mcp__github__add_issue_comment` linking the PR URL
and noting the BigQuery verification that 0 duplicates exist in
`stg_google_sheets__reporting__terms` or `dim_terms` under the current 6-tuple
composition (sheet owner cleaned the duplicate row between the issue's reopen
and now).

---

## Post-execution notes

- dbt Cloud CI is the authoritative test run; the job is
  `dbt build --select state:modified+ --full-refresh` against the Staging
  environment. Per `src/dbt/kipptaf/CLAUDE.md`. Do not attempt a full local
  `dbt build` — the staging schema is `dbt_cloud_pr_…`, not writable from this
  environment.
- The `--full-refresh` flag on CI is required because `term_key` null handling
  changes force every consumer row to rehash.
- If any of the six relationships tests still fail in CI, inspect the failing
  rows in `dbt_cloud_pr_<ci_id>_<pr_num>_kipptaf_dbt_test__audit` — those are
  legitimate residual coverage gaps, not `term_key` logic bugs.
