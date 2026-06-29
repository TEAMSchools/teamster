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
            between date(ay.academic_year, w.start_month, w.start_day) and date(
                ay.academic_year + 1, w.close_month, w.close_day
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

            -- window bounds drive the period-spine join in Cube
            date(yc.academic_year, w.start_month, w.start_day) as window_start_date,
            date(yc.academic_year + 1, w.close_month, w.close_day) as window_close_date,

            if(rc.employee_number is null, true, false) as is_attrition,
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
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            ["c.employee_number", "c.academic_year", "c.attrition_type"]
        )
    }} as staff_attrition_key,

    c.staff_key,

    c.academic_year,
    c.attrition_type as `type`,
    c.window_start_date,
    c.window_close_date,
    c.as_of_exit_date,
    c.attrition_cutoff_date as cutoff_date,
    c.is_attrition,
    c.termination_effective_date,
    c.termination_reason,
    c.termination_type,
from classified as c
