select
    r.aligned_enrollment_academic_year,
    r.enrollment_academic_year,
    r.finalsite_student_id,
    r.next_year_enrollment_type,
    r._dbt_source_relation,
    r.enrollment_year,
    r.enrollment_academic_year_display,
    r.sre_academic_year_start,
    r.sre_academic_year_end,
    r.org,
    r.region,
    r.latest_region,
    r.schoolid,
    r.latest_schoolid,
    r.school,
    r.latest_school,
    r.powerschool_student_number,
    r.first_name,
    r.last_name,
    r.grade_level,
    r.latest_grade_level,
    r.detailed_status,
    r.status_order,
    r.status_start_date,
    r.status_end_date,
    r.days_in_status,
    r.rn,
    r.enrollment_type_raw,
    r.latest_status,
    r.aligned_enrollment_academic_year_display,
    r.sre_aligned_academic_year_start,
    r.sre_aligned_academic_year_end,

    gs.goal_value as seat_target,

    gf.goal_value as fdos_target,
from {{ ref("int_students__finalsite_student_roster") }} as r
left join
    {{ ref("stg_google_sheets__finalsite__goals") }} as gs
    on r.aligned_enrollment_academic_year = gs.enrollment_academic_year
    and r.latest_schoolid = gs.schoolid
    and r.latest_grade_level = gs.grade_level
    and gs.goal_type = 'Enrollment'
    and gs.goal_name = 'Seat Target'
    and gs.goal_granularity = 'Grade Level'
left join
    {{ ref("stg_google_sheets__finalsite__goals") }} as gf
    on r.aligned_enrollment_academic_year = gf.enrollment_academic_year
    and r.latest_schoolid = gf.schoolid
    and r.latest_grade_level = gf.grade_level
    and gf.goal_type = 'Enrollment'
    and gf.goal_name = 'FDOS Target'
    and gf.goal_granularity = 'Grade Level'
where r.latest_status = 'Enrolled'
