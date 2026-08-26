# Chronic absence definition alignment

Refs [#4994](https://github.com/TEAMSchools/teamster/issues/4994). Follow-up:
[#5015](https://github.com/TEAMSchools/teamster/issues/5015).

## Problem

`fct_student_attendance_daily` computes chronic absence three ways that all
diverge from the definitions KTAF is held to. Sized on AY2025.

| Defect                                                   | Effect                                                                                                                                                                                                                                      | Enrollments                                               |
| -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| `_running_ada < 0.90` excludes students at exactly 90.0% | 198 sit at exactly 90.0%; 79 are flagged only because their float average lands under `0.9`, 119 are not flagged at all                                                                                                                     | 198                                                       |
| No minimum-days threshold                                | Students with a handful of days carry an unstable rate into the metric                                                                                                                                                                      | 147 under 10 days, 116 of them counted chronically absent |
| Period-end anchor drops mid-year leavers                 | `is_latest_record` marks the last **realized** day, then the Cube measure requires `membership_value = 1` on that row. A withdrawal day usually carries `membership_value = 0`, so the enrollment leaves numerator and denominator together | 180, of which 72 are chronically absent                   |

The repo also ships two disagreeing definitions. `rpt_tableau__okrts_referrals`
uses `unweighted_ada <= 0.90`, which is correct. The mart uses `< 0.90`, which
is not.

## The authority

Every definition KTAF answers to agrees on the comparison and on including
mid-year leavers. They differ only on the minimum-days threshold.

| Authority                        | Chronically absent when                         | Minimum days                 | Leavers  |
| -------------------------------- | ----------------------------------------------- | ---------------------------- | -------- |
| New Jersey, state accountability | absent 10% or more of days in membership        | 45 at a school               | included |
| New Jersey, federal EDFacts      | absent 10% or more                              | 10                           | included |
| Florida, covering Miami          | absent 10% or more of school days at the school | 10                           | included |
| KIPP Foundation                  | ADA at or below 90.0%                           | 10 at that individual school | included |

The 10-day and 10% rule is the federal EDFacts FS195 definition, which is why
Florida and KIPP Foundation match word for word.

New Jersey's own worked example settles the boundary: a student with an absence
rate of exactly 10% "would be considered chronically absent."

## Decisions

1. A student is chronically absent when ADA is **at or below 90.0%**.
1. A student is **eligible** when they have **10 or more membership days at the
   individual school**. Not per district, and not summed across schools.
1. Mid-year leavers are **included**.
1. The eligibility flag is canonical in dbt. The underlying day count is also
   exposed, so the New Jersey 45-day variant can be a Cube measure later without
   a model change
   ([#5015](https://github.com/TEAMSchools/teamster/issues/5015)).
1. The New Jersey 45-day threshold is **out of scope**. It is a separate figure
   for a separate audience.

## Changes

### `int_students__attendance_daily`

Add a per-school membership day count. The existing `n_membership_student_year`
partitions by `academic_year` and `student_number` only, so it sums a student's
days across schools. It cannot serve this test and must not be repartitioned —
`n_absent_projected` and the New Jersey truancy rule both read it.

```sql
sum(membershipvalue) over (
    partition by academic_year, student_number, schoolid
) as n_membership_student_school_year,
```

### `fct_student_attendance_daily`

Replace the float comparison with an exact one. Flipping `<` to `<=` alone keeps
the representation problem and only moves which students it mis-sorts. Comparing
the accumulated counts avoids the division entirely.

```sql
-- was:
--   if(_running_ada is null, null, _running_ada < 0.90) as is_chronically_absent

-- now, where _cum_present and _cum_membership accumulate over the same window
-- that _running_ada uses today:
if(
    _cum_membership = 0,
    null,
    _cum_present * 10 <= _cum_membership * 9
) as is_chronically_absent,
```

Add two columns:

- `n_membership_days_school` — carried through from
  `n_membership_student_school_year`.
- `is_ca_eligible` — `n_membership_days_school >= 10`.

`ada_tier` keeps its current boundaries. They already match KIPP Foundation.

### `src/cube/model/cubes/student_attendance/student_attendance.yml`

`_count_ca_eligible_students` and `count_chronically_absent` stop deriving
eligibility from `is_latest_record` plus `membership_value = 1` and filter on
`is_ca_eligible` instead. That is what restores the 180 leavers.

Expose `n_membership_days_school` as a dimension so the 45-day measure in
[#5015](https://github.com/TEAMSchools/teamster/issues/5015) needs no dbt
change.

## Impact

AY2025 chronic absence rate moves from **24.8% to 26.2%**.

The two current defects partly cancel, which is why this has stayed invisible:
adding the students at exactly 90.0% raises the rate, and removing the
short-enrollment students lowers it. The composition changes more than the
headline does.

Published dashboards move. Socialize before shipping.

## Testing

dbt unit tests on each boundary, since every defect here is a boundary defect:

- ADA of exactly 90.0% is chronically absent.
- ADA of 90.01% is not.
- Exactly 10 membership days is eligible; 9 is not.
- Membership days count per school, so 6 days at one school plus 6 at another is
  eligible at neither.
- An enrollment whose final realized day carries `membership_value = 0` still
  appears in numerator and denominator.

Reconcile before and after against the counts recorded on
[#4994](https://github.com/TEAMSchools/teamster/issues/4994): 11,153 counted
today, 180 restored leavers, 119 students added at exactly 90.0%, 147 excluded
under 10 days.

## Out of scope

- The New Jersey 45-day figure
  ([#5015](https://github.com/TEAMSchools/teamster/issues/5015)).
- Collapsing the 30 duplicate `_year_end` / `_month_end` / `_week_end` measures
  and removing the `queryRewrite` snapshot block. That work is tracked on
  [#4994](https://github.com/TEAMSchools/teamster/issues/4994) and does not
  change any number.
- `student_enrollment_key` splitting a student who exits and re-enrolls at the
  same school into two calculations. Every authority accumulates days at the
  school across the year. Needs its own investigation.
- `ada_tier` label wording. KIPP Foundation calls Tier 1 and Tier 2 "on track"
  and Tier 3 "at risk"; the properties file calls Tier 2 "at risk" and Tier 3
  "chronic". The boundaries agree, so this is documentation only.

## Open question for KIPP Foundation

Their criteria contradict themselves. Item 1 calls Tier 1 and Tier 2 on track at
90% or above ADA. Item 8 says chronic absence is ADA at or below 90.0%. A
student at exactly 90.0% is both on track and chronically absent.
