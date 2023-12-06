with
    all_scores as (

        select
            employee_number,
            academic_year,
            pm_term,
            etr_score,
            so_score,
            overall_score,
            etr_tier,
            so_tier,
            overall_tier,
            case
                when pm_term = 'PM1'
                then date(academic_year, 10, 1)
                when pm_term = 'PM2'
                then date(academic_year + 1, 1, 1)
                when pm_term = 'PM3'
                then date(academic_year + 1, 3, 1)
                when pm_term = 'PM4'
                then date(academic_year + 1, 5, 15)
            end as eval_date,
        from
            {{
                source(
                    "performance_management",
                    "src_performance_management__scores_overall_archive",
                )
            }}

        union all

        select distinct
            employee_number,
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
        from {{ ref("rpt_tableau__schoolmint_grow_observation_details") }}
        where form_type = 'PM' and academic_year = 2023

        union all

        select distinct
            employee_number,
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
        from {{ ref("rpt_tableau__schoolmint_grow_observation_details") }}
        where
            form_type = 'PM'
            and overall_score is not null
            and academic_year = 2023
            and form_term in ('PM2', 'PM3')
        group by employee_number, academic_year
    )

select
    s.employee_number,
    s.academic_year,
    s.pm_term,
    s.etr_score,
    s.so_score,
    s.overall_score,
    s.etr_tier,
    s.so_tier,
    s.overall_tier,
    s.eval_date,

    sr.preferred_name_lastfirst as teammate,
    sr.business_unit_home_name as entity,
    sr.home_work_location_name as location,
    sr.home_work_location_grade_band as grade_band,
    sr.home_work_location_powerschool_school_id,
    sr.department_home_name as department,
    sr.primary_grade_level_taught as grade_taught,
    sr.job_title,
    sr.report_to_preferred_name_lastfirst as manager,
    sr.worker_original_hire_date,
    sr.assignment_status,
    sr.gender_identity,
    sr.race_ethnicity_reporting,
    sr.base_remuneration_annual_rate_amount_amount_value as annual_salary,
    sr.alumni_status,
    sr.community_professional_exp,

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
where overall_score is not null
