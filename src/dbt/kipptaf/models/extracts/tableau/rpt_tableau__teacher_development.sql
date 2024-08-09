select
    td.employee_number,
    td.observer_employee_number,
    td.observation_id,
    td.rubric_name,
    td.observation_score,
    td.observed_at,
    td.academic_year,
    td.observation_type,
    td.observation_type_abbreviation,
    td.observation_subject,
    td.observation_grade,
    td.row_score,
    td.measurement_name,
    td.strand_name,
    td.text_box,
    td.growth_area,
    td.glow_area,

    srh.preferred_name_lastfirst as teammate,
    srh.business_unit_home_name as entity,
    srh.home_work_location_name as `location`,
    srh.home_work_location_grade_band as grade_band,
    srh.department_home_name as department,
    srh.primary_grade_level_taught as grade_taught,
    srh.job_title,
    srh.report_to_preferred_name_lastfirst as manager,
    srh.worker_original_hire_date,
    srh.assignment_status,
    srh.sam_account_name,
    srh.report_to_sam_account_name,

    coalesce(sr.preferred_name_lastfirst, td.observer_name) as observer_name,
    if(sr.department_home_name = 'Teacher Development', 'TDT', 'NTNC') as observer_team,

    os.final_score as performance_management_final_score,
    os.final_tier as performance_management_final_tier,
from {{ ref("int_performance_management__teacher_development") }} as td
left join
    {{ ref("base_people__staff_roster_history") }} as srh
    on td.employee_number = srh.employee_number
    and cast(td.observed_at as timestamp)
    between srh.work_assignment_start_date and srh.work_assignment_end_date
left join
    {{ ref("base_people__staff_roster") }} as sr
    on td.observer_employee_number = sr.employee_number
left join
    {{ ref("int_performance_management__overall_scores") }} as os
    on td.employee_number = os.employee_number
    and td.academic_year = os.academic_year
