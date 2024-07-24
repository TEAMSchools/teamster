select
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

    t.type as observation_type_abbreviation,
    t.code as term_code,
    t.name as term_name,
    t.academic_year,
    t.is_current,

    o.observer_employee_number,
    o.observation_id,
    o.observed_at,
    o.observation_score,
    o.observation_type,
    o.locked,
    o.grows,
    o.glows,
    o.rubric_name,
    max(
        case when od.measurement_name = 'Teacher Moves Track' then od.text_box end
    ) as teacher_moves_track,
    max(
        case when od.measurement_name = 'Student Habits Track' then od.text_box end
    ) as student_habits_track,

    sr.sam_account_name,
    sr.report_to_sam_account_name,
    sr.preferred_name_lastfirst as observer_name
from {{ ref("base_people__staff_roster_history") }} as srh
inner join
    {{ ref("stg_reporting__terms") }} as t
    on srh.business_unit_home_name = t.region
    and (
        t.start_date between date(srh.work_assignment_start_date) and date(
            srh.work_assignment_end_date
        )
        or t.end_date between date(srh.work_assignment_start_date) and date(
            srh.work_assignment_end_date
        )
    )
    and t.type = 'WT'
    and t.academic_year = {{ var("current_academic_year") }}
left join
    {{ ref("int_performance_management__observations") }} as o
    on t.type = o.observation_type_abbreviation
    and srh.employee_number = o.employee_number
    and o.observed_at between t.start_date and t.end_date
left join
    {{ ref("int_performance_management__observation_details") }} as od
    on o.observation_id = od.observation_id
left join
    {{ ref("base_people__staff_roster") }} as sr
    on od.employee_number = sr.employee_number
left join
    {{ ref("base_people__staff_roster") }} as sr2
    on od.observer_employee_number = sr2.employee_number
group by
    srh.preferred_name_lastfirst,
    srh.business_unit_home_name,
    srh.home_work_location_name,
    srh.home_work_location_grade_band,
    srh.department_home_name,
    srh.primary_grade_level_taught,
    srh.job_title,
    srh.report_to_preferred_name_lastfirst,
    srh.worker_original_hire_date,
    srh.assignment_status,
    t.type,
    t.code,
    t.name,
    t.academic_year,
    t.is_current,
    o.observer_employee_number,
    o.observation_id,
    o.observed_at,
    o.observation_score,
    o.observation_type,
    o.locked,
    o.grows,
    o.glows,
    o.rubric_name,
    sr.sam_account_name,
    sr.report_to_sam_account_name,
    sr.preferred_name_lastfirst
