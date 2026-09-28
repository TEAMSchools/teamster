# DeansList package rules

Issue: [#5582](https://github.com/TEAMSchools/teamster/issues/5582)

## Goal

Move DeansList rules that kipptaf recomputes over the district unions into the
shared `src/dbt/deanslist` package, so every district computes them once and the
same way. This ships before #5580 removes the package from `kippmiami`, so
Miami's frozen `kippmiami_deanslist` tables get one final rebuild with the new
columns and values.

Success looks like this:

- One `referral_tier` definition network-wide. The re-implementation in
  `rpt_tableau__okrts_referrals` is gone.
- The "exclude Social Work and Non-Behavioral" filter reads a single package
  flag, not five hand-written copies.
- Bad DeansList dates are nulled in the package, and a warn test reports new
  ones.
- `cs_hours`, the incentive-by-term rollup, and the comm-log latest-per-reason
  pick live in the package.

Out of scope: suspension aggregations
(`int_deanslist__referral_suspension_rollup` logic beyond the case fix below).

## 1. `referral_tier` and `is_behavioral_referral`

File: `src/dbt/deanslist/models/intermediate/int_deanslist__incidents.sql`.

### `referral_tier`

Match on the leading characters of `category`, not on `category_tier`.
`category_tier` is a regex that needs a `" - "` separator, and many categories
have none, so today they fall through to `Other`. First match wins:

| Tier           | Rule                                                                                                                                   |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| Social Work    | `left(category, 2) in ('SW', 'SS')` (covers `SSC` and `SSW`)                                                                           |
| Non-Behavioral | `left(category, 2) = 'TX'`, or `category like 'Documentation%'`, or `category in ('School Clinic', 'Incident Report/Accident Report')` |
| Low (Miami)    | `left(category, 2) in ('T4', 'T3')` and `project_name = 'kippmiami'`                                                                   |
| High (Miami)   | `left(category, 2) = 'T1'` and `project_name = 'kippmiami'`                                                                            |
| Low            | `left(category, 2) = 'T1'` or `left(category, 6) = 'Tier 1'`                                                                           |
| Middle         | `left(category, 2) = 'T2'` or `left(category, 6) = 'Tier 2'`                                                                           |
| High           | `left(category, 2) = 'T3'` or `left(category, 6) = 'Tier 3'`                                                                           |
| Other          | `category is not null`                                                                                                                 |
| null           | `category is null`                                                                                                                     |

Miami's inverted scale stays as it is today, so Miami's final rebuild keeps its
own scale. Once #5580 removes the package from `kippmiami`, the two Miami
branches can never match; #5580 deletes them. The okrts `Bus Referral (Miami)`
bucket (`TB`) is dropped: no incident in any region has a `TB` category.

`category_tier` stays in staging unchanged; it is a contracted column.

Measured impact against prod on 2026-09-28. No other rows change.

| Region   | From → to                              | All years | Since 2024-07-01 |
| -------- | -------------------------------------- | --------: | ---------------: |
| Newark   | Other → Non-Behavioral (Documentation) |     5,626 |            2,229 |
| Newark   | Other → High / Middle / Low            |     7,267 |                0 |
| Camden   | Other → Non-Behavioral (Documentation) |     2,137 |            1,721 |
| Paterson | Other → Low (`Tier 1`, no separator)   |       190 |              190 |
| Miami    | Other → Non-Behavioral (Documentation) |       164 |              164 |

The Paterson row is a live miscount: every current Paterson Tier 1 category has
no separator, so today all of them report as `Other`.

Downstream effect: about 4,100 Documentation incidents since July 2024 leave the
referral counts in the rollup, topline, school-metrics, and historical-
suspensions models. This is the intended correction; the school-metrics sheet
owner gets a heads-up before PR 1 merges.

### `is_behavioral_referral`

```sql
coalesce(referral_tier not in ('Social Work', 'Non-Behavioral'), false)
```

An incident with no category is `false`. That matches the four consumers that
filter with `not in` today (a null tier drops out of `not in`).
`rpt_branchingminds__behavior_incident` includes null-category incidents today
and keeps doing so with an explicit `or category is null`.

`int_deanslist__incidents__penalties` selects `i.*` from incidents, so both
columns reach the penalties model without further change.

## 2. Bad dates

DeansList data starts in the 2015-16 school year; the earliest real date in the
warehouse is 2016-08-17. Anything before 2015-07-01 is a typo (years 19 to 1029,
and 2002 for 2022).

- Package var `deanslist_min_valid_date: "2015-07-01"` in
  `src/dbt/deanslist/dbt_project.yml`, so the SQL and the test share one floor.
- `stg_deanslist__incidents`: `close_ts_date` is null below the floor.
- `int_deanslist__incidents__penalties`: `start_date` and `end_date` are null
  below the floor.
- New singular test
  `src/dbt/deanslist/tests/deanslist_dates_before_min_valid.sql`,
  `severity: warn`. It reads the raw source (`src_deanslist__incidents`, with
  `unnest(penalties)` for penalty dates), not the cleaned models, and returns
  one row per bad date with `incident_id` and the field name. It runs in each
  district that builds the package.

Why the raw source: the current kipptaf `expression_is_true` warn tests check
the output of the `sanitized` CTE, which has already nulled those rows, so they
can never fail.

Measured on 2026-09-28: 15 dates become null (Newark and Camden only). The
`fct_behavioral_incidents` and `fct_behavioral_consequences` date keys for those
rows become null; their relationships tests pass as they do today.

## 3. `cs_hours`

File: `src/dbt/deanslist/models/staging/stg_deanslist__behavior.sql`. New
contracted column, `int64`:

- the hours prefix of `behavior` (`left(behavior, length(behavior) - 5)`),
  `safe_cast` to `int64`
- only when
  `behavior_category in ('Community Service', 'Community Service Hours')`; null
  otherwise

Split the `left(...)` into the `transformations` CTE so the final select stays
at one level of nesting.

`rpt_tableau__community_service` keeps its `coalesce(..., 0)`; that is display
logic. `rpt_gsheets__community_service_upload` sums through a pivot, and `sum`
ignores nulls, so its output does not change.

## 4. `int_deanslist__behavior_incentive_by_term`

New package model
`src/dbt/deanslist/models/intermediate/int_deanslist__behavior_incentive_by_term.sql`.
The kipptaf model of the same name becomes a `union_relations` wrapper over the
four district sources, so its consumers
(`int_topline__deanslist_incentives_weekly`, `rpt_tableau__okrts_behavior`) do
not change.

Collapse the four `union all` branches into one query:

- A CTE over `stg_deanslist__behavior` filtered to the four incentive behaviors,
  with a `case` mapping each to its term type: `Earned Quarterly Incentive` →
  `Quarters`, `Earned Monthly Incentive` → `Months`, `Earned Weekly Incentive`
  and `Progress to Quarterly Incentive` → `Weeks`.
- Join `stg_deanslist__terms` on academic year, school, term type, and
  `behavior_date between start_date_date and end_date_date`.
- `incentive_type` gets the ` (Progress to Quarterly Incentive)` suffix for that
  behavior; `term_name` gets the `Q<n>` reformat for `Quarters`.

Output columns, names, and grain are unchanged. Uniqueness test on
`student_school_id, incentive_type, academic_year, term_name, school_id`.

## 5. Comm-log latest per reason

Add `is_latest_for_reason` (boolean) to the package `int_deanslist__comm_log`,
not a new model. A new model would need its own source, wrapper, and tests for
one flag.

```sql
row_number() over (
    partition by student_school_id, academic_year, reason
    order by call_date desc, call_date_time desc
) = 1
```

Computed as a ranked column in a CTE, then compared in the final select.

`int_students__attendance_interventions` and
`fct_student_attendance_interventions` replace their `dbt_utils.deduplicate`
calls with `where is_latest_for_reason`.

Two value changes, both small:

- Ties on `call_date` break on `call_date_time` instead of arbitrarily.
- `int_students__attendance_interventions` partitions today without the region.
  Per district, a `student_school_id` present in two regions keeps one row per
  region. Count the collisions in prod before building.

## Rollout

Two PRs.

**PR 1: package only.** Sections 1 through 5 in `src/dbt/deanslist`, plus the
four kipptaf source entries for `int_deanslist__behavior_incentive_by_term`
(unreferenced until PR 2). The kipptaf `sanitized` CTEs stay; cleaning twice is
harmless.

After it deploys, confirm every district, including `kippmiami`, materialized
the changed models (`mcp__dagster__get_asset_materializations`, and
`INFORMATION_SCHEMA.COLUMNS` shows `is_behavioral_referral`, `cs_hours`,
`is_latest_for_reason`). Then #5580 can merge, with the Miami `referral_tier`
branches deleted. It does not wait for PR 2.

**PR 2: kipptaf only.** With the columns in prod and in the `zz_stg` clones, dbt
Cloud CI validates it.

- `int_deanslist__behavior_incentive_by_term` becomes the union wrapper.
- Delete the `sanitized` CTEs in the incidents and penalties wrappers and their
  three dead `expression_is_true` tests.
- `rpt_tableau__okrts_referrals`: replace its tier `case` with
  `dli.referral_tier`.
- Switch the tier filters to `is_behavioral_referral`:
  `int_topline__suspension_weekly`, `rpt_gsheets__historical_suspensions`,
  `rpt_gsheets__school_metrics_extract`,
  `int_deanslist__referral_suspension_rollup` (two sites), and
  `rpt_branchingminds__behavior_incident` (with `or category is null`).
- `int_deanslist__referral_suspension_rollup`: fix `referral_tier = 'low'` to
  `'Low'` (two sites). BigQuery compares strings case-sensitively, so
  `referral_count_low` is always 0 today.
- `rpt_gsheets__community_service_upload` and `rpt_tableau__community_service`:
  read `b.cs_hours`.
- The two comm-log consumers: `where is_latest_for_reason`.

## Testing

- Unit test on `int_deanslist__incidents` `referral_tier` and
  `is_behavioral_referral`: one fixture row per branch, including a `Tier 1`
  category with no separator, a `Documentation` category, and a null category.
  It runs in the NJ districts. The Miami branches are not unit-tested, since
  #5580 deletes them; the prod diff below covers Miami's one rebuild.
- `uv run dbt build --select <changed>+` in each district's dev target.
- Re-run the tier diff query against dev and confirm exactly the row moves in
  section 1.
- Incentive model: `except distinct` both directions between the new union
  wrapper (dev) and the prod kipptaf model; both must be empty.
- PR 2: dbt Cloud CI plus the same `except distinct` check on the switched
  consumers where the value change is not expected (`cs_hours`, incentive).
