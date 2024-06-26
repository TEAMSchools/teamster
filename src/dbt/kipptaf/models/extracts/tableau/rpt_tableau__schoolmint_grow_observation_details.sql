select
    od.employee_number,
    od.observer_employee_number,
    od.observation_id,
    od.rubric_name,
    od.observation_score,
    od.strand_score,
    od.glows,
    od.grows,
    od.locked,
    od.observed_at,
    od.academic_year,
    od.observation_type,
    od.observation_type_abbreviation,
    od.code,
    od.name,
    od.row_score,
    od.measurement_name,
    od.strand_name,
    od.text_box,
    od.overall_tier,

    os.final_score,
    os.final_tier,

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

    sr.sam_account_name,
    sr.report_to_sam_account_name,
    sr.preferred_name_lastfirst as observer_name,
from {{ ref("int_performance_management__observation_details") }} as od
left join
    {{ ref("int_performance_management__overall_scores") }} as os
    on od.observation_id = os.observation_id
inner join
    {{ ref("base_people__staff_roster_history") }} as srh
    on od.employee_number = srh.employee_number
    and od.observed_at
    between date(srh.work_assignment_start_date) and date(srh.work_assignment_end_date)
left join
    {{ ref("base_people__staff_roster") }} as sr
    on od.employee_number = sr.employee_number
left join
    {{ ref("base_people__staff_roster") }} as sr2
    on od.observer_employee_number = sr2.employee_number
