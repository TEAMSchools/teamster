# Point-in-Time Role-Playing Manager for Cube

**Date:** 2026-05-28 **Status:** Active **Issue:**
[#3838](https://github.com/TEAMSchools/teamster/issues/3838)

## Overview

Let the gradebook, observations, and surveys Cube cubes surface a teacher's /
observed staff's / survey subject's **manager as of the record date** via a
single date-range join plus a role-playing `staff_manager` cube
(`extends: staff`) — without denormalizing manager attributes onto `dim_staff`,
and without each consuming cube re-deriving a fragile multi-table period
intersection.

The manager-at-a-date resolution is built as a shared **Cube period-intersection
cube** (`staff_reporting_relationships`), per the cube-model spec's design
decision _"Period intersection lives in Cube SQL, not dbt."_ The only dbt change
is a **guard test** protecting the invariant the resolver's grain depends on.

This supersedes the original #3838 plan (denormalize `manager_name` /
`manager_staff_key` onto `dim_staff`), which violated the marts strict-chain
rule and was current-only.

## Decision: resolve in Cube SQL, not a dbt dim

Two strict-chain-compliant placements were considered for the
primary-assignment + reporting-relationship intersection:

- **Cube SQL** (chosen) — a shared `staff_reporting_relationships` cube whose
  `sql:` block computes the intersection, mirroring `staff_work_history`.
- **dbt dim** — a new `dim_staff_reporting_relationships` mart at
  `(staff_key, effective_start_date)` grain.

Cube SQL wins because:

1. **Convention.** The cube-model spec explicitly decides _"Period intersection
   lives in Cube SQL, not dbt … dbt handles structural transformations and
   stable business rules; Cube owns presentation-layer shaping."_
   `staff_work_history` is already built this way.
2. **Zero dbt footprint.** No new mart to maintain, contract, or rebuild.
3. **Nesting is not a differentiator.** An inline Cube cube adds no persisted
   view level; a dbt dim would have to be materialized as a `table` to match
   that. Both are safe (validated below).

Trade-off accepted: the unique-grain guarantee rests on the
**primary-exclusivity invariant** (≤1 primary assignment per staff at any
instant), which a dbt dim would enforce via its own PK uniqueness test. Cube SQL
has no such test, so we add a standalone dbt guard test (below) regardless of
placement.

## Why it isn't a single existing join

The facts carry a _person_ FK (`teacher_staff_key`, `observer_staff_key`,
`subject_staff_key` — i.e. `staff_key`), but the manager lives at
_work-assignment_ grain. "Manager at date D" is therefore a three-table,
point-in-time intersection:

```text
primary assignment @ D         (dim_work_assignment_primary,                SCD2)
  -> reporting-relationship @ D (dim_work_assignment_reporting_relationships, SCD2)
    -> manager_staff_key         (role FK -> dim_staff)
```

`staff_key` is **not unique** in `dim_staff_work_assignments` (a person can hold
multiple assignments — e.g. teacher + coach), so the **primary** assignment at
date D must be resolved before the manager. The primary flag is itself SCD2
(`dim_work_assignment_primary`), so this is a genuine period intersection, not a
filter. A bare `is_primary` predicate on a join cannot express it — the flag and
the join keys live in three separately date-versioned tables.

## Design

### Cube: `staff_reporting_relationships` (period-intersection cube)

`public: false`. The `staff_` prefix keeps it under `queryRewrite`'s
`startsWith("staff")` staff-access gate. Reference `sql:` (validated against
prod — see Validation):

```sql
SELECT
  swa.staff_key,
  rr.manager_staff_key,
  GREATEST(wap.effective_start_date, rr.effective_start_date) AS effective_start_date,
  LEAST(wap.effective_end_date,   rr.effective_end_date)      AS effective_end_date
FROM kipptaf_marts.dim_work_assignment_primary wap
JOIN kipptaf_marts.dim_staff_work_assignments swa
  ON wap.work_assignment_key = swa.work_assignment_key
  AND swa.staff_key IS NOT NULL          -- assignment must be attributable to a person
JOIN kipptaf_marts.dim_work_assignment_reporting_relationships rr
  ON rr.work_assignment_key = wap.work_assignment_key
  AND wap.effective_start_date <= rr.effective_end_date   -- period overlap
  AND wap.effective_end_date   >= rr.effective_start_date
WHERE wap.is_primary_position           -- the "hard requirement for primary"
```

- **PK dimension:**
  `CONCAT(staff_key, '|', CAST(effective_start_date AS STRING))` (Pattern 3
  convention — no surrogate spans the intersection rows).
- **Dimensions:** `staff_key`, `manager_staff_key`, `effective_start_date`
  (time), `effective_end_date`. `manager_staff_key` carries `meta: {pii: false}`
  (a surrogate, not an identifier); manager identifiers come through the
  `staff_manager` join.
- **`dates` join** is `one_to_many` (one span -> many days) if the cube is ever
  queried standalone; consumers must apply a date filter. As a join _target_
  from facts it is `many_to_one` (validated).

### Cube: `staff_manager` role alias + per-fact join

```yaml
cubes:
  - name: staff_manager # role alias - inherits all staff dimensions
    extends: staff
    public: false
```

Each staff-keyed fact joins the resolver, then the resolver (or the fact)
reaches `staff_manager` on `manager_staff_key`:

```yaml
joins:
  - name: staff_reporting_relationships
    relationship: many_to_one
    sql: >
      {staff_reporting_relationships.staff_key} = {CUBE}.teacher_staff_key AND
      CAST({CUBE}.observed_date_key AS TIMESTAMP)
          BETWEEN CAST({staff_reporting_relationships.effective_start_date} AS
      TIMESTAMP)
          AND     CAST({staff_reporting_relationships.effective_end_date}   AS
      TIMESTAMP)
```

`BETWEEN` is inclusive — these spans are end-dated to day-before-next-start, so
inclusive bounds match exactly one span (validated: zero fan-out). Manager name
= `staff_manager.full_name`, reached purely by traversal. Detail views add
`staff_manager_*` PII fields to the relevant `excludes:` list.

### dbt: primary-exclusivity guard test

A singular test (`tests/`) asserting no staff has two _distinct_ primary
assignments with overlapping effective periods — the invariant the resolver's
unique grain depends on:

```sql
with primary_spans as (
    select
        swa.staff_key,
        wap.work_assignment_key,
        wap.effective_start_date,
        wap.effective_end_date,
    from {{ ref("dim_work_assignment_primary") }} as wap
    inner join {{ ref("dim_staff_work_assignments") }} as swa
        on wap.work_assignment_key = swa.work_assignment_key
    where wap.is_primary_position and swa.staff_key is not null
)

select a.staff_key
from primary_spans as a
inner join primary_spans as b
    on a.staff_key = b.staff_key
    and a.work_assignment_key < b.work_assignment_key
    and a.effective_start_date <= b.effective_end_date
    and a.effective_end_date >= b.effective_start_date
```

`meta.dagster.ref` -> `dim_work_assignment_primary`. Default `warn` severity is
acceptable (it's a drift detector, not a build-blocker) — or `error` if we want
CI to fail hard on a future violation. Decide at implementation.

## Validation (prod `kipptaf_marts`, 2026-05-28)

The reference SQL above was run against prod:

| Check                                                  | Result                                                   |
| ------------------------------------------------------ | -------------------------------------------------------- |
| Resolver grain unique on `(staff_key, eff_start)`      | 10,387 rows = 10,387 distinct PKs, 3,231 staff           |
| Concurrent-primary fan-out                             | none                                                     |
| `manager_staff_key` NULL in intersected set            | 0                                                        |
| `fct_staff_observations` date-range join multiplicity  | 47,585 obs; **0 fan-out** (`max=1`); 47,537 one, 48 none |
| Nesting (resolver + `dim_staff` joined twice) executes | yes — all source dims are views; clean run               |

The 48 zero-match observations are dated before the teacher's primary/reporting
span begins; they correctly resolve to a NULL manager via `LEFT JOIN`.

## Scope & ownership

- **This branch / issue (dbt):** the primary-exclusivity guard test + this spec.
- **Cube-model branch** (`cristinabaldor/feat/claude-cube-model-yaml-design`):
  the `staff_reporting_relationships` and `staff_manager` cubes + the per-fact
  joins. They depend on the `staff` cube, which exists only on that branch, so
  they are authored there. This spec supersedes that spec's current-manager
  gradebook note.

## Out of scope (follow-up)

The "who can see a person's data **today**" reporting chain — the `queryRewrite`
`dim_staff.reporting_chain` segment (`src/cube/cube.js`) — is a separate
current-transitive-closure access mechanism, already scoped to the cube-infra
follow-up. Not addressed here.

## Open questions

1. **Guard-test severity** — `warn` (drift detector) vs `error` (hard CI fail).
2. **#3869 coverage** — pre-2021 NJ (Dayforce-era) manager history. Prod shows 0
   NULL managers in the primary-assignment set today, so impact is low; revisit
   if historical gradebook/observation analysis surfaces gaps.
3. **No-primary-assignment staff** (pre-hire, gaps) resolve to NULL manager for
   that date. Confirm acceptable for gradebook/observations denominators.

## Validation plan (implementation)

- dbt:
  `uv run dbt build --select dim_work_assignment_primary test_staff_primary_assignment_no_overlap`
  against `kipptaf` (worktree).
- Cube (on the cube-model branch): compile the resolver via `/sql`, confirm
  nesting and `WHERE`-free `many_to_one` behavior, spot-check a known
  manager-change teacher resolves the correct manager per observation date.
