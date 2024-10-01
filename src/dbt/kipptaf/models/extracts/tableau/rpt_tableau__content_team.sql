select
    o.employee_number,
    o.observer_employee_number,
    o.observation_id,
    o.rubric_name,
    o.observation_score,
    o.observed_at,
    o.academic_year,
    o.observation_type,
    o.observation_type_abbreviation,
    o.observation_course as observation_subject,
    o.observation_grade,
    o.observation_notes,
    o.grows,
    o.glows,

    od.row_score,
    od.measurement_name,
    od.strand_name,
    od.measurement_dropdown_selection,
    od.measurement_comments,

    srh.preferred_name_lastfirst as teammate,
    srh.business_unit_home_name as entity,
    srh.home_work_location_name as `location`,
    srh.home_work_location_grade_band as grade_band,
    srh.department_home_name as department,
    srh.job_title,
    srh.report_to_preferred_name_lastfirst as manager,
    srh.worker_original_hire_date,
    srh.assignment_status,
    srh.sam_account_name,
    srh.report_to_sam_account_name,
    sr.preferred_name_lastfirst as observer_name,
    -- trunk-ignore(sqlfluff/LT01) 
    date_trunc(o.observed_at, week(monday)) as week_start,
from {{ ref("int_performance_management__observations") }} as o
left join
    {{ ref("int_performance_management__observation_details") }} as od
    on o.observation_id = od.observation_id
left join
    {{ ref("base_people__staff_roster_history") }} as srh
    on o.employee_number = srh.employee_number
    and o.observed_at
    between srh.work_assignment_start_date and srh.work_assignment_end_date
    and srh.assignment_status = 'Active'
left join
    {{ ref("base_people__staff_roster") }} as sr
    on o.observer_employee_number = sr.employee_number
where o.observation_type_abbreviation = 'LD' and od.row_score is not null
