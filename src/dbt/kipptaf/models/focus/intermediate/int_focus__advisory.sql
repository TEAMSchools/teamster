-- Miami advisory, the analogue of int_powerschool__advisory. Focus carries a
-- homeroom boolean on both the schedule and the user, but it is null on every
-- row, so the homeroom course is identified by its title instead.
--
-- Elementary only: 957 of 983 ES students carry a Homeroom course for AY2026,
-- against 42 of 593 MS and 0 of 114 HS. int_focus__schedule also holds AY2026
-- alone, so there is no advisory for prior years. Both gaps are Focus
-- configuration, not modeling -- see #4868.
with
    homeroom_enrollments as (
        select
            sch.student_id,
            sch.academic_year,
            sch.schoolid,
            sch.course_period_id,
            sch.course_period_short_name,
            sch._dbt_source_project,

            usr.last_name || ', ' || usr.first_name as advisor_lastfirst,
        from {{ ref("int_focus__schedule") }} as sch
        left join
            {{ ref("int_focus__users") }} as usr
            on sch.teacher_id = usr.staff_id
            and sch._dbt_source_project = usr._dbt_source_project
        where sch.course_title like 'Homeroom%'
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="homeroom_enrollments",
                partition_by="student_id, academic_year, schoolid",
                order_by="course_period_id desc",
            )
        }}
    )

select
    academic_year,
    schoolid,
    advisor_lastfirst,
    _dbt_source_project,

    student_id as student_number,
    course_period_short_name as advisory_section_number,

    coalesce(course_period_short_name, advisor_lastfirst) as advisory_name,
from deduplicate
