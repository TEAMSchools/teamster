with
    tir_previous as (
        {# Teachers who were TiR in a given academic year → 'prior_year_tir' for the next year #}
        select distinct
            employee_number,
            {{
                date_to_fiscal_year(
                    date_field="effective_date_start",
                    start_month=7,
                    year_source="start",
                )
            }} + 1 as academic_year,
            true as prior_year_tir,
        from {{ ref("int_people__staff_roster_history") }}
        where
            assignment_status = 'Active'
            and job_title in ('Teacher in Residence', 'Paraprofessional')
    ),

    recent_leave as (
        {# Teammates who were on leave within 6 weeks before a term lockbox date #}
        select distinct
            srh.employee_number, t.academic_year, t.code, true as recent_leave,
        from {{ ref("int_people__staff_roster_history") }} as srh
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as t
            on srh.assignment_status_effective_date
            between date_sub(t.lockbox_date, interval 6 week) and t.lockbox_date
            and t.type = 'PMS'
        where srh.assignment_status = 'Leave' or srh.assignment_status_lag = 'Leave'
    ),

    {#
        Deduplicate staff roster history to one primary record per (employee, date).
        Needed for pm_round_eligible fields not present on dim_staff
        (worker_hire_date_recent, work_assignment_actual_start_date).
    #}
    staff_history_dedup as (
        select
            employee_number,
            effective_date_start,
            effective_date_end,
            worker_hire_date_recent,
            work_assignment_actual_start_date,
        from {{ ref("int_people__staff_roster_history") }}
        where primary_indicator
        qualify
            row_number() over (
                partition by employee_number, effective_date_start order by position_id
            )
            = 1
    ),

    observations as (
        {#
            Deduplicate to one row per observation_id. Archive data can have
            different observed_at values per measurement row for the same
            observation; prefer the earliest non-null date.
        #}
        select
            observation_id,
            rubric_id,
            rubric_name,
            observation_score,
            glows,
            grows,
            locked,
            observed_at,
            academic_year,
            observation_type,
            observation_type_abbreviation,
            term_code,
            employee_number,
            observer_employee_number,
            overall_tier,
            observation_notes,
            etr_score,
            so_score,
        from {{ ref("int_performance_management__observation_details") }}
        qualify
            row_number() over (
                partition by observation_id order by observed_at nulls last
            )
            = 1
    )

select
    {{ dbt_utils.generate_surrogate_key(["od.observation_id"]) }} as observation_key,

    od.observation_id,
    od.rubric_id,
    od.rubric_name,
    od.observed_at,
    od.academic_year,
    od.observation_type,
    od.observation_type_abbreviation,
    od.observation_score,
    od.overall_tier,
    od.glows,
    od.grows,
    od.locked,
    od.observation_notes,
    od.etr_score,
    od.so_score,
    os.final_score,
    os.final_tier,

    true as is_published,

    ds_teacher.staff_history_key,
    ds_observer.staff_history_key as observer_staff_history_key,

    dt.terms_key,

    case
        when dt.terms_key is null
        then null
        when rl.recent_leave
        then false
        when
            od.term_code = 'PM1'
            and (
                ds_teacher.job_title = 'Teacher in Residence'
                or tir.prior_year_tir
                or ds_teacher.entity = 'KIPP Miami'
                or srh.worker_hire_date_recent
                between date(od.academic_year, 4, 1) and date_sub(
                    cast(dt.lockbox_date as date), interval 3 week
                )
            )
        then true
        when
            od.term_code in ('PM2', 'PM3')
            and srh.work_assignment_actual_start_date
            <= date_sub(cast(dt.lockbox_date as date), interval 6 week)
        then true
        else false
    end as pm_round_eligible,
from observations as od
left join
    {{ ref("dim_staff") }} as ds_teacher
    on od.employee_number = ds_teacher.employee_number
    and cast(od.observed_at as timestamp)
    between ds_teacher.marts_effective_date_start
    and ds_teacher.marts_effective_date_end
left join
    {{ ref("dim_staff") }} as ds_observer
    on od.observer_employee_number = ds_observer.employee_number
    and cast(od.observed_at as timestamp)
    between ds_observer.marts_effective_date_start
    and ds_observer.marts_effective_date_end
left join
    staff_history_dedup as srh
    on od.employee_number = srh.employee_number
    and od.observed_at between srh.effective_date_start and srh.effective_date_end
left join
    {{ ref("int_performance_management__overall_scores") }} as os
    on od.employee_number = os.employee_number
    and od.academic_year = os.academic_year
left join
    {{ ref("dim_terms") }} as dt
    on od.observation_type_abbreviation = dt.term_type
    and od.term_code = dt.term_code
    and od.observed_at
    between cast(dt.term_start_date as date) and cast(dt.term_end_date as date)
    and ds_teacher.entity = dt.entity
    and dt.term_type in ('PMS', 'PMC', 'TR')
left join
    tir_previous as tir
    on od.employee_number = tir.employee_number
    and od.academic_year = tir.academic_year
left join
    recent_leave as rl
    on od.employee_number = rl.employee_number
    and od.academic_year = rl.academic_year
    and od.term_code = rl.code
