with
    teachers as (
        select
            employee_number,
            formatted_name,
            job_title,
            home_department_name,
            home_work_location_name,
            home_business_unit_name,
            home_work_location_powerschool_school_id,
            effective_date_start,
            effective_date_end,
        from {{ ref("dim_teammates") }}
        where primary_indicator and assignment_status = 'Active' and is_teacher
    ),

    /* using as date scaffold to align with Topline */
    calendar as (
        select schoolid, week_start_monday, week_end_sunday,
        from {{ ref("int_powerschool__calendar_week") }}
    ),

    grow_users as (select *, from {{ ref("stg_schoolmint_grow__users") }}),

    assignments as (
        select user_id, assignment_id, created_date_local, creator_name,
        from {{ ref("stg_schoolmint_grow__assignments") }}
    ),

    /* need to import to link assignment to microgoal name and categories */
    tags as (select *, from {{ ref("int_schoolmint_grow__assignments__tags") }}),

    microgoals as (select *, from {{ ref("int_schoolmint_grow__microgoals") }}),

    final as (
        select
            teachers.employee_number,
            teachers.formatted_name,
            teachers.job_title,
            teachers.home_department_name,
            teachers.home_work_location_name,
            teachers.home_business_unit_name,
            teachers.home_work_location_powerschool_school_id,

            calendar.week_start_monday,
            calendar.week_end_sunday,

            assignments.assignment_id,
            assignments.created_date_local,
            assignments.creator_name,

            microgoals.tag_name as goal_name,
            microgoals.strand_name,
            microgoals.bucket_name,
        from teachers
        inner join
            calendar
            on teachers.home_work_location_powerschool_school_id = calendar.schoolid
            /* if a teacher switches schools mid-week, they will be counted in the
            receiving school only for that week */
            and calendar.week_end_sunday
            between teachers.effective_date_start and teachers.effective_date_end
        inner join grow_users on teachers.employee_number = grow_users.internal_id_int
        left join
            assignments
            on grow_users.user_id = assignments.user_id
            and assignments.created_date_local
            between calendar.week_start_monday and calendar.week_end_sunday
        left join tags on assignments.assignment_id = tags.assignment_id
        left join microgoals on tags.tag_id = microgoals.tag_id

    )

select *,
from final
