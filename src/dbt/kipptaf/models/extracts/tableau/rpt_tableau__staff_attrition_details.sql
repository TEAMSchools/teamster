select
    l.academic_year,
    l.employee_number,
    l.is_attrition,
    l.year_at_kipp,
    l.termination_reason,
    l.preferred_name_lastfirst,
    l.business_unit_home_name,
    l.ps_school_id,
    l.home_work_location_name,
    l.home_work_location_abbreviation,
    l.home_work_location_grade_band,
    l.department_home_name,
    l.job_title,
    l.base_remuneration_annual_rate_amount_amount_value,
    l.additional_remuneration_rate_amount_value,
    l.report_to_employee_number,
    l.report_to_preferred_name_lastfirst,
    l.gender_identity,
    l.race_ethnicity_reporting,
    l.community_grew_up,
    l.community_professional_exp,
    l.level_of_education,
    l.alumni_status,
    l.original_hire_date,
    l.termination_date,
    l.total_years_teaching,
    tgl.grade_level as primary_grade_level_taught,
    pm.final_tier as overall_tier,
    pm.final_score as overall_score,
from {{ ref("int_people__staff_attrition_details") }} as l
left join
    {{ ref("int_powerschool__teacher_grade_levels") }} as tgl
    on l.powerschool_teacher_number = tgl.teachernumber
    and l.academic_year = tgl.academic_year
    and tgl.grade_level_rank = 1
left join
    {{ ref("int_performance_management__overall_scores") }} as pm
    on l.employee_number = pm.employee_number
    and l.academic_year = pm.academic_year
