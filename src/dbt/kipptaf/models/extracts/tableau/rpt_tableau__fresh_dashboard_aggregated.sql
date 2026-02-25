with
    scaffold as (
        -- join for region/grade level
        select
            b.academic_year,
            b.org,
            b.region,
            b.schoolid,
            b.school,
            b.grade_level,

            g.school_level,
            g.goal_granularity,
            g.goal_type,
            g.goal_name,
            g.goal_value,

        from {{ ref("stg_google_sheets__finalsite__school_scaffold") }} as b
        inner join
            {{ ref("stg_google_sheets__finalsite__goals") }} as g
            on b.academic_year = g.enrollment_academic_year
            and b.region = g.region
            and b.grade_level = g.grade_level
            and g.goal_granularity = 'Region/Grade Level'
    )

-- currently waitlisted
select
    s.academic_year,
    s.org,
    s.region,
    s.school_level,
    s.schoolid,
    s.school,
    s.grade_level,
    s.goal_granularity,
    s.goal_type,
    s.goal_name,
    s.goal_value,

    f.aligned_enrollment_academic_year,
    f.aligned_enrollment_academic_year_display,
    f.enrollment_academic_year,
    f.enrollment_academic_year_display,
    f.finalsite_student_id,
    f.powerschool_student_number,
    f.first_name,
    f.last_name,
    f.grade_level as student_grade_level,
    f.aligned_enrollment_academic_year_grade_level,
    f.self_contained,
    f.enrollment_academic_year_enrollment_type,
    f.is_enrolled_fdos,
    f.is_enrolled_oct01,
    f.is_enrolled_oct15,
    f.aligned_enrollment_type,

from scaffold as s
left join
    {{ ref("int_tableau__finalsite_student_scaffold") }} as f
    on s.academic_year = f.enrollment_academic_year
    and s.region = f.region
    and s.grade_level = f.grade_level
    and s.goal_type = f.grouped_status
    and f.latest_status = 'Waitlisted'
where s.goal_type = 'Waitlisted' and s.goal_granularity = 'Region/Grade Level'

union all

-- currently inquiries
select
    s.academic_year,
    s.org,
    s.region,
    s.school_level,
    s.schoolid,
    s.school,
    s.grade_level,
    s.goal_granularity,
    s.goal_type,
    s.goal_name,
    s.goal_value,

    f.aligned_enrollment_academic_year,
    f.aligned_enrollment_academic_year_display,
    f.enrollment_academic_year,
    f.enrollment_academic_year_display,
    f.finalsite_student_id,
    f.powerschool_student_number,
    f.first_name,
    f.last_name,
    f.grade_level as student_grade_level,
    f.aligned_enrollment_academic_year_grade_level,
    f.self_contained,
    f.enrollment_academic_year_enrollment_type,
    f.is_enrolled_fdos,
    f.is_enrolled_oct01,
    f.is_enrolled_oct15,
    f.aligned_enrollment_type,

from scaffold as s
left join
    {{ ref("int_tableau__finalsite_student_scaffold") }} as f
    on s.academic_year = f.enrollment_academic_year
    and s.region = f.region
    and s.grade_level = f.grade_level
    and s.goal_type = f.grouped_status
where s.goal_type = 'Inquiries' and s.goal_granularity = 'Region/Grade Level'
