with
    sections as (
        select
            sec.sections_id,
            sec.sections_section_number,
            sec.sections_external_expression,
            sec.sections_schoolid,
            sec.sections_termid,
            sec.sections_course_number,
            sec.sections_room,
            sec._dbt_source_relation,
            concat(
                sec.sections_schoolid,
                '-',
                sec.sections_course_number,
                '-',
                sec.sections_id,
                '-',
                sec.sections_termid
            ) as class_alias,
            concat(
                sec.courses_course_name,
                ' (' || sec.sections_course_number || ') - ',
                sec.sections_section_number || ' - ',
                {{ var("current_academic_year") }},
                '-',
                ({{ var("current_academic_year") }} + 1)
            ) as class_name,

            sch.name as school_name,

            scw.google_email as teacher_gsuite_email,
        from {{ ref("base_powerschool__sections") }} as sec
        inner join
            {{ ref("stg_powerschool__schools") }} as sch
            on sec.sections_schoolid = sch.school_number
            and {{ union_dataset_join_clause(left_alias="sec", right_alias="sch") }}
        inner join
            {{ ref("base_people__staff_roster") }} as scw
            on sec.teachernumber = scw.powerschool_teacher_number
        where
            sec.terms_yearid = ({{ var("current_academic_year") }} - 1990)
            and sec.sections_no_of_students > 0
            and sec.courses_credittype != 'LOG'
    )

select *
from sections
