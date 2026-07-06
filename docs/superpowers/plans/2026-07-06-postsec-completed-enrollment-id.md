# postsec_completed_enrollment_id Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `postsec_completed_enrollment_id` column (plus its full parallel
`postsec_completed_*` attribute set) to `int_kippadb__enrollment_pivot` that
returns a student's best post-secondary enrollment, preferring a completed
(`Graduated`) enrollment over any in-progress or withdrawn one.

**Architecture:** In the `enrollment_wide` CTE, add a compact
`unnest`-of-structs scalar subquery beside the existing `ugrad_enrollment_id`
CASE that ranks the three already-resolved track picks (`ba`/`aa`/`cte`) by
completed-tier → degree level → recency. Carry the id into the final `select`
and add two `stg_kippadb__enrollment` / `stg_kippadb__account` joins to surface
the parallel attribute columns. Additive only — no existing column or consumer
changes.

**Tech Stack:** dbt (BigQuery), `uv run dbt`, trunk (sqlfluff + yamllint).

**Spec:**
`docs/superpowers/specs/2026-07-06-postsec-completed-enrollment-id-design.md`
(Issue #4331, PR #4332)

---

## File structure

- Modify:
  `src/dbt/kipptaf/models/kippadb/intermediate/int_kippadb__enrollment_pivot.sql`
  — add the pick, carry the id to the final select, add the attribute joins and
  columns.
- Modify:
  `src/dbt/kipptaf/models/kippadb/intermediate/properties/int_kippadb__enrollment_pivot.yml`
  — document the new id and attribute columns.

All work happens on branch
`CGibson17/feat/claude-postsec-completed-enrollment-id` (already checked out).

**Preflight (run once before Task 3 build/verify):** confirm the prod manifest
used for `--defer` exists; regenerate if missing.

```bash
ls src/dbt/kipptaf/target/prod/manifest.json \
  || VIRTUAL_ENV= DBT_PROFILES_DIR=.dbt uv run dbt parse --target prod \
       --project-dir src/dbt/kipptaf --target-path target/prod
```

---

## Task 1: Add the completed-first pick and attribute set to the model SQL

**Files:**

- Modify:
  `src/dbt/kipptaf/models/kippadb/intermediate/int_kippadb__enrollment_pivot.sql`

- [ ] **Step 1: Add the pick subquery in `enrollment_wide`**

Insert this column immediately after the existing `ugrad_enrollment_id` CASE
(currently ends `end as ugrad_enrollment_id,` at line 290), before the
`coalesce(emp.start_date, ...)` block. `e` is `enrollment_grouped`;
`ba`/`aa`/`cte` are the already-joined `stg_kippadb__enrollment` picks.

```sql
            (
                select cand.enrollment_id
                from
                    unnest([
                        struct(
                            e.ba_enrollment_id as enrollment_id,
                            if(ba.status = 'Graduated', 1, 0) as is_completed,
                            3 as degree_rank,
                            ba.start_date as start_date
                        ),
                        struct(
                            e.aa_enrollment_id,
                            if(aa.status = 'Graduated', 1, 0),
                            2,
                            aa.start_date
                        ),
                        struct(
                            e.cte_enrollment_id,
                            if(cte.status = 'Graduated', 1, 0),
                            1,
                            cte.start_date
                        )
                    ]) as cand
                where cand.enrollment_id is not null
                order by
                    cand.is_completed desc,
                    cand.degree_rank desc,
                    cand.start_date desc
                limit 1
            ) as postsec_completed_enrollment_id,
```

- [ ] **Step 2: Carry the id into the final `select`**

In the final `select` block, add this line immediately after
`ew.ugrad_enrollment_id,` (currently line 336):

```sql
    ew.postsec_completed_enrollment_id,
```

- [ ] **Step 3: Add the parallel attribute columns**

In the final `select`, immediately after the last `ugrad_*` column
(`uga.adjusted_6_year_minority_graduation_rate as ugrad_adjusted_6_year_minority_graduation_rate,`,
currently line 442) and before the `is_never_enrolled` expression, insert:

```sql
    pce.name as postsec_completed_school_name,
    pce.pursuing_degree_type as postsec_completed_pursuing_degree_type,
    pce.status as postsec_completed_status,
    pce.start_date as postsec_completed_start_date,
    pce.actual_end_date as postsec_completed_actual_end_date,
    pce.anticipated_graduation as postsec_completed_anticipated_graduation,
    pce.account_type as postsec_completed_account_type,
    pce.major as postsec_completed_major,
    pce.major_area as postsec_completed_major_area,
    pce.college_major_declared as postsec_completed_college_major_declared,
    pce.date_last_verified as postsec_completed_date_last_verified,
    pce.of_credits_required_for_graduation
    as postsec_completed_credits_required_for_graduation,

    pcea.name as postsec_completed_account_name,
    pcea.billing_state as postsec_completed_billing_state,
    pcea.nces_id as postsec_completed_nces_id,
    pcea.act_composite_25_75 as postsec_completed_act_composite_25_75,
    pcea.competitiveness_ranking as postsec_completed_competitiveness_ranking,
    pcea.adjusted_6_year_minority_graduation_rate
    as postsec_completed_adjusted_6_year_minority_graduation_rate,
```

- [ ] **Step 4: Add the attribute joins**

At the very end of the model, immediately after the existing `ug`/`uga` joins
(currently the last two lines, `left join ... as uga on ug.school = uga.id`),
append:

```sql
left join
    {{ ref("stg_kippadb__enrollment") }} as pce
    on ew.postsec_completed_enrollment_id = pce.id
left join {{ ref("stg_kippadb__account") }} as pcea on pce.school = pcea.id
```

- [ ] **Step 5: Compile to validate refs and SQL**

Run:

```bash
VIRTUAL_ENV= DBT_PROFILES_DIR=.dbt uv run dbt compile \
  --select int_kippadb__enrollment_pivot --target prod \
  --project-dir src/dbt/kipptaf 2>&1 | tail -15
```

Expected: `Compiled node 'int_kippadb__enrollment_pivot'` with no errors.
(`--target prod` compile does no warehouse write and is not classifier-blocked.)

- [ ] **Step 6: Lint the model**

Run from the repo root:

```bash
.trunk/tools/trunk check --force \
  src/dbt/kipptaf/models/kippadb/intermediate/int_kippadb__enrollment_pivot.sql \
  2>&1 | tail -20
```

Expected: `✔ No issues`. If sqlfluff ST06 (column ordering) fires on the pick
subquery's placement, move `postsec_completed_enrollment_id` so it sits with the
other complex/CASE expressions (adjacent to `ugrad_enrollment_id`) and re-run.

- [ ] **Step 7: Commit**

```bash
git add src/dbt/kipptaf/models/kippadb/intermediate/int_kippadb__enrollment_pivot.sql
git commit -m "feat(kipptaf): add postsec_completed_enrollment_id to enrollment pivot

Refs #4331

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Document the new columns in the properties YAML

**Files:**

- Modify:
  `src/dbt/kipptaf/models/kippadb/intermediate/properties/int_kippadb__enrollment_pivot.yml`

- [ ] **Step 1: Add the id column entry**

Immediately after the `ugrad_enrollment_id` entry (currently lines 18-19), add:

```yaml
- name: postsec_completed_enrollment_id
  data_type: string
  description:
    Enrollment id of the student's best post-secondary enrollment across the BA,
    AA, and CTE track picks — preferring a completed (Graduated) enrollment over
    any in-progress or withdrawn one, then higher degree level (BA over AA over
    CTE), then most recent start date. Null when the student has no BA, AA, or
    CTE enrollment.
```

- [ ] **Step 2: Add the attribute column entries**

Immediately after the last `ugrad_*` entry
(`ugrad_adjusted_6_year_minority_graduation_rate`, currently lines 230-231) and
before the `is_never_enrolled` entry, add. Data types mirror the corresponding
`ugrad_*` columns exactly.

```yaml
- name: postsec_completed_school_name
  data_type: string
  description:
    Name of the enrollment identified by postsec_completed_enrollment_id.
- name: postsec_completed_pursuing_degree_type
  data_type: string
  description:
    Pursuing degree type of the enrollment identified by
    postsec_completed_enrollment_id.
- name: postsec_completed_status
  data_type: string
  description:
    Status of the enrollment identified by postsec_completed_enrollment_id.
- name: postsec_completed_start_date
  data_type: date
  description:
    Start date of the enrollment identified by postsec_completed_enrollment_id.
- name: postsec_completed_actual_end_date
  data_type: date
  description:
    Actual end date of the enrollment identified by
    postsec_completed_enrollment_id.
- name: postsec_completed_anticipated_graduation
  data_type: date
  description:
    Anticipated graduation date of the enrollment identified by
    postsec_completed_enrollment_id.
- name: postsec_completed_account_type
  data_type: string
  description:
    Account type of the enrollment identified by
    postsec_completed_enrollment_id.
- name: postsec_completed_major
  data_type: string
  description:
    Major of the enrollment identified by postsec_completed_enrollment_id.
- name: postsec_completed_major_area
  data_type: string
  description:
    Major area of the enrollment identified by postsec_completed_enrollment_id.
- name: postsec_completed_college_major_declared
  data_type: boolean
  description:
    Whether a college major was declared for the enrollment identified by
    postsec_completed_enrollment_id.
- name: postsec_completed_date_last_verified
  data_type: date
  description:
    Date the enrollment identified by postsec_completed_enrollment_id was last
    verified.
- name: postsec_completed_credits_required_for_graduation
  data_type: numeric
  description:
    Credits required for graduation for the enrollment identified by
    postsec_completed_enrollment_id.
- name: postsec_completed_account_name
  data_type: string
  description:
    Account name for the school of the enrollment identified by
    postsec_completed_enrollment_id.
- name: postsec_completed_billing_state
  data_type: string
  description:
    Billing state for the school of the enrollment identified by
    postsec_completed_enrollment_id.
- name: postsec_completed_nces_id
  data_type: string
  description:
    NCES id for the school of the enrollment identified by
    postsec_completed_enrollment_id.
- name: postsec_completed_act_composite_25_75
  data_type: string
  description:
    ACT composite 25th-75th percentile range for the school of the enrollment
    identified by postsec_completed_enrollment_id.
- name: postsec_completed_competitiveness_ranking
  data_type: string
  description:
    Competitiveness ranking for the school of the enrollment identified by
    postsec_completed_enrollment_id.
- name: postsec_completed_adjusted_6_year_minority_graduation_rate
  data_type: numeric
  description:
    Adjusted 6-year minority graduation rate for the school of the enrollment
    identified by postsec_completed_enrollment_id.
```

- [ ] **Step 3: Reparse to bind the new descriptions**

Partial parse caches unbound state; force a full parse.

```bash
VIRTUAL_ENV= DBT_PROFILES_DIR=.dbt uv run dbt parse --no-partial-parse \
  --target prod --project-dir src/dbt/kipptaf 2>&1 | tail -5
```

Expected: parses with no errors.

- [ ] **Step 4: Lint the YAML**

```bash
.trunk/tools/trunk check --force \
  src/dbt/kipptaf/models/kippadb/intermediate/properties/int_kippadb__enrollment_pivot.yml \
  2>&1 | tail -20
```

Expected: `✔ No issues` (trunk-fmt may reflow the `description` scalars — accept
the reformat).

- [ ] **Step 5: Commit**

```bash
git add src/dbt/kipptaf/models/kippadb/intermediate/properties/int_kippadb__enrollment_pivot.yml
git commit -m "docs(kipptaf): document postsec_completed_* columns

Refs #4331

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Build and verify behavior

Builds into the developer's dev dataset using prod upstreams via `--defer`; no
prod write.

- [ ] **Step 1: Define the acceptance check**

The core behavior is: for at least some students the new field returns a
`Graduated` enrollment while `ugrad_enrollment_id` returns a non-graduated one.
This query (used in Step 3) is the acceptance criterion — it must return rows:

```sql
select
    ei.student,
    ei.ugrad_enrollment_id,
    ei.ugrad_status,
    ei.postsec_completed_enrollment_id,
    ei.postsec_completed_status,
from {{ ref('int_kippadb__enrollment_pivot') }} as ei
where
    ei.postsec_completed_enrollment_id != ei.ugrad_enrollment_id
    and ei.postsec_completed_status = 'Graduated'
    and ei.ugrad_status != 'Graduated'
```

- [ ] **Step 2: Build the model into dev**

```bash
VIRTUAL_ENV= DBT_PROFILES_DIR=.dbt uv run dbt build \
  --select int_kippadb__enrollment_pivot --target dev \
  --defer --state target/prod --project-dir src/dbt/kipptaf 2>&1 | tail -25
```

Expected: model builds; the `student` uniqueness test passes (`PASS`). If the
build reports the dev relation for an upstream is missing, add
`dbt clone --select <upstream>` or ensure `--state target/prod` is fresh
(preflight parse).

- [ ] **Step 3: Run the divergence acceptance check**

```bash
VIRTUAL_ENV= DBT_PROFILES_DIR=.dbt uv run dbt show --inline "$(cat <<'SQL'
select
    ei.student,
    ei.ugrad_status,
    ei.postsec_completed_status,
from {{ ref('int_kippadb__enrollment_pivot') }} as ei
where
    ei.postsec_completed_enrollment_id != ei.ugrad_enrollment_id
    and ei.postsec_completed_status = 'Graduated'
    and ei.ugrad_status != 'Graduated'
SQL
)" --target dev --project-dir src/dbt/kipptaf --limit 20 2>&1 | tail -30
```

Expected: one or more rows where `postsec_completed_status = Graduated` and
`ugrad_status` is something else (e.g. `Attending`) — proving the
completed-first pick diverges from recency-first as intended.

- [ ] **Step 4: Confirm grain is preserved**

```bash
VIRTUAL_ENV= DBT_PROFILES_DIR=.dbt uv run dbt show --inline "$(cat <<'SQL'
select count(*) as dupes
from (
    select ei.student
    from {{ ref('int_kippadb__enrollment_pivot') }} as ei
    group by ei.student
    having count(*) > 1
)
SQL
)" --target dev --project-dir src/dbt/kipptaf --limit 5 2>&1 | tail -10
```

Expected: `dupes = 0`.

- [ ] **Step 5: Confirm null behavior aligns with is_never_enrolled**

```bash
VIRTUAL_ENV= DBT_PROFILES_DIR=.dbt uv run dbt show --inline "$(cat <<'SQL'
select
    ei.is_never_enrolled,
    countif(ei.postsec_completed_enrollment_id is null) as n_null,
    count(*) as n_total,
from {{ ref('int_kippadb__enrollment_pivot') }} as ei
group by ei.is_never_enrolled
SQL
)" --target dev --project-dir src/dbt/kipptaf --limit 5 2>&1 | tail -10
```

Expected: every `is_never_enrolled = true` row has a null
`postsec_completed_enrollment_id` (both derive from the same BA/AA/CTE pool).

- [ ] **Step 6: Push and mark the PR ready**

```bash
git push origin CGibson17/feat/claude-postsec-completed-enrollment-id
```

Then mark PR #4332 ready for review (via the GitHub UI or `gh pr ready 4332`) so
dbt Cloud CI and `claude-review` fire on the full change. Confirm dbt Cloud CI
is green before requesting human review.

---

## Self-review

- **Spec coverage:** candidate pool (Task 1 Step 1 — BA/AA/CTE structs);
  completed = Graduated (`if(status = 'Graduated', ...)`); ranking order
  (`order by is_completed desc, degree_rank desc, start_date desc`); full
  attribute set (Task 1 Steps 3-4, Task 2); grain unchanged (Task 3 Step 4);
  null when no BA/AA/CTE (Task 3 Step 5). All covered.
- **Placeholder scan:** no TBD/TODO; all code and commands are concrete.
- **Type consistency:** alias `pce`/`pcea` and column name
  `postsec_completed_enrollment_id` are used identically across the SQL joins,
  the final select, and the YAML entries; attribute `data_type`s mirror the
  verified `ugrad_*` types (`date`/`numeric`/`boolean`/`string`).
