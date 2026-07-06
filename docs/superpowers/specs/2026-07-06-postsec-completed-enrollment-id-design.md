# Design: `postsec_completed_enrollment_id` in `int_kippadb__enrollment_pivot`

- **Issue:** [#4331](https://github.com/TEAMSchools/teamster/issues/4331)
- **Date:** 2026-07-06
- **Model:**
  `src/dbt/kipptaf/models/kippadb/intermediate/int_kippadb__enrollment_pivot.sql`

## Problem

`int_kippadb__enrollment_pivot` exposes `ugrad_enrollment_id`, which picks a
student's single undergraduate enrollment between their best `BA` and best `AA`
track rows. Its tiebreak is **recency only** — the enrollment with the later
`start_date` wins (`BA` also wins when there is no `AA`):

```sql
case
    when ba.start_date > aa.start_date then e.ba_enrollment_id
    when aa.start_date is null then e.ba_enrollment_id
    else e.aa_enrollment_id
end as ugrad_enrollment_id
```

This means a student who **graduated** an `AA` in 2020 but is currently
**Attending** a `BA` resolves to the in-progress `BA`, not the credential they
actually earned. KIPP Forward reporting needs a field that surfaces the
**completed** post-secondary enrollment when one exists.

## Requirements (confirmed)

- **Candidate pool:** the three post-secondary track picks already resolved in
  the model — `ba_enrollment_id`, `aa_enrollment_id`, `cte_enrollment_id` (`CTE`
  = the `Vocational` pick). Excludes `HS`, `Graduate`, `Employment`. This
  matches the pool used by the model's `is_never_enrolled` flag.
- **Completed definition:** `status = 'Graduated'` only. Equivalent to the
  existing `is_graduated` flag; `Completed Coursework` and other statuses do
  **not** count.
- **Ranking** (first non-null candidate wins, in order):
  1. Completed tier — `Graduated` beats everything else.
  2. Degree level — `BA` > `AA` > `CTE`.
  3. Recency — later `start_date`.
- **Output:** the id column plus the full parallel attribute set, mirroring the
  existing `ugrad_*` block down through the final `select`.
- **Grain unchanged:** one row per `student`.

## Status domain reference

Distinct `status` values in `stg_kippadb__enrollment` (profiled 2026-07-06), for
context on why `Graduated`-only is the completed definition:

| status               | rows   | bucket            |
| -------------------- | ------ | ----------------- |
| Graduated            | 10,330 | completed         |
| Attending            | 4,379  | in progress       |
| Withdrawn            | 3,972  | withdrawn         |
| Transferred out      | 2,297  | withdrawn         |
| Did Not Enroll       | 727    | filtered upstream |
| Matriculated         | 66     | in progress       |
| Unknown              | 33     | other             |
| Leave of Absence     | 27     | in progress       |
| Completed Coursework | 17     | not counted       |
| Expelled             | 15     | withdrawn         |
| Special Circumstance | 11     | other             |
| Other                | 9      | other             |
| Deferred             | 9      | in progress       |

Only `Graduated` is treated as completed; every other retained status is a
non-completed candidate ranked by degree level then recency.

## Design

### The pick

Each of `ba` / `aa` / `cte` in the `enrollment_wide` CTE is already the best row
within its track (chosen upstream by
`rn_degree_desc = is_graduated desc, start_date desc`), and each is joined to
`stg_kippadb__enrollment`, exposing `.status` and `.start_date`. So the
completed-first pick is a compact `unnest`-of-structs scalar subquery placed
beside the existing `ugrad_enrollment_id` case:

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
                e.aa_enrollment_id, if(aa.status = 'Graduated', 1, 0), 2, aa.start_date
            ),
            struct(
                e.vocational_enrollment_id, if(cte.status = 'Graduated', 1, 0), 1, cte.start_date
            )
        ]) as cand
    where cand.enrollment_id is not null
    order by cand.is_completed desc, cand.degree_rank desc, cand.start_date desc
    limit 1
) as postsec_completed_enrollment_id
```

Notes:

- `where cand.enrollment_id is not null` drops tracks the student never enrolled
  in, so a student with no `BA`/`AA`/`CTE` yields `NULL`.
- The `order by ... limit 1` is the pick mechanism inside a scalar subquery, not
  cosmetic output ordering; the repo "no `ORDER BY`" rule does not apply. Will
  confirm lint-clean with `trunk check`.
- `start_date desc` sorts `NULL` last (BigQuery default), so a candidate with a
  known start date beats one without on the recency tiebreak.
- The literal `unnest([...])` is not a correlated join to another table, so it
  is not subject to BigQuery's correlated-subquery restriction.

### Attribute set

Add a `postsec_completed_*` block mirroring the `ugrad_*` block, keyed on the
new id. This requires:

1. Carrying `postsec_completed_enrollment_id` out of `enrollment_wide` and into
   the final `select`.
2. Two new joins at the bottom of the model, paralleling the `ug` / `uga` joins:

   ```sql
   left join
       {{ ref("stg_kippadb__enrollment") }} as pce
       on ew.postsec_completed_enrollment_id = pce.id
   left join {{ ref("stg_kippadb__account") }} as pcea on pce.school = pcea.id
   ```

3. The parallel columns (prefix `postsec_completed_`), matching the `ugrad_*`
   set exactly:

   | new column                                                   | source                                          |
   | ------------------------------------------------------------ | ----------------------------------------------- |
   | `postsec_completed_school_name`                              | `pce.name`                                      |
   | `postsec_completed_pursuing_degree_type`                     | `pce.pursuing_degree_type`                      |
   | `postsec_completed_status`                                   | `pce.status`                                    |
   | `postsec_completed_start_date`                               | `pce.start_date`                                |
   | `postsec_completed_actual_end_date`                          | `pce.actual_end_date`                           |
   | `postsec_completed_anticipated_graduation`                   | `pce.anticipated_graduation`                    |
   | `postsec_completed_account_type`                             | `pce.account_type`                              |
   | `postsec_completed_major`                                    | `pce.major`                                     |
   | `postsec_completed_major_area`                               | `pce.major_area`                                |
   | `postsec_completed_college_major_declared`                   | `pce.college_major_declared`                    |
   | `postsec_completed_date_last_verified`                       | `pce.date_last_verified`                        |
   | `postsec_completed_credits_required_for_graduation`          | `pce.of_credits_required_for_graduation`        |
   | `postsec_completed_account_name`                             | `pcea.name`                                     |
   | `postsec_completed_billing_state`                            | `pcea.billing_state`                            |
   | `postsec_completed_nces_id`                                  | `pcea.nces_id`                                  |
   | `postsec_completed_act_composite_25_75`                      | `pcea.act_composite_25_75`                      |
   | `postsec_completed_competitiveness_ranking`                  | `pcea.competitiveness_ranking`                  |
   | `postsec_completed_adjusted_6_year_minority_graduation_rate` | `pcea.adjusted_6_year_minority_graduation_rate` |

### Properties YAML

Add all new columns (`postsec_completed_enrollment_id` plus the attribute set)
to `properties/int_kippadb__enrollment_pivot.yml`, placed adjacent to the
corresponding `ugrad_*` entries, each with `data_type` and a `description`. This
intermediate model has no contract block, so the YAML is documentation only; the
`student` uniqueness test is unchanged.

## Testing / verification

- `dbt build --select int_kippadb__enrollment_pivot` (via a consuming path /
  `--target staging`) succeeds and the `student` uniqueness test still passes.
- Spot-check queries against `stg_kippadb__enrollment`:
  - A student with a graduated `AA` and an in-progress `BA` resolves
    `postsec_completed_enrollment_id` to the `AA`, while `ugrad_enrollment_id`
    still resolves to the `BA` (demonstrates the divergence).
  - A student with only in-progress enrollments resolves to the highest
    degree-level / most-recent candidate (no completed row).
  - A student with no `BA`/`AA`/`CTE` yields `NULL`.
- `trunk check` clean on the modified `.sql` and `.yml`.

## Out of scope

- No change to `ugrad_enrollment_id` or any existing column.
- No consumer wiring — `rpt_*` models opt in later as needed. This PR only adds
  the columns to the pivot and its properties YAML.
