with
    /* Per-employee assignment-status timeline. Sourced from
       dim_work_assignment_status (status SCD), filtered to primary,
       non-Intern assignments via inner joins to
       dim_work_assignment_primary and dim_work_assignment_jobs.
       dim_staff_work_assignments resolves item_id -> staff_key, and
       dim_staff resolves staff_key -> employee_number via staff_unique_id.

       Limitation: pre-2021 NJ Dayforce-era staff are not covered. The
       retired int_people__staff_roster_history chain unioned Dayforce
       records; the work-assignment dim family is ADP-only. Restoring
       Dayforce coverage requires unioning into the upstream dims —
       tracked at #3744. */
    teammate_history as (
        select
            wast.effective_start_date as effective_date_start,
            wast.effective_end_date as effective_date_end,
            wast.effective_start_date as assignment_status_effective_date,
            ds.staff_unique_id as employee_number,
            {{ dbt_utils.generate_surrogate_key(["ds.staff_unique_id"]) }} as staff_key,
            wast.status_code,
            wast.reason_name,

            {{
                date_to_fiscal_year(
                    date_field="wast.effective_start_date",
                    start_month=7,
                    year_source="start",
                )
            }} as academic_year,
        from {{ ref("dim_work_assignment_status") }} as wast
        inner join
            {{ ref("dim_work_assignment_primary") }} as wap
            on wast.work_assignment_key = wap.work_assignment_key
            and wast.effective_start_date <= wap.effective_end_date
            and wast.effective_end_date >= wap.effective_start_date
            and wap.is_primary_position
        inner join
            {{ ref("dim_work_assignment_jobs") }} as waj
            on wast.work_assignment_key = waj.work_assignment_key
            and wast.effective_start_date <= waj.effective_end_date
            and wast.effective_end_date >= waj.effective_start_date
            and waj.position_title != 'Intern'
        inner join
            {{ ref("dim_staff_work_assignments") }} as swa
            on wast.work_assignment_key = swa.work_assignment_key
        inner join {{ ref("dim_staff") }} as ds on swa.staff_key = ds.staff_key
    ),

    -- one row per methodology; the only thing that differs between types
    windows as (
        select *,
        from
            unnest(
                [
                    struct(
                        'foundation' as attrition_type,
                        9 as start_month,
                        1 as start_day,
                        4 as close_month,
                        30 as close_day,
                        9 as check_month,
                        1 as check_day
                    ),
                    struct('nj_compliance', 7, 1, 6, 30, 7, 1),
                    struct('recruitment', 9, 1, 8, 31, 9, 1)
                ]
            )
    ),

    academic_years as (select distinct academic_year, from teammate_history),

    -- denominator: active (non-'T') with effective span overlapping the window
    year_cohort as (
        select distinct
            w.attrition_type, ay.academic_year, th.employee_number, th.staff_key,
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
    -- genuine reason wins the rn=1 pick when both exist). The capture window
    -- extends to the return-check date, NOT the cohort window close: foundation
    -- closes 4/30 but measures attrition by the 9/1 return check, so summer
    -- (May-Aug) departures are flagged is_attrition yet their T-status date
    -- falls in the 5/1-8/31 gap. Capturing to the check date recovers them
    -- (~1k foundation rows); +1 day for nj_compliance/recruitment (negligible).
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
            between date(ay.academic_year, w.start_month, w.start_day) and date(
                ay.academic_year + 1, w.check_month, w.check_day
            )
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
            on yc.employee_number = th.employee_number
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
            yc.staff_key,
            ao.as_of_exit_date,

            -- window start (cohort membership) and the measurement-end date
            -- (the return-check date) that bounds the weekly trend axis:
            -- departures count through the check date, not the window close.
            date(yc.academic_year, w.start_month, w.start_day) as window_start_date,
            date(yc.academic_year + 1, w.check_month, w.check_day) as measure_end_date,

            if(rc.employee_number is null, true, false) as is_attrition,
            if(
                rc.employee_number is null, t.termination_effective_date, null
            ) as termination_effective_date,
            if(
                rc.employee_number is null, t.termination_reason, null
            ) as termination_reason,
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
                when termination_reason is null
                then null
                when starts_with(termination_reason, 'Resignation')
                then 'Resignation'
                when starts_with(termination_reason, 'Termination')
                then 'Termination'
                when
                    starts_with(termination_reason, 'Non-Renewal')
                    or starts_with(termination_reason, 'NonRenewal')
                then 'Non-Renewal'
                else 'Other'
            end as termination_type,
        from attrition
    ),

    -- cap the measurement end at today for in-progress windows, so the spine
    -- never runs past the current date. Computed as a plain column so the
    -- date_trunc(..., week(monday)) calls below take a simple argument.
    capped as (
        select
            *,
            least(
                measure_end_date, current_date('{{ var("local_timezone") }}')
            ) as capped_end_date,
        from classified
    ),

    -- Monday that starts each boundary week. Standalone date_trunc (not nested
    -- in date_add) so sqlfluff keeps the week(monday) datepart grammar.
    week_starts as (
        select
            *,
            -- trunk-ignore(sqlfluff/LT01): week(monday) is a datepart, not a call
            date_trunc(window_start_date, week(monday)) as first_week_start_date,
            -- trunk-ignore(sqlfluff/LT01): week(monday) is a datepart, not a call
            date_trunc(capped_end_date, week(monday)) as final_week_start_date,
        from capped
    ),

    /* Monday-anchored week-end bounds (Sunday = Monday start + 6) per cohort
       row: the first Sunday on/after window_start, and the Sunday of the week
       holding capped_end_date. Spine runs to measure_end_date (the return-check
       date), NOT window_close: foundation departures run through the summer (to
       the 9/1 check), so the trend axis must reach there. dim_dates' calendar
       week is Sun-Sat and its school week splits at term/month boundaries, so
       neither is a clean Mon-Sun grid — derive it here. */
    bounds as (
        select
            *,
            date_add(first_week_start_date, interval 6 day) as first_week_end_date,
            date_add(final_week_start_date, interval 6 day) as final_week_end_date,
        from week_starts
    ),

    expanded as (
        select
            b.employee_number,
            b.staff_key,
            b.academic_year,
            b.attrition_type,
            b.as_of_exit_date,
            b.termination_effective_date,
            b.termination_reason,
            b.termination_type,
            b.is_attrition,
            b.final_week_end_date,
            week_end_date,
        from bounds as b
        cross join
            unnest(
                generate_date_array(
                    b.first_week_end_date, b.final_week_end_date, interval 7 day
                )
            ) as week_end_date
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "e.employee_number",
                "e.academic_year",
                "e.attrition_type",
                "e.week_end_date",
            ]
        )
    }} as staff_attrition_weekly_key,

    e.staff_key,
    e.academic_year,
    e.attrition_type as `type`,
    e.week_end_date,
    e.as_of_exit_date,
    e.termination_effective_date,
    e.termination_reason,
    e.termination_type,
    e.is_attrition,

    -- cumulative as-of flag: an attritor is counted from the week their
    -- termination falls in onward. The ~0.5% of attritors with no captured
    -- termination date (intern/artifact edge cases) are parked at the final
    -- week of their window so the trend's last point reconciles with the
    -- final-outcome count.
    e.is_attrition
    and (
        (
            e.termination_effective_date is not null
            and e.termination_effective_date <= e.week_end_date
        )
        or (
            e.termination_effective_date is null
            and e.week_end_date = e.final_week_end_date
        )
    ) as is_attritor_as_of,
from expanded as e
