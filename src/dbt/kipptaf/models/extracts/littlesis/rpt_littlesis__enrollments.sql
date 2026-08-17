with
    staff_roster as (
        select powerschool_teacher_number, google_email,
        from {{ ref("int_people__staff_roster") }}

        union all

        select employee_id as powerschool_teacher_number, google_email,
        from {{ ref("int_people__temp_staff") }}
    ),

    powerschool_enrollments as (
        select
            sec.sections_schoolid as school_id,
            sec.sections_course_number as course_id,
            sec.sections_id as section_id,
            sec.sections_termid as term_id,
            sec.sections_section_number as section_number,
            sec.sections_external_expression as `period`,
            sec.sections_room as room,
            sec.students_student_number as student_id,

            sas.google_email as student_gsuite_email,

            sch.name as school_name,

            scw.google_email as teacher_gsuite_email,

            concat(
                sec.courses_course_name,
                ' (' || sec.sections_course_number || ') - ',
                sec.sections_section_number || ' - ',
                '{{ var("current_academic_year") }}-{{ var("current_fiscal_year") }}'
            ) as class_name,
        from {{ ref("base_powerschool__course_enrollments") }} as sec
        inner join
            {{ ref("stg_people__student_logins") }} as sas
            on sec.students_student_number = sas.student_number
        inner join
            {{ ref("stg_powerschool__schools") }} as sch
            on sec.sections_schoolid = sch.school_number
            and sec._dbt_source_project = sch._dbt_source_project
        inner join
            staff_roster as scw on sec.teachernumber = scw.powerschool_teacher_number
        where
            sec.cc_academic_year = {{ var("current_academic_year") }}
            and not sec.is_dropped_section
            and sec.courses_credittype != 'LOG'
    ),

    /*
       Miami is on Focus, not PowerSchool, so it contributes no rows to the
       branch above. Focus schedules carry the same grain (one row per student
       per course period) and are keyed on the prefixed student id that
       stg_people__student_logins already assigns Google accounts to.
    */
    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    focus_schedule_raw as (
        select
            academic_year,
            schoolid,
            student_id,
            course_period_id,
            marking_period_id,
            course_period_short_name,
            room,
            teacher_id,
            course_title,

            cast(course_id as string) as course_id,
        from {{ ref("int_focus__schedule") }}
        where academic_year = {{ var("current_academic_year") }}
    ),

    -- Focus schedules some students into the same course period twice: once
    -- as a full-year row (marking_period_id null, the FY sentinel already
    -- normalized upstream) and once term-specific. Keep the full-year row
    -- where both exist so Little SIS gets one enrollment per section.
    focus_schedule as (
        {{
            dbt_utils.deduplicate(
                relation="focus_schedule_raw",
                partition_by="student_id, course_period_id",
                order_by="(marking_period_id is not null) asc",
            )
        }}
    ),

    /*
       Full-year course periods carry Focus's marking_period_id = 0 sentinel,
       which int_focus__schedule normalizes to null. Little SIS gets the
       school's year-level marking period for those instead of a null term, so
       every row carries a term the way the PowerSchool branch does.
    */
    focus_year_terms as (
        select syear, school_id, marking_period_id,
        from {{ ref("stg_focus__marking_periods") }}
        where type = 'year'
    ),

    focus_users as (
        select
            staff_id,

            safe_cast(staff_number_identifier_local as int64) as employee_number,
        from {{ ref("int_focus__users") }}
    ),

    focus_enrollments as (
        select
            sch.schoolid as school_id,
            sch.course_id,
            sch.course_period_id as section_id,
            sch.course_period_short_name as section_number,
            sch.room,
            sch.student_id,

            sas.google_email as student_gsuite_email,

            fsc.title as school_name,

            scw.google_email as teacher_gsuite_email,

            -- Focus stores the bell-schedule slot as a period_id whose label
            -- lives in school_periods, which is not exposed at kipptaf yet
            cast(null as string) as `period`,

            coalesce(sch.marking_period_id, fyt.marking_period_id) as term_id,

            concat(
                sch.course_title,
                ' (' || sch.course_id || ') - ',
                sch.course_period_short_name || ' - ',
                '{{ var("current_academic_year") }}-{{ var("current_fiscal_year") }}'
            ) as class_name,
        from focus_schedule as sch
        inner join
            {{ ref("stg_people__student_logins") }} as sas
            on sch.student_id = sas.student_number
        inner join {{ ref("int_focus__schools") }} as fsc on sch.schoolid = fsc.id
        inner join focus_users as fu on sch.teacher_id = fu.staff_id
        inner join
            {{ ref("int_people__staff_roster") }} as scw
            on fu.employee_number = scw.employee_number
        left join
            focus_year_terms as fyt
            on sch.academic_year = fyt.syear
            and sch.schoolid = fyt.school_id
    )

select
    school_id,
    course_id,
    section_id,
    term_id,
    section_number,
    `period`,
    room,
    student_id,
    student_gsuite_email,
    school_name,
    teacher_gsuite_email,
    class_name,
from powerschool_enrollments

union all

select
    school_id,
    course_id,
    section_id,
    term_id,
    section_number,
    `period`,
    room,
    student_id,
    student_gsuite_email,
    school_name,
    teacher_gsuite_email,
    class_name,
from focus_enrollments
