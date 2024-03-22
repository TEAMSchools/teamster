with
    scaffold as (
        select
            sr.employee_number,
            rt.type,
            rt.code,
            rt.name,
            rt.academic_year,
            rt.start_date,
            rt.lockbox_date,
        from {{ ref("base_people__staff_roster") }} as sr
        cross join {{ ref("stg_reporting__terms") }} as rt
        where
            sr.job_title in ('Teacher', 'Teacher in Residence', 'Learning Specialist')
            and sr.assignment_status not in ('Terminated', 'Deceased')
            and rt.type in ('PM', 'O3', 'WT')

    )

select distinct
    s.employee_number,
    s.type as form_type,
    s.code as form_term,
    s.name as form_long_name,
    s.academic_year,
    s.start_date,
    s.lockbox_date,

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
    srh.sam_account_name,
    srh.report_to_sam_account_name,

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

    /* past observers names */
    srh2.preferred_name_lastfirst as observer_name,

from scaffold as s
left join
    {{ ref("int_performance_management__observation_details") }} as od
    on s.employee_number = od.employee_number
    and s.code = od.form_term
    and s.academic_year = od.academic_year
    and regexp_contains(od.form_long_name, s.name)
left join
    {{ ref("int_performance_management__overall_scores") }} as os
    on od.observation_id = os.observation_id
left join
    {{ ref("base_people__staff_roster_history") }} as srh
    on s.employee_number = srh.employee_number
    and od.observed_at
    between safe_cast(srh.work_assignment_start_date as date) and safe_cast(
        srh.work_assignment_end_date as date
    )
left join
    {{ ref("base_people__staff_roster_history") }} as srh2
    on od.observer_employee_number = srh2.employee_number
