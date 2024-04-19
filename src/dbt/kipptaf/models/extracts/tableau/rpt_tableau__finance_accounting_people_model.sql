with
    additional_earnings_clean as (
        select distinct
            employee_number,
            academic_year,
            pay_date,
            additional_earnings_description,
            gross_pay,
        from {{ ref("stg_adp_workforce_now__additional_earnings_report") }}
    ),

    additional_earnings as (
        select
            employee_number, academic_year, sum(gross_pay) as additional_earnings_total,
        from additional_earnings_clean
        group by employee_number, academic_year
    )

select
    hd.employee_number,
    hd.work_assignment_start_date as effective_start_date,
    hd.work_assignment_end_date as effective_end_date,
    hd.historic_position_status as position_status,
    hd.historic_legal_entity as business_unit,
    hd.historic_location as location,
    hd.historic_dept as home_department,
    hd.historic_role as job_title,
    hd.historic_salary as annual_salary,
    hd.academic_year,
    hd.adp_associate_id,
    hd.current_position_id as position_id,
    hd.current_status,
    hd.payroll_group_code as company_code,
    hd.payroll_file_number as file_number,
    hd.preferred_first_name,
    hd.preferred_last_name,
    hd.legal_first_name,
    hd.legal_last_name,
    hd.race_ethnicity_reporting as primary_race_ethnicity_reporting,
    hd.gender,
    hd.is_manager,
    hd.worker_original_hire_date as original_hire_date,
    hd.worker_rehire_date as rehire_date,
    hd.worker_termination_date as termination_date,
    hd.overall_score as most_recent_pm_score,
    hd.overall_tier as most_recent_pm_tier,

    ye.years_at_kipp_total as years_at_kipp_total_current,

    ae.additional_earnings_total as additional_earnings_summed,

    null as original_salary_upon_hire,
    null as is_currently_certified_nj_only,

    ye.years_teaching_total,

    lag(hd.historic_legal_entity, 1) over (
        partition by hd.employee_number order by hd.academic_year desc
    ) as last_year_business_unit,

    lag(hd.historic_role, 1) over (
        partition by hd.employee_number order by hd.academic_year desc
    ) as last_year_job_title,
    lag(hd.historic_salary, 1) over (
        partition by hd.employee_number order by hd.academic_year desc
    ) as last_year_salary,

    row_number() over (
        partition by hd.employee_number
        order by hd.academic_year desc, hd.historic_position_status asc
    ) as rn_curr,
from {{ ref("int_people__annual_historic_data") }} as hd
left join
    {{ ref("int_people__years_experience") }} as ye
    on hd.employee_number = ye.employee_number
    and hd.academic_year = ye.academic_year
left join
    additional_earnings as ae
    on hd.employee_number = ae.employee_number
    and hd.academic_year = ae.academic_year
