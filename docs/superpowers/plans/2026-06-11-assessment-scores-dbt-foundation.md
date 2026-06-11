# Assessment-scores dbt mart foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the response/standard columns to
`fct_assessment_scores_enrollment_scoped` and an `assessment_key` FK to
`dim_assessment_administrations`, so the Cube semantic layer can break scores
down by standard/skill and read canonical assessment descriptors from
`dim_assessments`.

**Architecture:** Two additive dbt mart changes in the `kipptaf` project. Both
are pure projections of values already computed upstream — no surrogate-key hash
changes. The fact gains response-grain columns from
`int_assessments__response_rollup` plus a `standard_domain` lookup; the
administration dim gains a single surrogate-key FK that resolves to the
canonical-representative `dim_assessments` row.

**Tech Stack:** dbt (BigQuery dialect), `src/dbt/kipptaf`. All work happens in
the worktree at
`/workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube`.

**Scope guardrails:**

- Additive only. Do **not** change any `generate_surrogate_key(...)` input list.
- Follow `src/dbt/kipptaf/models/marts/CLAUDE.md` (column-naming R1–R10, ST06
  ordering, reserved-word backticks).
- Do **not** use `select distinct` / `qualify row_number() = 1` /
  `dbt_utils.deduplicate` to paper over the `standard_domains` lookup — instead
  verify the lookup key is unique (Task 1, Step 2).

---

## Task 0: Worktree dbt setup

**Files:** none (environment only).

- [ ] **Step 1: Install dbt packages in the worktree**

A fresh worktree has no `dbt_packages/`.

Run:

```bash
uv run dbt deps --project-dir /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube/src/dbt/kipptaf
```

Expected: `Installed from ...` / `Up to date` with no error.

- [ ] **Step 2: Confirm the prod manifest exists for `--defer`**

Run:

```bash
ls /workspaces/teamster/src/dbt/kipptaf/target/prod/manifest.json
```

Expected: the file exists. If missing, regenerate:
`uv run dbt parse --target prod --project-dir /workspaces/teamster/src/dbt/kipptaf --target-path target/prod`.

---

## Task 1: Project response/standard columns onto the fact

Add `response_type`, `response_type_code`, `response_type_description`,
`response_type_root_description`, `is_replacement`,
`performance_band_label_number`, and `standard_domain` to
`fct_assessment_scores_enrollment_scoped`. Internal (Illuminate) rows get real
values from `int_assessments__response_rollup`; state rows get typed NULLs
(state scores have no response-type breakdown).

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_enrollment_scoped.sql`
- Modify:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_assessment_scores_enrollment_scoped.yml`

- [ ] **Step 1: Confirm the source columns exist in the rollup**

Run:

```bash
uv run dbt show --inline "select response_type, response_type_code, response_type_description, response_type_root_description, is_replacement, performance_band_label_number from {{ ref('int_assessments__response_rollup') }} limit 1" --project-dir /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube/src/dbt/kipptaf --target dev
```

Expected: returns one row (columns resolve). If any column errors, stop and
re-trace before editing.

- [ ] **Step 2: Verify the `standard_domains` lookup key is unique**

The fact will left-join `stg_google_sheets__assessments__standard_domains` on
`response_type_code = standard_code`. A duplicate `standard_code` would fan out
the fact. Confirm uniqueness:

```bash
uv run dbt show --inline "select standard_code, count(*) as n from {{ ref('stg_google_sheets__assessments__standard_domains') }} group by 1 having count(*) > 1" --project-dir /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube/src/dbt/kipptaf --target dev
```

Expected: **zero rows**. If any row returns, the join would fan out — stop and
raise it with the data team (do not add a defensive dedupe).

- [ ] **Step 3: Add the source columns + lookup join to the
      `internal_assessments` CTE**

In `fct_assessment_scores_enrollment_scoped.sql`, the `internal_assessments` CTE
selects from `int_assessments__response_rollup as rr`. Add the new `rr.*`
columns and a left join to the standard-domain lookup. The CTE's column list
gains (placed with the other `rr.` enumerations, before the constant/aliased
columns per ST06):

```sql
            rr.response_type,
            rr.response_type_code,
            rr.response_type_description,
            rr.response_type_root_description,
            rr.is_replacement,
            rr.performance_band_label_number,

            sd.standard_domain,
```

And add the join after the existing `inner join ... as c ...` joins in that CTE:

```sql
        left join
            {{ ref("stg_google_sheets__assessments__standard_domains") }} as sd
            on rr.response_type_code = sd.standard_code
```

(`response_type` and `response_type_code` may already be selected for the hash —
if so, do not duplicate them; keep one copy each.)

- [ ] **Step 4: Project the columns in the internal `SELECT` branch**

In the `/* internal assessments */` final `SELECT` (the branch reading
`internal_assessments as ia`), add, grouped with the other `ia.` columns:

```sql
    ia.response_type,
    ia.response_type_code,
    ia.response_type_description,
    ia.response_type_root_description,
    ia.is_replacement,
    ia.performance_band_label_number,
    ia.standard_domain,
```

- [ ] **Step 5: Project typed NULLs in the state `SELECT` branch**

In the `/* state assessments */` final `SELECT` (reading `state_union as su`),
add the same column names as typed NULLs so the `UNION ALL` aligns. Place them
with the constants group per ST06:

```sql
    cast(null as string) as response_type,
    cast(null as string) as response_type_code,
    cast(null as string) as response_type_description,
    cast(null as string) as response_type_root_description,
    cast(null as bool) as is_replacement,
    cast(null as int) as performance_band_label_number,
    cast(null as string) as standard_domain,
```

- [ ] **Step 6: Add the columns to the contract YAML**

In `properties/fct_assessment_scores_enrollment_scoped.yml`, add column entries
(no per-column data_tests; descriptions required). Match `data_type` to the
casts above (`string`, `string`, `string`, `string`, `boolean`, `int64`,
`string`):

```yaml
- name: response_type
  data_type: string
  description: >-
    The standard/skill breakdown level of this scored response (e.g. overall vs
    a specific standard). Null for state assessments, which have no
    response-type breakdown.

- name: response_type_code
  data_type: string
  description: >-
    Standard code for this response type (joins the standard-domain lookup).
    Null for state assessments.

- name: response_type_description
  data_type: string
  description: Human-readable description of the response type. Null for state.

- name: response_type_root_description
  data_type: string
  description: >-
    Root/parent description of the response type's standard hierarchy. Null for
    state.

- name: is_replacement
  data_type: boolean
  description: >-
    TRUE if this Illuminate score replaced a prior attempt for the same student
    and canonical assessment. Null for state.

- name: performance_band_label_number
  data_type: int64
  description: >-
    Numeric rank of the performance band (pairs with proficiency_level). Null
    for state.

- name: standard_domain
  data_type: string
  description: >-
    Domain grouping for the response type's standard, from the standard-domains
    reference sheet. Null when the standard code has no mapping or for state
    assessments.
```

- [ ] **Step 7: Build the fact and its downstream, verify success + no new
      warnings**

Run:

```bash
uv run dbt build --select fct_assessment_scores_enrollment_scoped --project-dir /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube/src/dbt/kipptaf --target dev --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: `PASS`/`Completed successfully`. The PK `unique`/`not_null` tests
still pass (row count unchanged — the `standard_domains` join is verified 1:1 in
Step 2). If the row count changed, the join fanned out — revert and recheck
Step 2.

- [ ] **Step 8: Confirm row count is unchanged vs prod**

Run:

```bash
uv run dbt show --inline "select count(*) as n from {{ ref('fct_assessment_scores_enrollment_scoped') }}" --project-dir /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube/src/dbt/kipptaf --target dev
```

Expected: equals the prod row count (~14.19M, the figure from the spec's
verified findings). A higher count means fan-out.

- [ ] **Step 9: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube add src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_enrollment_scoped.sql src/dbt/kipptaf/models/marts/facts/properties/fct_assessment_scores_enrollment_scoped.yml
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube commit -m "feat(dbt): add response/standard columns to assessment-scores fact

Refs #4163"
```

---

## Task 2: Add `assessment_key` FK to `dim_assessment_administrations`

Add one column, `assessment_key`, computed from the four inputs already present
in the model's `all_administrations` CTE. It resolves to the
canonical-representative `dim_assessments` row (Illuminate) or the 1:1 state
row.

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/dim_assessment_administrations.sql`
- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_assessment_administrations.yml`

- [ ] **Step 1: Add the FK column to the final `SELECT`**

In `dim_assessment_administrations.sql`, the final `SELECT` reads from
`all_administrations`, which carries `assessment_type`, `module_code`,
`source_assessment_id`, and `test_type`. Add, immediately after the existing
`assessment_administration_key` surrogate-key block:

```sql
    {{
        dbt_utils.generate_surrogate_key(
            [
                "assessment_type",
                "module_code",
                "source_assessment_id",
                "test_type",
            ]
        )
    }} as assessment_key,
```

Do not alter the existing `assessment_administration_key` inputs.

- [ ] **Step 2: Add the FK column + relationships test to the contract YAML**

In `properties/dim_assessment_administrations.yml`, add the column with a
`foreign_key` constraint and a `relationships` test to `dim_assessments`:

```yaml
- name: assessment_key
  data_type: string
  description: >-
    FK to dim_assessments. Resolves to the canonical-representative member row
    for Illuminate (the canonical id is itself the representative member id) and
    the 1:1 row for state assessments. Lets consumers read canonical descriptors
    (title, academic_subject, type, grade_level_tested, module_type) without
    denormalizing them onto this dim.
  constraints:
    - type: foreign_key
      to: ref('dim_assessments')
      to_columns: [assessment_key]
      warn_unsupported: false
  data_tests:
    - relationships:
        arguments:
          to: ref('dim_assessments')
          field: assessment_key
```

- [ ] **Step 3: Build the dim + run the relationships test**

Run:

```bash
uv run dbt build --select dim_assessment_administrations --project-dir /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube/src/dbt/kipptaf --target dev --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: `PASS`. The new `relationships` test passes for the Illuminate branch
(verified 4748/4748 in the spec).

- [ ] **Step 4: Verify the state-branch FK populates (the spec's open validation
      item)**

The spec flagged that only Illuminate was empirically proven. Confirm state rows
resolve (no NULL/orphan `assessment_key` for state administrations):

```bash
uv run dbt show --inline "select countif(a.assessment_key is null) as n_unmatched, count(*) as n_total from {{ ref('dim_assessment_administrations') }} adm left join {{ ref('dim_assessments') }} a on adm.assessment_key = a.assessment_key where adm._dbt_source_project is not null" --project-dir /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube/src/dbt/kipptaf --target dev
```

Expected: `n_unmatched = 0`. (`_dbt_source_project is not null` scopes to
region-scoped administrations, which is where state assessments live.) If
`n_unmatched > 0`, capture the unmatched `assessment_type`/`module_code` and
raise before proceeding — the state key composition needs reconciliation.

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube add src/dbt/kipptaf/models/marts/dimensions/dim_assessment_administrations.sql src/dbt/kipptaf/models/marts/dimensions/properties/dim_assessment_administrations.yml
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube commit -m "feat(dbt): add assessment_key FK from administrations to dim_assessments

Refs #4163"
```

---

## Task 3: Trunk-check and push

**Files:** none (validation).

- [ ] **Step 1: Trunk-check the changed SQL/YAML**

sqlfluff/yamllint fire at pre-push, not pre-commit. Verify from inside the
worktree:

```bash
/workspaces/teamster/.trunk/tools/trunk check --force src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_enrollment_scoped.sql src/dbt/kipptaf/models/marts/facts/properties/fct_assessment_scores_enrollment_scoped.yml src/dbt/kipptaf/models/marts/dimensions/dim_assessment_administrations.sql src/dbt/kipptaf/models/marts/dimensions/properties/dim_assessment_administrations.yml
```

Run with cwd set to the worktree. Expected: `No issues`. Fix any ST06 ordering /
RF04 reserved-word findings and rebuild before pushing.

- [ ] **Step 2: Push (confirm dbt Cloud CI is idle first)**

Pushing triggers dbt Cloud CI. Push the branch:

```bash
git -C /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-assessment-scores-cube push origin cristinabaldor/feat/claude-assessment-scores-cube
```

- [ ] **Step 3: After CI passes, pull warnings**

Use `mcp__dbt__get_job_run_error(run_id=<ci_run>, warning_only=true)`. New
marts-model warnings must be triaged per `marts/CLAUDE.md` (search open issues
by model + FK target before filing). Pre-existing warnings unchanged from `main`
are ignorable.

---

## Self-review notes

- **Spec coverage (this plan only):** fact response/standard columns → Task 1;
  administration `assessment_key` FK → Task 2. The dim enrichments
  (`is_foundations`, `year_in_network`, `head_of_school`, `status_504`,
  `is_sipps`, `is_self_contained`) and the entire Cube layer are **out of scope
  for this plan** — they are Plan 2 (dbt dim enrichments) and Plan 3 (Cube),
  respectively.
- **No hash changes:** neither task touches a `generate_surrogate_key` input
  list; the new `assessment_key` is a _new_ surrogate, not a change to an
  existing one.
- **Fan-out guards:** Task 1 Step 2 (standard_domains uniqueness) and Step 8
  (row-count equality) protect the fact's grain; Task 2 Step 4 confirms the FK
  is not silently NULL.
