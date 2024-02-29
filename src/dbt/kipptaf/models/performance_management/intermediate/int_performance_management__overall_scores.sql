with
    all_scores as (
        select
            employee_number,
            academic_year,
            form_term,
            etr_score,
            so_score,
            overall_score,
            etr_tier,
            so_tier,
            overall_tier,
            eval_date,
        from {{ ref("stg_performance_management__scores_overall_archive") }}

        union all

        select distinct
            safe_cast(internal_id as int) as employee_number,
            academic_year,
            form_term,
            etr_score,
            so_score,
            overall_score,
            etr_tier,
            so_tier,
            overall_tier,
            case
                when form_term = 'PM1'
                then date(academic_year, 10, 1)
                when form_term = 'PM2'
                then date(academic_year + 1, 1, 1)
                when form_term = 'PM3'
                then date(academic_year + 1, 3, 1)
            end as eval_date,
        from {{ ref("int_performance_management__observation_details") }}
        where form_type = 'PM' and rn_submission = 1

        union all

        select
            safe_cast(internal_id as int) as employee_number,
            academic_year,
            'PM4' as form_term,
            avg(etr_score) as etr_score,
            avg(so_score) as so_score,
            avg(overall_score) as overall_score,
            case
                when avg(etr_score) >= 3.5
                then 4
                when avg(etr_score) >= 2.745
                then 3
                when avg(etr_score) >= 1.745
                then 2
                when avg(etr_score) < 1.75
                then 1
            end as etr_tier,
            case
                when avg(so_score) >= 3.5
                then 4
                when avg(so_score) >= 2.945
                then 3
                when avg(so_score) >= 1.945
                then 2
                when avg(so_score) < 1.95
                then 1
            end as so_tier,
            case
                when avg(overall_score) >= 3.5
                then 4
                when avg(overall_score) >= 2.745
                then 3
                when avg(overall_score) >= 1.745
                then 2
                when avg(overall_score) < 1.75
                then 1
            end as overall_tier,
            date(academic_year + 1, 5, 15) as eval_date,
        from {{ ref("int_performance_management__observation_details") }}
        where
            form_type = 'PM'
            and form_term in ('PM2', 'PM3')
            and rn_submission = 1
            and overall_score is not null
        group by internal_id, academic_year
    )

select
    s.employee_number,
    s.academic_year,
    s.form_term as pm_term,
    s.etr_score,
    s.so_score,
    s.overall_score,
    s.etr_tier,
    s.so_tier,
    s.overall_tier,
    s.eval_date,

    case
        when sr.worker_termination_date is null
        then
            y.years_at_kipp_total
            - ({{ var("current_academic_year") }} - s.academic_year)
        else
            y.years_at_kipp_total - (
                {{
                    teamster_utils.date_to_fiscal_year(
                        date_field="worker_termination_date",
                        start_month=7,
                        year_source="start",
                    )
                }} - s.academic_year
            )
    end as years_at_kipp,

    case
        when sr.worker_termination_date is null
        then
            y.years_teaching_at_kipp
            + sr.years_teaching_in_njfl
            + sr.years_teaching_outside_njfl
            - ({{ var("current_academic_year") }} - s.academic_year)
        else
            y.years_teaching_at_kipp
            + sr.years_teaching_in_njfl
            + sr.years_teaching_outside_njfl
            - (
                {{
                    teamster_utils.date_to_fiscal_year(
                        date_field="worker_termination_date",
                        start_month=7,
                        year_source="start",
                    )
                }} - s.academic_year
            )
    end as years_teaching,
from all_scores as s
inner join
    {{ ref("base_people__staff_roster_history") }} as sr
    on s.employee_number = sr.employee_number
    and s.eval_date between date(sr.work_assignment__fivetran_start) and date(
        sr.work_assignment__fivetran_end
    )
    and sr.assignment_status not in ('Terminated', 'Deceased')
    and sr.primary_indicator
inner join
    {{ ref("int_people__years_experience") }} as y
    on s.employee_number = y.employee_number
where s.overall_score is not null
