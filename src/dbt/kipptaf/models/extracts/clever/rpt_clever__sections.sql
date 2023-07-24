{{ config(enabled=False) }}

with
    dsos as (
        select
            df.ps_teachernumber as teacher_id,

            coalesce(ccw.ps_school_id, df.primary_site_schoolid) as school_id
        from people.staff_crosswalk_static as df
        left join
            people.campus_crosswalk as ccw
            on df.primary_site = ccw.campus_name
            and not ccw.is_pathways
        where
            df.assignment_status != 'Terminated'
            and df.job_title in (
                'Director of Campus Operations',
                'Director Campus Operations',
                'Director School Operations',
                'School Leader'
            )
    ),

    teachers_long as (
        select
            sec.schoolid as school_id,
            sec.section_number as section_number,
            sec.course_number as course_number,
            sec.section_number as period,

            r.sortorder,

            t.teachernumber as teacher_id,

            c.course_name as course_name,

            terms.abbreviation as term_name,

            null as name,
            null as grade,
            null as course_description,

            convert(varchar, terms.firstday, 101) as term_start,
            convert(varchar, terms.lastday, 101) as term_end,

            concat(
                case
                    when sec.db_name = 'kippnewark'
                    then 'NWK'
                    when sec.db_name = 'kippcamden'
                    then 'CMD'
                    when sec.db_name = 'kippmiami'
                    then 'MIA'
                end,
                sec.id
            ) as section_id,

            case
                when c.credittype = 'ART'
                then 'Arts and music'
                when c.credittype = 'CAREER'
                then 'other'
                when c.credittype = 'COCUR'
                then 'other'
                when c.credittype = 'ELEC'
                then 'other'
                when c.credittype = 'ENG'
                then 'English/language arts'
                when c.credittype = 'LOG'
                then 'other'
                when c.credittype = 'MATH'
                then 'Math'
                when c.credittype = 'NULL'
                then 'Homeroom/advisory'
                when c.credittype = 'PHYSED'
                then 'PE and health'
                when c.credittype = 'RHET'
                then 'English/language arts'
                when c.credittype = 'SCI'
                then 'Science'
                when c.credittype = 'SOC'
                then 'Social studies'
                when c.credittype = 'STUDY'
                then 'other'
                when c.credittype = 'WLANG'
                then 'Language'
            end as subject
        from powerschool.sections as sec
        inner join
            powerschool.sectionteacher as st
            on sec.id = st.sectionid
            and sec.db_name = st.db_name
        inner join
            powerschool.roledef as r on st.roleid = r.id and st.db_name = r.db_name
        inner join
            powerschool.teachers_static as t
            on st.teacherid = t.id
            and sec.schoolid = t.schoolid
            and sec.db_name = t.db_name
        inner join
            powerschool.courses as c
            on sec.course_number = c.course_number
            and sec.db_name = c.db_name
        inner join
            powerschool.terms
            on sec.termid = terms.id
            and sec.schoolid = terms.schoolid
            and sec.db_name = terms.db_name
            and cast(current_timestamp as date) between terms.firstday and terms.lastday
        where sec.no_of_students > 0

        union all

        select
            dsos.school_id,
            concat(
                utilities.global_academic_year(), s.abbreviation, r.n
            ) as section_number,
            'ENR' as course_number,
            concat(utilities.global_academic_year(), s.abbreviation, r.n) as period,
            1 as sortorder,
            dsos.teacher_id,
            'Enroll' as course_name,
            concat(
                right(utilities.global_academic_year(), 2),
                '-',
                right(utilities.global_academic_year() + 1, 2)
            ) as term_name,
            null as name,
            case
                when r.n = 0 then 'Kindergarten' else cast(r.n as varchar(5))
            end as grade,
            null as course_description,
            convert(
                varchar, date(utilities.global_academic_year(), 7, 1), 101
            ) as term_start,
            convert(
                varchar, date(utilities.global_academic_year() + 1, 6, 30), 101
            ) as term_end,
            concat(
                utilities.global_academic_year() - 1990,
                dsos.school_id,
                right(concat(0, r.n), 2)
            ) as section_id,
            'Homeroom/advisory' as subject
        from dsos
        inner join powerschool.schools as s on dsos.school_id = s.school_number
        inner join
            utilities.row_generator_smallint as r
            on r.n between s.low_grade and s.high_grade
    ),

    pre_pivot as (
        select
            school_id,
            section_id,
            name,
            section_number,
            grade,
            course_name,
            course_number,
            course_description,
            period,
            subject,
            term_name,
            term_start,
            term_end,
            teacher_id,
            concat(
                'Teacher_',
                row_number() over (partition by section_id order by sortorder asc),
                '_id'
            ) as pivot_field
        from teachers_long
    )

select
    school_id,
    section_id,
    teacher_id,
    teacher_2_id,
    teacher_3_id,
    teacher_4_id,
    teacher_5_id,
    teacher_6_id,
    teacher_7_id,
    teacher_8_id,
    teacher_9_id,
    teacher_10_id,
    name,
    section_number,
    grade,
    course_name,
    course_number,
    course_description,
    period,
    subject,
    term_name,
    term_start,
    term_end
from
    pre_pivot pivot (
        max(teacher_id) for pivot_field in (
            'teacher_1_id' as `teacher_id`,
            'teacher_2_id',
            'teacher_3_id',
            'teacher_4_id',
            'teacher_5_id',
            'teacher_6_id',
            'teacher_7_id',
            'teacher_8_id',
            'teacher_9_id',
            'teacher_10_id'
        )
    )
