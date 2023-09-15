with
    years as (
        select
            date_day as effective_date,
            {{
                teamster_utils.date_to_fiscal_year(
                    date_field="date_day", start_month=7, year_source="start"
                )
            }} as academic_year,
        from {{ ref("utils__date_spine") }}
        where
            extract(month from date_day) = 4
            and extract(day from date_day) = 30
            and extract(year from date_day) >= 2016
    ),

    additional_earnings as (
        select
            employee_number, academic_year, sum(gross_pay) as additional_earnings_total,
        from {{ ref("stg_adp_workforce_now__additional_earnings_report") }}
        group by employee_number, academic_year
    )

select
    eh.employee_number,
    eh.work_assignment__fivetran_start as effective_start_date,
    eh.work_assignment__fivetran_end as effective_end_date,
    eh.assignment_status as position_status,
    eh.business_unit_home_name as business_unit,
    eh.home_work_location_name as location,
    eh.department_home_name as home_department,
    eh.job_title as job_title,
    eh.base_remuneration_annual_rate_amount_amount_value as annual_salary,

    y.academic_year,

    cw.worker_id as adp_associate_id,
    cw.position_id as position_id,
    cw.assignment_status as current_status,
    cw.payroll_group_code as company_code,
    cw.payroll_file_number as file_number,
    cw.preferred_name_given_name as preferred_first_name,
    cw.preferred_name_family_name as preferred_last_name,
    cw.legal_name_given_name as legal_first_name,
    cw.legal_name_family_name as legal_last_name,
    cw.race_ethnicity_reporting as primary_race_ethnicity_reporting,
    cw.gender_identity as gender,
    cw.management_position_indicator as is_manager,
    cw.worker_original_hire_date as original_hire_date,
    cw.worker_rehire_date as rehire_date,
    cw.worker_termination_date as termination_date,

    ly.business_unit_home_name as last_year_business_unit,
    ly.job_title as last_year_job_title,

    ye.years_at_kipp_total as years_at_kipp_total_current,
    ye.years_teaching_at_kipp
    + coalesce(cw.years_teaching_in_njfl, 0)
    + coalesce(cw.years_teaching_outside_njfl, 0) as years_teaching_total_current,

    ae.additional_earnings_total as additional_earnings_summed,

    row_number() over (
        partition by cw.employee_number
        order by y.academic_year desc, eh.assignment_status asc
    ) as rn_curr,

    {# TODO: add archival salary data #}
    null as last_year_salary,
    null as original_salary_upon_hire,

    {# TODO: add teacher goals/certs data #}
    {# if year is over, displays PM4 score #}
    null as most_recent_pm_score,
    null as is_currently_certified_nj_only,
from {{ ref("base_people__staff_roster_history") }} as eh
inner join
    years as y
    on y.effective_date
    between safe_cast(eh.work_assignment__fivetran_start as date) and safe_cast(
        eh.work_assignment__fivetran_end as date
    )
inner join
    {{ ref("base_people__staff_roster") }} as cw
    on eh.employee_number = cw.employee_number
    and date_add(
        coalesce(
            cw.worker_termination_date, current_date('{{ var("local_timezone") }}')
        ),
        interval 1 year
    )
    > y.effective_date
left join
    {{ ref("base_people__staff_roster_history") }} as ly
    on eh.employee_number = ly.employee_number
    and date_sub(
        y.effective_date,
        interval 1 year
    ) between safe_cast(ly.work_assignment__fivetran_start as date) and safe_cast(
        ly.work_assignment__fivetran_end as date
    )
left join
    {{ ref("int_people__years_experience") }} as ye
    on eh.employee_number = ye.employee_number
left join
    additional_earnings as ae
    on eh.employee_number = ae.employee_number
    and y.academic_year = ae.academic_year
