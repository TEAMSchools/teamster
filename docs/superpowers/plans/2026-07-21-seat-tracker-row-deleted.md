# Seat Tracker Hard-Delete Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make hard-deleted AppSheet seat tracker rows detectable and excluded
from staffing reporting, and start capturing future deletions with a dated audit
trail — entirely in dbt, no AppSheet app or permission changes.

**Architecture:** Two mechanisms. Path 1 (does the real work) derives an
`is_deleted` flag in `int_seat_tracker__snapshot` by anti-joining the snapshot's
open rows against the live staging source; rows present in the snapshot but
absent from source are hard-deleted. Path 2 turns on `hard_deletes: new_record`
on the snapshot so future deletions also get a dated tombstone in the raw table.
Path 1 is deliberately independent of Path 2's new column, so the model changes
cannot break CI if the snapshot migration lags.

**Tech Stack:** dbt-bigquery 1.11, BigQuery, kipptaf dbt project.

## Global Constraints

- Follow `src/dbt/CLAUDE.md` SQL guide: no `QUALIFY`, no `ORDER BY`, no
  subqueries against tables/CTEs (`in (select ...)`), max 1 level function
  nesting, cast once in staging, `DISTINCT` only for grain projection
  (annotate), ON/WHERE placement rules, ST06 column ordering.
- `is_deleted` is derived by anti-join to the live staging source
  `stg_google_appsheet__seat_tracker__seats`. It must NOT reference the
  snapshot's `dbt_is_deleted` column, so the model logic works whether or not
  the Path 2 migration has run.
- Keep the original `staffing_status` untouched (28 backlog rows are `Staffed`);
  `is_deleted` is a separate boolean.
- Deleted seats have been confirmed all-intentional, so excluding them from
  fill-rate denominators is a correctness fix; fill rate rises ~1.3 pp (AY2026)
  / ~3.0 pp (AY2025). Dashboard owners must be told before rollout.
- `dim_staffing_positions` has NO inbound FK (`fct_job_candidate_applications`
  explicitly does not FK to it). It reads the raw snapshot (no log-archive
  union), so it filters deleted positions DIRECTLY via anti-join to the live
  source and drops those rows — no `is_deleted` column, no contract change. The
  centralized `is_deleted` flag lives only on `int_seat_tracker__snapshot`
  (whose log-archive union needs the `is_from_snapshot` guard) and serves
  `rpt` + `topline`.
- dbt CLI runs are local `--target dev`/`staging` only; `--target prod` runs,
  DDL, and prod snapshot runs are handed to the user.

---

## File Structure

- `src/dbt/kipptaf/snapshots/google_appsheet.yml` — add
  `hard_deletes: new_record` to `snapshot_seat_tracker__seats` (Path 2).
- `src/dbt/kipptaf/models/google/appsheet/intermediate/int_seat_tracker__snapshot.sql` +
  its properties yml — derive and expose `is_deleted` (Path 1).
- `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__seat_tracker_snapshot.sql`
  — exclude `is_deleted`.
- `src/dbt/kipptaf/models/topline/intermediate/int_topline__seats_staffed_weekly_aggregations.sql`
  — exclude `is_deleted`.
- `src/dbt/kipptaf/models/marts/dimensions/dim_staffing_positions.sql` — filter
  out deleted positions directly via anti-join to the live source (drops rows;
  no column or contract change).
- Prod migration runbook (Task 1) — executed by the user, not committed.

---

## Task 1: Enable `hard_deletes: new_record` on the snapshot + migration runbook

**Files:**

- Modify: `src/dbt/kipptaf/snapshots/google_appsheet.yml` (the
  `snapshot_seat_tracker__seats` config block)

**Interfaces:**

- Produces: a `dbt_is_deleted` meta column and dated tombstone rows in
  `kipptaf_google_appsheet.snapshot_seat_tracker__seats` going forward. No
  downstream model consumes `dbt_is_deleted` (Path 1 uses source-comparison
  instead).

- [ ] **Step 1: Add the config**

In `snapshot_seat_tracker__seats` config, add `hard_deletes: new_record`
alongside the existing keys:

```yaml
- name: snapshot_seat_tracker__seats
  relation: ref("stg_google_appsheet__seat_tracker__seats")
  config:
    schema: google_appsheet
    strategy: timestamp
    unique_key:
      - academic_year
      - staffing_model_id
    updated_at: edited_at
    dbt_valid_to_current: "'9999-12-31'"
    hard_deletes: new_record
```

- [ ] **Step 2: Parse to confirm valid config**

Run:
`uv run dbt parse --project-dir src/dbt/kipptaf --target prod --target-path target/prod`
Expected: parses with no error.

- [ ] **Step 3: Write the prod migration runbook (hand-off, do not run)**

dbt does NOT auto-migrate an existing snapshot to `hard_deletes` (see docs). The
existing table needs the `dbt_is_deleted` column before the first `new_record`
snapshot run, or results are inconsistent. Hand the user this sequence,
referencing https://docs.getdbt.com/reference/resource-configs/hard-deletes and
the snapshot-configuration-migration guide:

```text
1. Add the meta column to the prod snapshot table (BQ console / their terminal):
   ALTER TABLE `teamster-332318.kipptaf_google_appsheet.snapshot_seat_tracker__seats`
   ADD COLUMN dbt_is_deleted STRING;
   UPDATE ... SET dbt_is_deleted = 'False' WHERE dbt_is_deleted IS NULL;  (all existing rows)
2. Confirm the exact column type/default against the dbt migration guide for 1.11.
3. Run the snapshot once in prod via Dagster (asset kipptaf/google/appsheet/snapshot_seat_tracker__seats).
4. Do NOT expect this run to retro-close the ~112 backlog; backlog stays open and is handled by Path 1's is_deleted.
```

- [ ] **Step 4: Commit**

```bash
git add src/dbt/kipptaf/snapshots/google_appsheet.yml
git commit -m "feat(dbt): enable hard_deletes new_record on seat tracker snapshot"
```

---

## Task 2: Derive `is_deleted` in `int_seat_tracker__snapshot`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/google/appsheet/intermediate/int_seat_tracker__snapshot.sql`
- Modify:
  `src/dbt/kipptaf/models/google/appsheet/intermediate/properties/int_seat_tracker__snapshot.yml`

**Interfaces:**

- Produces: `is_deleted` (boolean) on `int_seat_tracker__snapshot`. TRUE when a
  snapshot-sourced seat's `(academic_year, staffing_model_id)` is absent from
  the live staging source. Always FALSE for `log_archive`-sourced rows.

- [ ] **Step 1: Add a source-key CTE and a snapshot-origin discriminator**

Add a `live_keys` CTE and tag the two `combined_snapshot` branches with an
origin flag. In `combined_snapshot`, add `true as is_from_snapshot,` to the
first (snapshot) branch's SELECT and `false as is_from_snapshot,` to the second
(`log_archive`) branch. Add this CTE:

```sql
    live_keys as (
        -- grain projection: one row per seat key; not a mask for upstream dups
        select distinct academic_year, staffing_model_id,
        from {{ ref("stg_google_appsheet__seat_tracker__seats") }}
    ),
```

- [ ] **Step 2: Left join `live_keys` and project `is_deleted`**

In the final SELECT, add the `is_deleted` column and the join (join listed after
`os1`/`os2`/`loc` per ST09):

```sql
    if(
        os1.is_from_snapshot and lk.staffing_model_id is null, true, false
    ) as is_deleted,
```

```sql
left join
    live_keys as lk
    on os1.academic_year = lk.academic_year
    and os1.staffing_model_id = lk.staffing_model_id
```

- [ ] **Step 3: Add the column to properties yml**

Add under `columns:`:

```yaml
- name: is_deleted
  data_type: boolean
  description: >-
    TRUE when this snapshot-sourced seat no longer exists in the live AppSheet
    seat tracker source (hard-deleted at source). Always FALSE for rows sourced
    from the manual log archive. Derived by anti-join to
    stg_google_appsheet__seat_tracker__seats, independent of the snapshot
    dbt_is_deleted meta column.
```

- [ ] **Step 4: Build against dev and confirm compile/build**

Run:
`uv run dbt build --select int_seat_tracker__snapshot --project-dir src/dbt/kipptaf --target dev --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod`
Expected: PASS (model builds, uniqueness test passes).

- [ ] **Step 5: Validate the flag matches the known backlog**

Run this against the dev build (BigQuery MCP or `bq`); expected ~112
currently-open deleted seats, matching the diagnostic:

```sql
select countif(is_deleted) as n_deleted, count(*) as n_rows
from `teamster-332318.<dev_schema>.int_seat_tracker__snapshot`
where valid_to = '9999-12-31'
```

Expected: `n_deleted` ≈ 112 (open-and-deleted seats).

- [ ] **Step 6: Commit**

```bash
git add src/dbt/kipptaf/models/google/appsheet/intermediate/int_seat_tracker__snapshot.sql src/dbt/kipptaf/models/google/appsheet/intermediate/properties/int_seat_tracker__snapshot.yml
git commit -m "feat(dbt): flag hard-deleted seats in int_seat_tracker__snapshot"
```

---

## Task 3: Exclude deleted seats from `rpt_tableau__seat_tracker_snapshot`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__seat_tracker_snapshot.sql`

**Interfaces:**

- Consumes: `int_seat_tracker__snapshot.is_deleted`.
- Produces: same contract columns as today (no column change); deleted seats no
  longer appear in the extract.

- [ ] **Step 1: Filter the `seats_snapshot` CTE**

```sql
    seats_snapshot as (
        select *,
        from {{ ref("int_seat_tracker__snapshot") }}
        where not is_deleted
    ),
```

- [ ] **Step 2: Build against dev**

Run:
`uv run dbt build --select rpt_tableau__seat_tracker_snapshot --project-dir src/dbt/kipptaf --target dev --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod`
Expected: PASS (contract holds — columns unchanged).

- [ ] **Step 3: Validate fill-rate direction (AY2026)**

Confirm the current-week active/staffed counts and that excluding deleted raises
the fill rate (~93.24% → ~94.51% for AY2026). Compare
`avg(open_seats)`/`avg(staffed_seats)` over `active_seats` before/after the
filter.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__seat_tracker_snapshot.sql
git commit -m "feat(dbt): exclude deleted seats from seat tracker snapshot extract"
```

---

## Task 4: Exclude deleted seats from topline staffed aggregation

**Files:**

- Modify:
  `src/dbt/kipptaf/models/topline/intermediate/int_topline__seats_staffed_weekly_aggregations.sql`

**Interfaces:**

- Consumes: `int_seat_tracker__snapshot.is_deleted`.
- Produces: `metric_aggregate_value` (weekly `avg(is_staffed)` fill rate)
  computed over non-deleted active current-year seats.

- [ ] **Step 1: Add `not is_deleted` to the `seat_tracker` CTE filter**

```sql
    seat_tracker as (
        select
            staffing_model_id, entity, adp_location, valid_from, valid_to, is_staffed,
        from {{ ref("int_seat_tracker__snapshot") }}
        /* only active, non-deleted seats for the current academic year */
        where
            academic_year = {{ var("current_academic_year") }}
            and is_active
            and not is_deleted
    ),
```

- [ ] **Step 2: Build against dev**

Run:
`uv run dbt build --select int_topline__seats_staffed_weekly_aggregations --project-dir src/dbt/kipptaf --target dev --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add src/dbt/kipptaf/models/topline/intermediate/int_topline__seats_staffed_weekly_aggregations.sql
git commit -m "feat(dbt): exclude deleted seats from topline staffed aggregation"
```

---

## Task 5: Filter deleted positions out of `dim_staffing_positions` directly

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_staffing_positions.sql`

**Interfaces:**

- Produces: `dim_staffing_positions` with deleted positions dropped (all
  versions of any seat whose key is absent from the live source). Nothing FKs
  in, so no orphans. No column or contract change (properties yml untouched).

- [ ] **Step 1: Add a `live_keys` CTE and inner-join to keep only live seats**

Restructure the model to lead with a `live_keys` CTE and inner-join it (the
inner join drops deleted seats; `distinct` keys prevent fan-out).
`staffing_model_id` is a plain column on `s`, used only in the join predicate.

```sql
with
    live_keys as (
        -- grain projection: one row per seat key; not a mask for upstream dups
        select distinct academic_year, staffing_model_id,
        from {{ ref("stg_google_appsheet__seat_tracker__seats") }}
    )

select
    ... (existing SELECT list unchanged) ...
from {{ ref("snapshot_seat_tracker__seats") }} as s
inner join
    live_keys as lk
    on s.academic_year = lk.academic_year
    and s.staffing_model_id = lk.staffing_model_id
left join
    {{ ref("int_people__location_crosswalk") }} as loc
    on s.adp_location = loc.location_name
    and not loc.location_is_pathways
    and loc.location_clean_name <> 'KIPP Whittier Elementary'
```

This also naturally excludes `new_record` tombstone rows (their keys are absent
from the live source too), with no reference to `dbt_is_deleted`.

- [ ] **Step 2: Build against dev**

Run:
`uv run dbt build --select dim_staffing_positions --project-dir src/dbt/kipptaf --target dev --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod`
Expected: PASS (`unique`/`not_null` on `staffing_position_key` hold; contract
unchanged).

- [ ] **Step 3: Validate deleted positions dropped**

Confirm the row count dropped by the deleted-seat version count and that no
surviving `staffing_model_id` is absent from the live source.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/kipptaf/models/marts/dimensions/dim_staffing_positions.sql
git commit -m "feat(dbt): drop deleted positions from dim_staffing_positions"
```

---

## Task 6: Downstream contract + Cube + exposure check

**Files:**

- Inspect: `src/cube/model/` (any staffing/seat cube),
  `src/dbt/kipptaf/models/exposures/*.yml`

- [ ] **Step 1: Grep Cube + exposures for staffing/seat usage**

Run:
`grep -rniE "staffing_position|seat_tracker" src/cube src/dbt/kipptaf/models/exposures`
Expected: confirm whether any Cube measure computes a staffing fill rate. If one
exists, add a `not is_deleted` filter there in this PR; if none, note that
`dim_staffing_positions.is_deleted` is available for future use.

- [ ] **Step 2: Confirm no other consumer selects `select *` from the changed
      models**

Run:
`grep -rln "int_seat_tracker__snapshot\|rpt_tableau__seat_tracker_snapshot" src/dbt --include=*.sql`
Expected: only the consumers already handled (Tasks 3-4). Adding `is_deleted` to
`int_seat_tracker__snapshot` is additive; confirm no contract-enforced
`select *` consumer breaks.

- [ ] **Step 3: Commit any Cube/exposure edits (if needed)**

```bash
git add src/cube src/dbt/kipptaf/models/exposures
git commit -m "feat(dbt): exclude deleted seats in staffing cube fill rate"
```

---

## Task 7: Trunk, CI, and rollout

- [ ] **Step 1: Trunk-check every changed file**

Run from inside the repo:
`/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <changed files> </dev/null`
Expected: clean (sqlfluff, yamllint, markdownlint on this plan doc).

- [ ] **Step 2: Push and open PR using the template**

Reference `Closes #4475`. In the PR body, call out: (a) the Path 2 prod
migration must run before/with deploy (Task 1 runbook), (b) fill rates rise ~1.3
pp AY2026 / ~3.0 pp AY2025 as a data-quality correction, (c) dashboard owners
notified.

- [ ] **Step 3: Sequence the prod migration**

Coordinate the Task 1 migration (add `dbt_is_deleted`, run snapshot in prod)
with the merge so the first `new_record` snapshot run has the column. Path 1
(`is_deleted`) does not depend on it, so the reporting fix lands even if the
migration is delayed.

---

## Self-Review

- **Spec coverage:** Path 1 (Task 2) + Path 2 (Task 1); exclude-everywhere
  Option B across rpt (Task 3), topline (Task 4), dim (Task 5), Cube (Task 6).
  Backfill of ~112 is automatic via Task 2's source-comparison. All covered.
- **FK safety:** Confirmed nothing FKs to `dim_staffing_positions`
  (`fct_job_candidate_applications` explicitly does not), so dropping deleted
  rows there orphans nothing.
- **CI safety:** No model references `dbt_is_deleted`; the Path 2 migration
  cannot break the model build. The `is_deleted` flag and both direct anti-joins
  derive from `stg_google_appsheet__seat_tracker__seats` only.
- **Design split:** `is_deleted` flag lives on `int_seat_tracker__snapshot`
  (log-archive-guarded) and is consumed by
  `rpt_tableau__seat_tracker_snapshot` +
  `int_topline__seats_staffed_weekly_aggregations`; `dim_staffing_positions`
  filters directly (drops rows) since it reads the raw snapshot and cannot see
  the flag.
