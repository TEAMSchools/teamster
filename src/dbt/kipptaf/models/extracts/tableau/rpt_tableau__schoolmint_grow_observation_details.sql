select
    od.employee_number,
    od.observer_employee_number,
    od.observation_id,
    od.teacher_id,
    od.form_long_name,
    od.rubric_id,
    od.observed_at,
    od.glows,
    od.grows,
    od.score_measurement_id,
    od.row_score_value,
    od.measurement_name,
    od.text_box,
    od.score_measurement_type,
    od.score_measurement_shortname,
    od.etr_score,
    od.so_score,
    od.overall_score,
    od.form_term,
    od.form_type,
    od.academic_year,
    od.rn_submission,

    os.etr_tier,
    os.so_tier,
    os.overall_tier,

    srh.preferred_name_lastfirst as teammate,
    srh.business_unit_home_name as entity,
    srh.home_work_location_name as location,
    srh.home_work_location_grade_band as grade_band,
    srh.home_work_location_powerschool_school_id,
    srh.department_home_name as department,
    srh.primary_grade_level_taught as grade_taught,
    srh.job_title,
    srh.report_to_preferred_name_lastfirst as manager,
    srh.worker_original_hire_date,
    srh.assignment_status,
    srh.mail,
    srh.report_to_mail,
    srh.sam_account_name,

    /* past observers names */
    srh2.preferred_name_lastfirst as observer_name,

    /* current manager login for Tableau visibility of past years */
    sr.report_to_sam_account_name,

from {{ ref("int_performance_management__observation_details") }} as od
left join
    {{ ref("int_performance_management__overall_scores") }} as os
    on od.observation_id = os.observation_id
left join
    {{ ref("base_people__staff_roster_history") }} as srh
    on safe_cast(od.employee_number as int64) = safe_cast(srh.employee_number as int64)
    and od.observed_at
    between safe_cast(srh.work_assignment_start_date as date) and safe_cast(
        srh.work_assignment_end_date as date
    )
left join
    {{ ref("base_people__staff_roster_history") }} as srh2
    on od.observer_employee_number = srh2.employee_number

left join
    {{ ref("base_people__staff_roster") }} as sr
    on safe_cast(od.employee_number as int64) = safe_cast(sr.employee_number as int64)
