select
    sr.employee_number,
    sr.sam_account_name,
    sr.report_to_sam_account_name,

    rt.type as form_type,
    rt.code as form_term,
    rt.name as form_long_name,
    rt.academic_year,
    rt.start_date,
    rt.lockbox_date,

    sr2.preferred_name_lastfirst as observer_name,

    od.observer_employee_number,
    od.observation_id,
    od.teacher_id,
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
    od.academic_year as od_academic_year,
    od.rn_submission,

    os.etr_tier,
    os.so_tier,
    os.overall_tier,

    coalesce(srh.preferred_name_lastfirst, sr.preferred_name_lastfirst) as teammate,
    coalesce(srh.business_unit_home_name, sr.business_unit_home_name) as entity,
    coalesce(srh.home_work_location_name, sr.home_work_location_name) as location,
    coalesce(
        srh.home_work_location_grade_band, sr.home_work_location_grade_band
    ) as grade_band,
    coalesce(srh.department_home_name, sr.department_home_name) as department,
    coalesce(
        srh.primary_grade_level_taught, sr.primary_grade_level_taught
    ) as grade_taught,
    coalesce(srh.job_title, sr.job_title) as job_title,
    coalesce(
        srh.report_to_preferred_name_lastfirst, sr.report_to_preferred_name_lastfirst
    ) as manager,
    coalesce(
        srh.worker_original_hire_date, sr.worker_original_hire_date
    ) as worker_original_hire_date,
    coalesce(srh.assignment_status, sr.assignment_status) as assignment_status,

from {{ ref("base_people__staff_roster") }} as sr
cross join {{ ref("stg_reporting__terms") }} as rt
left join
    {{ ref("int_performance_management__observation_details") }} as od
    on sr.employee_number = od.employee_number
    and rt.code = od.form_term
    and rt.academic_year = od.academic_year
    and regexp_contains(od.form_long_name, rt.name)
left join
    {{ ref("int_performance_management__overall_scores") }} as os
    on od.observation_id = os.observation_id
left join
    {{ ref("base_people__staff_roster_history") }} as srh
    on sr.employee_number = srh.employee_number
    and od.observed_at
    between date(srh.work_assignment_start_date) and date(srh.work_assignment_end_date)
left join
    {{ ref("base_people__staff_roster") }} as sr2
    on od.observer_employee_number = sr2.employee_number
where
    (sr.job_title like '%Teacher%' or sr.job_title = 'Learning Specialist')
    and sr.assignment_status not in ('Terminated', 'Deceased')
    and rt.type in ('PM', 'O3', 'WT')
