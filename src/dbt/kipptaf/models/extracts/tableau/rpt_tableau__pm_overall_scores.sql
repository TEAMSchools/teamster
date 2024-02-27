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
    s.years_at_kipp,
    s.years_teaching,
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
from {{ ref("int_performance_management_pm_overall_scores") }} as s
inner join
    {{ ref("base_people__staff_roster_history") }} as sr
    on s.employee_number = sr.employee_number
    and s.eval_date between date(sr.work_assignment__fivetran_start) and date(
        sr.work_assignment__fivetran_end
    )
    and sr.assignment_status not in ('Terminated', 'Deceased')
    and sr.primary_indicator
