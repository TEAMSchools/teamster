with
    dsos as (
        select
            sr.powerschool_teacher_number,

            coalesce(
                ccw.powerschool_school_id, sr.home_work_location_powerschool_school_id
            ) as school_id
        from {{ ref("base_people__staff_roster") }} as sr
        left join
            {{ source("people", "src_people__campus_crosswalk") }} as ccw
            on sr.home_work_location_name = ccw.name
            and not ccw.is_pathways
        where
            sr.assignment_status != 'Terminated'
            and sr.job_title in (
                'Director of Campus Operations',
                'Director Campus Operations',
                'Director School Operations',
                'School Leader'
            )
    ),

    teachers_long as (
        select
            sec.sections_schoolid,
            sec.sections_section_number,
            sec.sections_course_number,
            sec.courses_course_name,
            sec.terms_abbreviation,
            format_date('%m/%d/%Y', sec.terms_firstday) as terms_firstday,
            format_date('%m/%d/%Y', sec.terms_lastday) as terms_lastday,
            concat(
                regexp_extract(sec._dbt_source_relation, r'(kipp\w+)_'), sec.sections_id
            ) as section_id,
            case
                sec.courses_credittype
                when 'ART'
                then 'Arts and music'
                when 'CAREER'
                then 'other'
                when 'COCUR'
                then 'other'
                when 'ELEC'
                then 'other'
                when 'ENG'
                then 'English/language arts'
                when 'LOG'
                then 'other'
                when 'MATH'
                then 'Math'
                when 'NULL'
                then 'Homeroom/advisory'
                when 'PHYSED'
                then 'PE and health'
                when 'RHET'
                then 'English/language arts'
                when 'SCI'
                then 'Science'
                when 'SOC'
                then 'Social studies'
                when 'STUDY'
                then 'other'
                when 'WLANG'
                then 'Language'
            end as `subject`,

            r.sortorder,

            t.teachernumber,

            null as grade,
        from {{ ref("base_powerschool__sections") }} as sec
        inner join
            {{ ref("stg_powerschool__sectionteacher") }} as st
            on sec.sections_id = st.sectionid
            and {{ union_dataset_join_clause(left_alias="sec", right_alias="st") }}
        inner join
            {{ ref("stg_powerschool__roledef") }} as r
            on st.roleid = r.id
            and {{ union_dataset_join_clause(left_alias="st", right_alias="r") }}
        inner join
            {{ ref("int_powerschool__teachers") }} as t
            on st.teacherid = t.id
            and sec.sections_schoolid = t.schoolid
            and {{ union_dataset_join_clause(left_alias="st", right_alias="t") }}
        where
            sec.terms_yearid = ({{ var("current_academic_year") }} - 1990)
            and sec.sections_no_of_students > 0

        union all

        select
            dsos.school_id as sections_schoolid,

            concat(
                {{ var("current_academic_year") }}, s.abbreviation, grade_level
            ) as sections_section_number,

            'ENR' as sections_course_number,
            'Enroll' as courses_course_name,

            concat(
                right(cast({{ var("current_academic_year") }} as string), 2),
                '-',
                right(cast(({{ var("current_academic_year") }} + 1) as string), 2)
            ) as terms_abbreviation,
            format_date(
                '%m/%d/%Y', date({{ var("current_academic_year") }}, 7, 1)
            ) as terms_firstday,
            format_date(
                '%m/%d/%Y', date({{ var("current_academic_year") }} + 1, 6, 30)
            ) as terms_lastday,

            concat(
                {{ var("current_academic_year") }} - 1990,
                dsos.school_id,
                right(concat(0, grade_level), 2)
            ) as section_id,

            'Homeroom/advisory' as `subject`,

            1 as sortorder,

            dsos.powerschool_teacher_number as teachernumber,

            case
                when grade_level = 0
                then 'Kindergarten'
                else cast(grade_level as string)
            end as grade,
        from dsos
        inner join
            {{ ref("stg_powerschool__schools") }} as s
            on dsos.school_id = s.school_number
        cross join unnest(generate_array(s.low_grade, s.high_grade)) as grade_level
    ),

    pre_pivot as (
        select
            section_id,
            sections_section_number,
            sections_schoolid,
            sections_course_number,
            courses_course_name,
            terms_abbreviation,
            terms_firstday,
            terms_lastday,
            `subject`,
            teachernumber,
            grade,
            concat(
                'teacher_',
                row_number() over (partition by section_id order by sortorder asc),
                '_id'
            ) as input_column
        from teachers_long
    )

select
    sections_schoolid as school_id,
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
    null as `name`,
    sections_section_number as section_number,
    grade,
    courses_course_name as course_name,
    sections_course_number as course_number,
    null as course_description,
    sections_section_number as `period`,
    `subject`,
    terms_abbreviation as term_name,
    terms_firstday as term_start,
    terms_lastday as term_end,
from
    pre_pivot pivot (
        max(teachernumber) for input_column in (
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
