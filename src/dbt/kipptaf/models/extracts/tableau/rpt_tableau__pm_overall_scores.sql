select
    s.employee_number,
    s.academic_year,
    s.term_code as pm_term,
    s.observation_score as overall_score,
    s.overall_tier,
    s.eval_date,

    sr.preferred_name_lastfirst as teammate,
    sr.business_unit_home_name as entity,
    sr.home_work_location_name as `location`,
    sr.home_work_location_grade_band as grade_band,
    sr.home_work_location_powerschool_school_id,
    sr.department_home_name as department,
    sr.job_title,
    sr.report_to_preferred_name_lastfirst as manager,
    sr.worker_original_hire_date,
    sr.assignment_status,
    sr.gender_identity,
    sr.race_ethnicity_reporting,
    sr.base_remuneration_annual_rate_amount_amount_value as annual_salary,
    sr.alumni_status,
    sr.community_professional_exp,

    ye.years_at_kipp_total as years_at_kipp,
    ye.years_teaching_total as years_teaching,

    tgl.grade_level as grade_taught,

    null as etr_score,
    null as so_score,
    null as etr_tier,
    null as so_tier,
from {{ ref("int_performance_management__observations") }} as s
inner join
    {{ ref("base_people__staff_roster_history") }} as sr
    on s.employee_number = sr.employee_number
    and s.eval_date
    between sr.work_assignment_start_date and sr.work_assignment_end_date
    and sr.primary_indicator
    and sr.assignment_status not in ('Terminated', 'Deceased')
left join
    {{ ref("int_people__years_experience") }} as ye
    on s.employee_number = ye.employee_number
    and ye.academic_year = {{ var("current_academic_year") }}
left join
    {{ ref("int_powerschool__teacher_grade_levels") }} as tgl
    on sr.powerschool_teacher_number = tgl.teachernumber
    and tgl.academic_year = {{ var("current_academic_year") }}
    and tgl.grade_level_rank = 1
