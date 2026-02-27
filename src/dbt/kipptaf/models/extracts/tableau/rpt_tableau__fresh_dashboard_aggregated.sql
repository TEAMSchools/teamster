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

        union all

        -- join for school/grade level
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
            and b.school = g.school
            and b.grade_level = g.grade_level
            and g.goal_granularity = 'School/Grade Level'

        union all

        -- join for school
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
            and b.school = g.school
            and g.goal_granularity = 'School'
    ),

    add_group_status_end_date as (
        select
            enrollment_academic_year,
            finalsite_id,
            grouped_status,
            grouped_status_order,
            grouped_status_start_date,

            lead(
                grouped_status_start_date,
                1,
                current_date('{{ var("local_timezone") }}')
            ) over (
                partition by finalsite_id, enrollment_academic_year
                order by grouped_status_start_date asc, grouped_status_order asc
            ) as grouped_status_end_date,

        from {{ ref("int_tableau__finalsite_student_scaffold") }}
        where grouped_status_order != 0
    ),

    days_in_status as (
        select
            enrollment_academic_year,
            finalsite_id,
            grouped_status,
            grouped_status_order,
            grouped_status_start_date,
            grouped_status_end_date,

            if(
                grouped_status_end_date = grouped_status_start_date,
                1,
                date_diff(grouped_status_end_date, grouped_status_start_date, day)
            ) as days_in_grouped_status,

        from add_group_status_end_date
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
    f.finalsite_id,
    f.powerschool_student_number,
    f.first_name,
    f.last_name,
    f.grade_level as student_grade_level,
    f.aligned_enrollment_academic_year_grade_level,
    f.grouped_status,
    f.self_contained,
    f.enrollment_academic_year_enrollment_type,
    f.is_enrolled_fdos,
    f.is_enrolled_oct01,
    f.is_enrolled_oct15,
    f.aligned_enrollment_type,

    f.grouped_status_order,
    f.grouped_status_start_date,
    null as grouped_status_end_date,
    null as days_in_grouped_status,

from scaffold as s
left join
    {{ ref("int_tableau__finalsite_student_scaffold") }} as f
    on s.academic_year = f.enrollment_academic_year
    and s.region = f.region
    and s.grade_level = f.grade_level
    and s.goal_type = f.grouped_status
    and f.latest_status = 'Waitlisted'
where s.goal_type = 'Waitlisted'

union all

-- inquiries ever
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
    f.finalsite_id,
    f.powerschool_student_number,
    f.first_name,
    f.last_name,
    f.grade_level as student_grade_level,
    f.aligned_enrollment_academic_year_grade_level,
    f.grouped_status,
    f.self_contained,
    f.enrollment_academic_year_enrollment_type,
    f.is_enrolled_fdos,
    f.is_enrolled_oct01,
    f.is_enrolled_oct15,
    f.aligned_enrollment_type,

    f.grouped_status_order,
    f.grouped_status_start_date,
    null as grouped_status_end_date,
    null as days_in_grouped_status,

from scaffold as s
left join
    {{ ref("int_tableau__finalsite_student_scaffold") }} as f
    on s.academic_year = f.enrollment_academic_year
    and s.region = f.region
    and s.grade_level = f.grade_level
    and s.goal_type = f.grouped_status
where s.goal_type = 'Inquiries'

union all

-- applications ever for region/grade level
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
    f.finalsite_id,
    f.powerschool_student_number,
    f.first_name,
    f.last_name,
    f.grade_level as student_grade_level,
    f.aligned_enrollment_academic_year_grade_level,
    f.grouped_status,
    f.self_contained,
    f.enrollment_academic_year_enrollment_type,
    f.is_enrolled_fdos,
    f.is_enrolled_oct01,
    f.is_enrolled_oct15,
    f.aligned_enrollment_type,

    d.grouped_status_order,
    d.grouped_status_start_date,
    d.grouped_status_end_date,
    d.days_in_grouped_status,

from scaffold as s
left join
    {{ ref("int_tableau__finalsite_student_scaffold") }} as f
    on s.academic_year = f.enrollment_academic_year
    and s.region = f.region
    and s.school = f.school
    and s.grade_level = f.grade_level
    and s.goal_type = f.grouped_status
left join
    days_in_status as d
    on f.enrollment_academic_year = d.enrollment_academic_year
    and f.finalsite_id = d.finalsite_id
    and f.grouped_status = d.grouped_status
where s.goal_type = 'Applications' and s.goal_granularity = 'Region/Grade Level'

union all

-- applications ever for school/grade level
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
    f.finalsite_id,
    f.powerschool_student_number,
    f.first_name,
    f.last_name,
    f.grade_level as student_grade_level,
    f.aligned_enrollment_academic_year_grade_level,
    f.grouped_status,
    f.self_contained,
    f.enrollment_academic_year_enrollment_type,
    f.is_enrolled_fdos,
    f.is_enrolled_oct01,
    f.is_enrolled_oct15,
    f.aligned_enrollment_type,

    d.grouped_status_order,
    d.grouped_status_start_date,
    d.grouped_status_end_date,
    d.days_in_grouped_status,

from scaffold as s
left join
    {{ ref("int_tableau__finalsite_student_scaffold") }} as f
    on s.academic_year = f.enrollment_academic_year
    and s.region = f.region
    and s.school = f.school
    and s.grade_level = f.grade_level
    and s.goal_type = f.grouped_status
left join
    days_in_status as d
    on f.enrollment_academic_year = d.enrollment_academic_year
    and f.finalsite_id = d.finalsite_id
    and f.grouped_status = d.grouped_status
where s.goal_type = 'Applications' and s.goal_granularity = 'School/Grade Level'

union all

-- applications ever for school
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
    f.finalsite_id,
    f.powerschool_student_number,
    f.first_name,
    f.last_name,
    f.grade_level as student_grade_level,
    f.aligned_enrollment_academic_year_grade_level,
    f.grouped_status,
    f.self_contained,
    f.enrollment_academic_year_enrollment_type,
    f.is_enrolled_fdos,
    f.is_enrolled_oct01,
    f.is_enrolled_oct15,
    f.aligned_enrollment_type,

    d.grouped_status_order,
    d.grouped_status_start_date,
    d.grouped_status_end_date,
    d.days_in_grouped_status,

from scaffold as s
left join
    {{ ref("int_tableau__finalsite_student_scaffold") }} as f
    on s.academic_year = f.enrollment_academic_year
    and s.region = f.region
    and s.school = f.school
    and s.grade_level = f.grade_level
    and s.goal_type = f.grouped_status
left join
    days_in_status as d
    on f.enrollment_academic_year = d.enrollment_academic_year
    and f.finalsite_id = d.finalsite_id
    and f.grouped_status = d.grouped_status
where s.goal_type = 'Applications' and s.goal_granularity = 'School'

union all

-- offers ever
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
    f.finalsite_id,
    f.powerschool_student_number,
    f.first_name,
    f.last_name,
    f.grade_level as student_grade_level,
    f.aligned_enrollment_academic_year_grade_level,
    f.grouped_status,
    f.self_contained,
    f.enrollment_academic_year_enrollment_type,
    f.is_enrolled_fdos,
    f.is_enrolled_oct01,
    f.is_enrolled_oct15,
    f.aligned_enrollment_type,

    d.grouped_status_order,
    d.grouped_status_start_date,
    d.grouped_status_end_date,
    d.days_in_grouped_status,

from scaffold as s
left join
    {{ ref("int_tableau__finalsite_student_scaffold") }} as f
    on s.academic_year = f.enrollment_academic_year
    and s.region = f.region
    and s.school = f.school
    and s.grade_level = f.grade_level
    and s.goal_type = f.grouped_status
left join
    days_in_status as d
    on f.enrollment_academic_year = d.enrollment_academic_year
    and f.finalsite_id = d.finalsite_id
    and f.grouped_status = d.grouped_status
where s.goal_type = 'Offers'

union all

-- currently pending offers
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
    f.finalsite_id,
    f.powerschool_student_number,
    f.first_name,
    f.last_name,
    f.grade_level as student_grade_level,
    f.aligned_enrollment_academic_year_grade_level,
    f.grouped_status,
    f.self_contained,
    f.enrollment_academic_year_enrollment_type,
    f.is_enrolled_fdos,
    f.is_enrolled_oct01,
    f.is_enrolled_oct15,
    f.aligned_enrollment_type,

    d.grouped_status_order,
    d.grouped_status_start_date,
    d.grouped_status_end_date,
    d.days_in_grouped_status,

from scaffold as s
left join
    {{ ref("int_tableau__finalsite_student_scaffold") }} as f
    on s.academic_year = f.enrollment_academic_year
    and s.region = f.region
    and s.school = f.school
    and s.grade_level = f.grade_level
    and s.goal_type = f.grouped_status
left join
    days_in_status as d
    on f.enrollment_academic_year = d.enrollment_academic_year
    and f.finalsite_id = d.finalsite_id
    and f.grouped_status = d.grouped_status
where
    s.goal_type = 'Pending Offers'
    and s.goal_name = 'Pending Offers'
    and s.academic_year = {{ var("current_academic_year") + 1 }}

union all

-- currently pending offers <= 4 days
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
    f.finalsite_id,
    f.powerschool_student_number,
    f.first_name,
    f.last_name,
    f.grade_level as student_grade_level,
    f.aligned_enrollment_academic_year_grade_level,
    f.grouped_status,
    f.self_contained,
    f.enrollment_academic_year_enrollment_type,
    f.is_enrolled_fdos,
    f.is_enrolled_oct01,
    f.is_enrolled_oct15,
    f.aligned_enrollment_type,

    d.grouped_status_order,
    d.grouped_status_start_date,
    d.grouped_status_end_date,
    d.days_in_grouped_status,

from scaffold as s
left join
    {{ ref("int_tableau__finalsite_student_scaffold") }} as f
    on s.academic_year = f.enrollment_academic_year
    and s.region = f.region
    and s.school = f.school
    and s.grade_level = f.grade_level
    and s.goal_type = f.grouped_status
left join
    days_in_status as d
    on f.enrollment_academic_year = d.enrollment_academic_year
    and f.finalsite_id = d.finalsite_id
    and f.grouped_status = d.grouped_status
where
    s.goal_type = 'Pending Offers'
    and s.goal_name = '<= 4 Days'
    and s.academic_year = {{ var("current_academic_year") + 1 }}
