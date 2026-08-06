# Staff Attrition Cube Views — Design Spec

Issue: [#4275](https://github.com/TEAMSchools/teamster/issues/4275)

## Design revision (2026-06-29) — single weekly-grain fact

> **This section supersedes the cohort-grain + `attrition_periods` spine design
> described below.** The sections from _dbt: `fct_staff_attrition`_ onward are
> retained for the reasoning trail but no longer describe what was built. What
> shipped:

**One model, weekly grain.** `fct_staff_attrition` and the originally-planned
`attrition_periods` date-spine cube were both dropped in favor of a single
materialized table, **`fct_staff_attrition_weekly`** — one row per
`(employee × academic_year × attrition_type × Monday-Sunday week)` within the
measurement window (~1.3M rows). It carries all the cohort-level attrition logic
(the CTEs below, unchanged) plus a weekly expansion.

**Why not the spine.** The original design kept the fact at cohort grain and did
the week expansion at query time via a `one_to_many` join to an
`attrition_periods` (`extends dates`) cube. Cube activates that join on _every_
query, so final-outcome queries fanned out across the whole date spine (slow),
the `academic_year` filter bound to the spine's copy (full `dim_dates` scan),
and the ratio measure tripped Cube's fan-trap guard ("rewrite using sub query").
Per `src/cube/CLAUDE.md`, a period-intersection grain belongs in dbt, not a
query-time Cube join — so the expansion moved into the dbt mart.

**Cumulative trend mechanic.** The fact has `is_attritor_as_of` — a monotonic
flag, true from the week a departure lands onward. `count_distinct(staff_key)`
filtered to it, grouped by `week_end_date`, gives the cumulative trend;
**ungrouped it collapses to the exact final-outcome count** (verified: AY2023
foundation 1573 cohort / 316 attritors, identical to `is_attrition`). So the
rate measures are fan-safe on one table, and **no `SNAPSHOT_CUBES` anchor is
needed** — count_distinct over the monotonic flag is idempotent, unlike the
re-stamped daily-status snapshot cubes.

**Foundation window bug fixed.** Investigating "~25% of attritors have a null
termination" revealed it was **59% of _foundation_** attritors, not 25% overall
— a window bug: the `terminations` capture closed at the cohort window-close
(4/30) but attrition is measured to the 9/1 return check, so summer (esp. June
end-of-year) departures were flagged `is_attrition` with their `T`-date dropped.
The capture window now extends to the **return-check date**
(`measure_end_date`), recovering ~1014 foundation termination dates and
collapsing the genuinely-null population to **<1%** (intern/artifact edge
cases). The trend axis also runs to `measure_end_date`, so the June exodus shows
up (AY2023 foundation jumps 8.5% → 17.9% at the 6/30 week).

**Weeks are Monday-Sunday.** `dim_dates.calendar_week_*` is Sun-Sat and
`school_week_*` splits at term boundaries, so neither is a clean Mon-Sun grid;
`week_end_date` (Sunday) is derived in-model via
`date_trunc(d, week(monday)) + 6 days`.

**Residual nulls → year-end.** The <1% of attritors with no captured termination
date are parked at the final week of their window so the trend's last point
reconciles with the final-outcome count.

**`staff_work_history` cube** gained two additive backing members (`staff_key`,
`effective_end_date`) so the point-in-time join from `staff_attrition` resolves
— they existed as raw columns but not as referenceable Cube members.

**Phase 1 still aggregate-only**: the `staff_attrition_summary` view ships;
per-methodology detail views remain deferred. The summary view now also exposes
`week_end_date` for the weekly/monthly trend.

## Starting point for a new session

- Branch: `cristinabaldor/feat/claude-staff-attrition-cube-views`.
- Status: **implemented and prototype-validated** against the dev schema (V1-V7
  in the Cube dev server). Read the _Design revision_ above first — it, not the
  sections below, describes what was built.
- Key files: `fct_staff_attrition_weekly.sql` (+ properties),
  `src/cube/model/cubes/staff/staff_attrition.yml`,
  `src/cube/model/cubes/staff/staff_work_history.yml` (additive members),
  `src/cube/model/views/staff/staff_attrition_summary.yml`.

## Motivation

KTAF needs to analyze staff attrition in the Cube semantic layer: the attrition
rate for each methodology, broken down by termination reason / type and by staff
characteristics (demographics, title, location, department, worker type,
manager) **as of the time they left**, and tracked **over the course of the
year**.

The existing mart `fct_staff_attrition` is a final-outcome fact: one row per
`(employee, academic_year, attrition_type)` with a boolean `is_attrition`. Its
methodology is the one KTAF wants — it is the **canonical** definition of
attrition for the network. It has no downstream dbt model consumers today (only
the `cube.yml` exposure pre-wire), so it is safe to restructure in place.

### Canonical-engine decision

There are two independent attrition definitions in the warehouse today:

|               | **Engine A** — `fct_staff_attrition` (this spec)    | **Engine B** — `int_people__staff_attrition_details` → `int_topline__staff_retention` |
| ------------- | --------------------------------------------------- | ------------------------------------------------------------------------------------- |
| Source        | `dim_work_assignment_status` + work-assignment dims | `int_people__staff_roster_history`                                                    |
| "Left" test   | `status_code = 'T'`                                 | `assignment_status in ('Terminated','Deceased')`                                      |
| Methodologies | 3 (foundation / nj_compliance / recruitment)        | 1 (≈ recruitment window)                                                              |
| Weekly grain  | ISO/calendar weeks                                  | per-school PowerSchool weeks                                                          |

**Engine A is canonical.** Engine B (the current topline weekly retention) is
flawed and incomplete and will be migrated onto Engine A in a follow-on phase
(see _Phasing_). Validation therefore targets the **existing
`fct_staff_attrition` output**, not topline.

## Decisions

1. **Grain unchanged.** `fct_staff_attrition` stays one row per
   `(employee_number, academic_year, attrition_type)` — attrition is a step
   function (no per-day signal), so the trend is computed at query time, not
   materialized daily. **No rename**, no daily spine, no anchor flags. It gains
   `window_start_date` / `window_close_date` (trend spine), `as_of_exit_date`
   (the `staff_work_history` pin), `staff_key` (the join key to
   `staff_work_history` and the `count_distinct` measure key), and a derived
   `termination_type` column.
2. **DRY the methodology.** Collapse the 9 near-identical CTEs into a single
   `windows` definition joined once to one cohort / one returner / one
   termination CTE. Pure SQL, no Jinja codegen. **Review before implementing.**
3. **No denormalization — traverse `staff_work_history`.** All as-of-exit
   dimensional context (title, job, department, business unit, worker type, FTE,
   management flag, location/region, manager, demographics, identity) is reached
   by a **point-in-time join to the existing `staff_work_history` cube** on
   `as_of_exit_date BETWEEN effective_start AND effective_end`, exactly as
   `staff_detail` composes the staff domain. The fact carries **no**
   work-assignment attributes and **no** direct `staff` / `locations` /
   `staff_status` FKs.
4. **Trend axis via an `extends: dates` cube — no new warehouse model.** Because
   `staff_work_history` already joins `dates`, routing the trend through `dates`
   too would be a diamond. Resolve it the canonical Cube way: an
   `attrition_periods` cube that **`extends: dates`** (reuses `dim_dates`, so
   one calendar source). It is a distinct cube, so the attrition fact joins it
   for the trend while `staff_work_history` keeps joining the original `dates` —
   no diamond, nothing added to the warehouse. All measures are
   `count_distinct(staff_key)` (fan-out-safe).
5. **Termination slicing.** Keep the full `termination_reason` string and derive
   `termination_type` (`Resignation` / `Termination` / `Non-Renewal` / `Other`,
   normalizing the `NonRenewal` spelling). No separate `is_regrettable` flag
   (the regrettable signal stays embedded in the reason string for filtering).
6. **Exclude artifact reasons from the termination pick.**
   `Import Created Action`, `Upgrade Created Action`, and `Internship Ended` are
   ADP status artifacts, not departures. Exclude them from the `rn = 1`
   termination-row candidate set so a real reason wins when both exist;
   standalone artifacts fall to a null reason. Attrition **counts are
   unchanged** (≈8 reason labels move), because `is_attrition` is driven by
   non-return, not by the termination row.
7. **No `cube.js` change.** Trends group by plain `dim_dates` columns
   (`calendar_week_end_date`, the Monday-based `school_week_end_date`, or month)
   with `count_distinct` — none of which needs the snapshot guard or its
   school-week rule (that rule is for the PowerSchool _per-school in-session_
   week grid, which this cube deliberately does not use). See _cube.js_.
8. **Methodology is structurally enforced — no blended rate.** A blended rate
   across the three methodologies (different cohorts, windows, denominators) is
   meaningless, so it must be impossible, not just discouraged by a note. All
   measures live on the **one `staff_attrition` cube**: the summary exposes only
   **per-methodology measures** (`*_attrition_rate` etc., each hard-filtered on
   `type`) with no generic blendable measure. Detail views (per-methodology,
   row-locked via a static `row_level` access-policy filter) are deferred to a
   follow-on phase — Phase 1 is aggregate only.

## dbt: `fct_staff_attrition` (refactor in place)

### Grain, keys, and columns

- Grain: one row per `(employee_number, academic_year, attrition_type)`.
- PK `staff_attrition_key` (unchanged inputs) =
  `generate_surrogate_key(["employee_number", "academic_year", "attrition_type"])`.
- Columns: `staff_attrition_key` (PK); `staff_key` (=
  `generate_surrogate_key(["employee_number"])`, the join key to
  `staff_work_history` and the `count_distinct` measure key); `academic_year`;
  `type` (methodology — surfaced as `attrition_methodology` in views to avoid
  confusion with `termination_type`); `window_start_date`; `window_close_date`;
  `as_of_exit_date` (last active assignment record — the `staff_work_history`
  pin); `is_attrition`; `termination_effective_date`; `termination_reason`;
  `termination_type` (derived); `cutoff_date`.
- No FK columns for `staff` / `locations` / `staff_status` and no
  work-assignment attributes — all reached via the `staff_work_history` join in
  Cube.

### Cohort windows

| Type            | Window start  | Window close        | Return check       |
| --------------- | ------------- | ------------------- | ------------------ |
| `foundation`    | `9/1` of year | `4/30` of year `+1` | `9/1` of year `+1` |
| `nj_compliance` | `7/1` of year | `6/30` of year `+1` | `7/1` of year `+1` |
| `recruitment`   | `9/1` of year | `8/31` of year `+1` | `9/1` of year `+1` |

### DRY 3-window refactor (review target)

The `teammate_history` CTE (sources `dim_work_assignment_status` joined to
`dim_work_assignment_primary`, `dim_work_assignment_jobs`,
`dim_staff_work_assignments`, `dim_staff`) is **unchanged**. Downstream, the 9
CTEs + 3-branch `union all` collapse to a `windows` row-set, one `year_cohort`,
one `returner_cohort`, one `terminations`, and a single `attrition` join.

```sql
-- one row per methodology; the only thing that differs between types
windows as (
    select *
    from
        unnest(
            [
                struct(
                    'foundation' as attrition_type,
                    9 as start_month, 1 as start_day,
                    4 as close_month, 30 as close_day,
                    9 as check_month, 1 as check_day
                ),
                struct('nj_compliance', 7, 1, 6, 30, 7, 1),
                struct('recruitment', 9, 1, 8, 31, 9, 1)
            ]
        )
),

-- distinct academic years present in the history (replaces the vestigial
-- (employee_number, academic_year) academic_years CTE — employee_number was
-- never a join key there, only the year set was used)
academic_years as (select distinct academic_year from teammate_history),

-- denominator: active (non-'T') with effective span overlapping the window
year_cohort as (
    select distinct w.attrition_type, ay.academic_year, th.employee_number,
    from academic_years as ay
    cross join windows as w
    inner join
        teammate_history as th
        on th.effective_date_start
        <= date(ay.academic_year + 1, w.close_month, w.close_day)
        and th.effective_date_end
        >= date(ay.academic_year, w.start_month, w.start_day)
    where th.status_code != 'T'
),

-- returners: active (non-'T') on the type's return-check date
returner_cohort as (
    select distinct w.attrition_type, ay.academic_year, th.employee_number,
    from academic_years as ay
    cross join windows as w
    inner join
        teammate_history as th
        on date(ay.academic_year + 1, w.check_month, w.check_day)
        between th.effective_date_start and th.effective_date_end
    where th.status_code != 'T'
),

-- first REAL termination within the window (artifact reasons excluded so a
-- genuine reason wins the rn=1 pick when both exist)
terminations as (
    select
        w.attrition_type,
        ay.academic_year,
        th.employee_number,
        th.reason_name as termination_reason,
        th.assignment_status_effective_date as termination_effective_date,
        row_number() over (
            partition by w.attrition_type, ay.academic_year, th.employee_number
            order by th.assignment_status_effective_date asc
        ) as rn,
    from academic_years as ay
    cross join windows as w
    inner join
        teammate_history as th
        on th.assignment_status_effective_date
        between date(ay.academic_year, w.start_month, w.start_day)
        and date(ay.academic_year + 1, w.close_month, w.close_day)
    where
        th.status_code = 'T'
        and coalesce(th.reason_name, '') not in (
            'Import Created Action', 'Upgrade Created Action', 'Internship Ended'
        )
),

-- last ACTIVE primary-assignment start on/before departure: the anchor for
-- resolving as-of-exit work context. Assignment-level (aligns with
-- staff_work_history periods) and capped at the term date so a stray
-- post-termination "active" row can't win.
as_of as (
    select
        yc.attrition_type,
        yc.academic_year,
        yc.employee_number,
        max(th.effective_date_start) as as_of_exit_date,
    from year_cohort as yc
    inner join windows as w on yc.attrition_type = w.attrition_type
    left join
        terminations as t
        on yc.attrition_type = t.attrition_type
        and yc.employee_number = t.employee_number
        and yc.academic_year = t.academic_year
        and t.rn = 1
    inner join
        teammate_history as th
        on th.employee_number = yc.employee_number
        and th.status_code != 'T'
        and th.effective_date_start
        between date(yc.academic_year, w.start_month, w.start_day) and coalesce(
            t.termination_effective_date,
            date(yc.academic_year + 1, w.close_month, w.close_day)
        )
    group by yc.attrition_type, yc.academic_year, yc.employee_number
),

attrition as (
    select
        yc.attrition_type,
        yc.academic_year,
        yc.employee_number,

        if(rc.employee_number is null, true, false) as is_attrition,

        -- NEW: window bounds drive the period-spine join
        date(yc.academic_year, w.start_month, w.start_day) as window_start_date,
        date(
            yc.academic_year + 1, w.close_month, w.close_day
        ) as window_close_date,

        if(
            rc.employee_number is null, t.termination_effective_date, null
        ) as termination_effective_date,
        if(
            rc.employee_number is null, t.termination_reason, null
        ) as termination_reason,
        if(
            rc.employee_number is null,
            t.termination_effective_date,
            date(yc.academic_year + 1, w.close_month, w.close_day)
        ) as attrition_cutoff_date,

        ao.as_of_exit_date,
    from year_cohort as yc
    inner join windows as w on yc.attrition_type = w.attrition_type
    left join
        returner_cohort as rc
        on yc.attrition_type = rc.attrition_type
        and yc.employee_number = rc.employee_number
        and yc.academic_year = rc.academic_year
    left join
        terminations as t
        on yc.attrition_type = t.attrition_type
        and yc.employee_number = t.employee_number
        and yc.academic_year = t.academic_year
        and t.rn = 1
    left join
        as_of as ao
        on yc.attrition_type = ao.attrition_type
        and yc.employee_number = ao.employee_number
        and yc.academic_year = ao.academic_year
),

-- derive termination_type from the leading token of the reason string;
-- a named CTE (not inline CASE in a select list) per marts conventions
classified as (
    select
        *,
        case
            when termination_reason is null then null
            when starts_with(termination_reason, 'Resignation') then 'Resignation'
            when starts_with(termination_reason, 'Termination') then 'Termination'
            when
                starts_with(termination_reason, 'Non-Renewal')
                or starts_with(termination_reason, 'NonRenewal')
            then 'Non-Renewal'
            else 'Other'
        end as termination_type,
    from attrition
)
```

The final `select` projects the PK, `staff_key`, `academic_year`, `type`,
`window_start_date`, `window_close_date`, `as_of_exit_date`, `is_attrition`,
`termination_effective_date`, `termination_reason`, `termination_type`, and
`cutoff_date` (= `attrition_cutoff_date`).

Behavioral equivalence to the current model must be exact for completed years
**except** the ≈8 artifact-reason rows (whose reason becomes null / a real
fallback) — attrition counts are otherwise identical.

> Implementation lint notes (not design changes): sqlfluff ST09 wants the
> earlier-referenced table on the left of `on` predicates; the `unnest([...])`
> struct array and `between`/`>=` range predicates are fine; `termination_type`
> derivation belongs in the named `classified` CTE, not inline in the final
> select list. Run trunk before pushing.

### Dimensional context (traversal, not columns)

Reached in Cube via the `staff_work_history` point-in-time join, pinned on
`as_of_exit_date` (the last active assignment record — see Decisions). The
**work context** (title, job, department, business unit, worker type, FTE,
management flag, location/region, manager) is period-dependent and resolves to
that record; **demographics/identity** (`gender_identity`, `race`, `birth_date`,
names) come from `dim_staff` via `staff_work_history.staff` and are
current-state, so the anchor date does not change them.

Because the attrition cohort is itself ADP-only (built from the same
work-assignment dims that feed `staff_work_history`), **every attrition row is
guaranteed a matching work-history period**, so no row loses its context.
Coverage limitation unchanged (pre-2021 NJ Dayforce staff excluded, tracked at
[#3744](https://github.com/TEAMSchools/teamster/issues/3744)).

### Data-quality caveat (document, don't fix here)

~25% of attritors (≈1,040) are non-returners with no captured `'T'` row → null
`termination_reason` / `termination_type`. They are genuine attrition (by
non-return) and belong in an explicit **Unknown** bucket in any reason/type
slice. This is inherent to the non-return methodology, not fixable in this spec.

### Tests

- `staff_attrition_key`: `unique`, `not_null`.
- `relationships` FK to `dim_staff` (`staff_key`) — the only structural FK left;
  declare it as a `foreign_key` constraint (`warn_unsupported: false`).
- `accepted_values` on `termination_type` (`Resignation` / `Termination` /
  `Non-Renewal` / `Other`, plus null).
- Behavioral-equivalence singular test against the pre-refactor output (see
  _Validation_) is run during development, not shipped.

## Cube: `attrition_periods` (extends `dates`)

A cube-layer-only trend axis — **no dbt model**:

```yaml
cubes:
  - name: attrition_periods
    public: false
    extends: dates # reuses dim_dates + all its dimensions / TIMESTAMP casts
```

- Distinct from `dates`, so the attrition fact joins it while
  `staff_work_history` joins the original `dates` — the diamond is resolved by
  aliasing.
- Inherits all `dim_dates` dimensions, so the trend can be grouped by any period
  grid and `count_distinct(staff_key)` stays correct for each:
  `calendar_week_end_date` (ISO/Sunday weeks), `school_week_end_date` (the
  Monday-based school-week grid — the same one student snapshots use, year-round
  so summer attrition still buckets), or `date_day` at `granularity: month`. No
  invented `period_grain` column; `current_date` capping is handled in the Cube
  join.
- PowerSchool _per-school in-session_ weeks (`int_powerschool__calendar_week`,
  the topline ADA/enrollment grid) are intentionally **not** used: they have no
  summer coverage and would require binding each staffer to one school's
  calendar. Out of scope.
- One-line check at implementation: confirm `dates` declares no outward joins
  (conformed leaf) so the `extends` copy inherits nothing unwanted.

## Cube: `staff_attrition` cube (`src/cube/model/cubes/staff/`)

`public: false`, `sql_table: kipptaf_marts.fct_staff_attrition`. Two joins:

```yaml
joins:
  # as-of-exit dimensional context — the staff-domain hub cube, point-in-time.
  # All staff / locations / regions / manager / job attrs traverse from here,
  # exactly as staff_detail composes them. many_to_one (one exit period).
  - name: staff_work_history
    relationship: many_to_one
    sql: >
      {staff_work_history.staff_key} = {CUBE}.staff_key AND
      {CUBE}.as_of_exit_date
        BETWEEN {staff_work_history.effective_start_date}
        AND {staff_work_history.effective_end_date}
      AND {staff_work_history.is_primary_position} = true

  # trend axis — attrition_periods extends dates, so it's a distinct cube from
  # staff_work_history.dates. one_to_many; count_distinct(staff_key) is
  # fan-out-safe (absorbs the daily ~365/yr fan-out).
  - name: attrition_periods
    relationship: one_to_many
    sql: >
      CAST({attrition_periods.date_day} AS DATE)
        BETWEEN {CUBE}.window_start_date
        AND LEAST({CUBE}.window_close_date, CURRENT_DATE())
```

No diamond: `staff` / `locations` / `dates` are reachable only via
`staff_work_history`; the trend axis is reachable only via `attrition_periods`.

Dimensions: `attrition_methodology` (the `type` column), `termination_reason`,
`termination_type`, `termination_effective_date`, `is_attrition`,
`academic_year`. `window_*` / `as_of_exit_date` / `staff_key` back the joins and
need not be public.

Measures — **per methodology, no blendable generic** (the methodology filter is
baked into every measure, so a cross-methodology rate cannot be constructed).
For each methodology `T` in {`foundation`, `nj_compliance`, `recruitment`}, four
`count_distinct(staff_key)`-based measures (shown for `foundation`; the other
two mirror it):

- `count_cohort_foundation` — `count_distinct(staff_key)`, `filters:`
  `{CUBE}.type = 'foundation'`. Denominator.
- `count_attritors_foundation` — `count_distinct(staff_key)`, `filters:`

  ```sql
  {CUBE}.type = 'foundation'
  AND {CUBE}.is_attrition = true
  AND (
    {CUBE}.termination_effective_date IS NULL
    OR {CUBE}.termination_effective_date <= CAST({attrition_periods.date_day} AS DATE)
  )
  ```

- `attrition_rate_foundation` —
  `count_attritors_foundation / count_cohort_foundation`.
- `retention_rate_foundation` — `1 - attrition_rate_foundation`.

There is deliberately **no** generic `attrition_rate` — that omission is the
guardrail. Analysts can still chart `attrition_rate_foundation` and
`attrition_rate_recruitment` side by side (distinct series, each with its own
correct denominator) — comparison without blending.

Semantics carried by every measure:

- The `is null` arm preserves the current convention (an attritor with a null
  termination date counts for the whole window).
- Filtering on `{attrition_periods.date_day}` makes the cumulative step
  granularity-agnostic; `count_distinct` dedups the daily fan-out (a member
  becomes an attritor in the first week/month bucket containing their
  termination day), and with no period grouping it collapses to the
  final-outcome count.
- The `count_attritors_*` measures reference `attrition_periods`, so they
  activate the spine join; the `count_cohort_*` measures and per-member dims do
  not, so a detail-style query stays join-free on the spine.

## Cube: views (`src/cube/model/views/staff/`)

### `staff_attrition_summary`

Aggregate rates + trend — no direct identifiers, **no blendable measure**.
Members: the per-methodology measures (`*_attrition_rate`, `*_retention_rate`,
`count_cohort_*`, `count_attritors_*` for each of the three methodologies);
`termination_reason`, `termination_type`, `is_attrition`; work/exit breakdowns
via `staff_work_history.*` (`position_title`, `department_name`,
`business_unit_name`, `worker_type`, `is_management_position`, `status_name`);
demographics via `staff_work_history.staff` (`gender_identity`, `race`,
`is_hispanic`) as aggregate breakdowns; `staff_work_history.locations` +
`.locations.regions` descriptors; the trend axis via `attrition_periods`
(`date_day`, `calendar_week_end_date`, `school_week_end_date`, `academic_year`,
`month_name`, `month_number`). `attrition_methodology` is **not** exposed as a
free dimension — it is encoded in the measure names, so no blended denominator
is reachable. Folders group dimensions. Single `cube-access-staff-data` policy,
`includes: "*"` (aggregate demographics only; low-n suppression tracked at
[#4237](https://github.com/TEAMSchools/teamster/issues/4237)).

Usage notes in `description:`: filter to a single `academic_year`; the as-of-now
rate comes from omitting the period grouping, and the trend from grouping
`attrition_periods.calendar_week_end_date` (ISO weeks),
`attrition_periods.school_week_end_date` (school-calendar weeks, year-round), or
`attrition_periods.date_day` at `granularity: month` (monthly). Methodology no
longer needs a usage note — it is structurally enforced by the measure names.

### Per-methodology detail views (deferred)

Three row-level `staff_attrition_<type>_detail` views (one per methodology, each
row-locked via a static `row_level` access-policy filter) are out of scope for
Phase 1. When implemented they will read the single `staff_attrition` cube and
expose no `attrition_periods` members (no spine fan-out), with two-tier PII
policies mirroring `staff_detail`.

## `cube.js`

**No changes required.** No snapshot-guard machinery is needed:

- **Not** added to `SNAPSHOT_CUBES` / `SNAPSHOT_MEASURE_STEMS` /
  `SNAPSHOT_ANCHOR_OVERRIDES` — `count_distinct(staff_key)` is correct per
  period bucket without a point-in-time anchor.
- **No** `SNAPSHOT_SCHOOL_WEEK_CUBES` carve-out — the school-week grouping uses
  the plain `dim_dates.school_week_end_date` column (not the PowerSchool
  per-school in-session grid the snapshot guard's school-week rule governs), so
  it never collides with that rule.
- **No** `SNAPSHOT_ANCHOR_ONLY_CUBES` — there are no anchor rows; all
  granularities are valid because the trend is a live range join.

Staff RLS still applies automatically: the location scope filter routes through
the `staff_work_history.locations` join, and the view access policies gate
fields.

## Exposures / contracts

- Update the `cube.yml` exposure: the fact keeps its name `fct_staff_attrition`,
  so add `staff_attrition_summary` to the Cube exposure surface. No new mart
  model (`attrition_periods` extends `dates`; the `staff_attrition` cube reads
  the existing fact).
- Satisfy marts FK-constraint / uniqueness conventions on the refactored fact
  (only the `staff_key` `foreign_key` constraint remains).

## Implementation order

1. **Cube range-join prototype (de-risk first).** Validate in a Cube dev/branch
   env that: (a) the `attrition_periods` spine groups and
   `count_distinct`-dedups correctly — weekly trend monotonic, equal to the
   final-outcome count at the last in-window period; (b) no-period-grouping
   equals the final outcome; (c) the in-progress year caps at `CURRENT_DATE()`;
   (d) the `staff_work_history` point-in-time join returns exactly one exit
   period per attrition row and the detail view (no spine members) returns one
   row per member; (e) no diamond — confirm `staff` / `locations` / `dates`
   resolve only through `staff_work_history`, and the trend only through
   `attrition_periods`.
2. dbt: DRY CTE refactor (review with user first) + `termination_type` +
   artifact exclusion + window / `staff_key` / `as_of_exit_date` columns +
   tests.
3. Cube: the single `staff_attrition` cube (per-methodology measures);
   `attrition_periods` (extends `dates`); `staff_attrition_summary` view;
   `cube.yml` exposure.

## Validation plan

- Build the fact in a dev schema; verify PK uniqueness and `staff_key` FK
  population.
- **Behavioral equivalence**: the refactored fact's
  `(type, academic_year, employee_number, is_attrition, termination_effective_date)`
  rows match the current `fct_staff_attrition` exactly for completed years; the
  only reason deltas are the ≈8 artifact-reason rows.
- Via Cube: a completed-year per-methodology rate (e.g.
  `attrition_rate_foundation`, no period grouping) equals the prior
  final-outcome rate; the weekly/monthly trend is monotonically non-decreasing
  and equals the final-outcome count at the last period.
- **Do not** reconcile against topline weekly retention (Engine B is flawed; it
  migrates onto this fact in Phase 2).

## Phasing

- **Phase 1 (this spec)**: canonical `fct_staff_attrition` refactor +
  `staff_attrition` cube + `attrition_periods` (extends `dates`) +
  `staff_attrition_summary` view (aggregate only; detail views deferred).
- **Phase 2 (follow-on issue to open)**: migrate `int_topline__staff_retention`
  off Engine B onto this fact (recruitment-window mapping; ISO vs per-school
  weeks decision; attribute parity).
- **Phase 3 (follow-on issue, #3744)**: union pre-2021 Dayforce history into the
  work-assignment dims so the canonical engine covers full history.

## Alternatives considered

Brief record of approaches weighed and not chosen, for reviewers:

- **Daily / anchor-row snapshot fact** (rename to `fct_staff_attrition_daily`,
  materialize period-end rows, register in the `cube.js` snapshot guard) —
  rejected: attrition is a step function with no per-day signal, so cohort grain
  - query-time trend is leaner and scales for a future student analog.
- **Cube Tesseract** (`rolling_window: to_date` / `multi_stage` measures) for
  the cumulative trend — rejected: not enabled in this deployment (a
  deployment-wide planner switch), and a poor fit for a fixed denominator with a
  fiscal (non-calendar) window. `count_distinct` + the spine join covers it.
- **Denormalizing as-of-exit work attributes onto the fact** — rejected:
  `staff_work_history` already models them point-in-time; traverse it (as
  `staff_detail` does) instead of duplicating columns.
- **Trend joined directly to `dim_dates`** — rejected: diamond with
  `staff_work_history.dates`; aliased via `attrition_periods extends dates`.
- **Dedicated period-end-only spine model** — not chosen (kept as a fallback if
  the daily range join proves too heavy): `extends: dates` adds no warehouse
  model and supports multiple week grids.
- **`is_regrettable` flag** — dropped: the regrettable signal stays embedded in
  `termination_reason` for filtering.
- **PowerSchool per-school in-session weeks** for the trend — rejected: no
  summer coverage and awkward school-binding for staff; use the `dim_dates`
  Monday grid.
- **Anchoring exit attributes on `outcome_determination_date` or
  `termination_effective_date`** — rejected: post-termination rows and
  worker-vs-assignment date misalignment; use `as_of_exit_date` (last active
  assignment start, capped at the termination date).
- **Validating against topline retention** — rejected: Engine B is flawed;
  validate against the existing `fct_staff_attrition` output.
- **A single blendable `attrition_rate` with a "filter by methodology" usage
  note** — rejected: not foolproof; replaced by per-methodology named measures.
- **Per-methodology `extends` cubes (`WHERE type = '…'`) to lock detail** —
  rejected: keeps all measures on one cube; when detail views are built, rows
  are locked via a static `row_level` access-policy filter instead.

## Open items / risks

- **Cube range-join modeling** is the central risk — two range joins (point-in-
  time `staff_work_history`, one_to_many `attrition_periods`) + `count_distinct`
  correctness/performance + diamond avoidance. De-risked by the prototype (task
  1).
- **`staff_work_history` anchor sub-choice**: `as_of_exit_date` pins to the last
  active status period; if that period splits into multiple `staff_work_history`
  intersection sub-periods (a job/location change on the final day), confirm in
  the prototype that the date pin lands on the intended sub-period — if not,
  resolve the exact `staff_work_history` record in dbt instead.
- **Null-reason attritors (~25%)** land in an Unknown bucket for every
  reason/type slice — documented caveat, not a defect.
