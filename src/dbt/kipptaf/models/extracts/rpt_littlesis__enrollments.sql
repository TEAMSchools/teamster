select
    sec.sections_schoolid as school_id,
    sec.sections_course_number as course_id,
    sec.sections_id as section_id,
    sec.sections_termid as term_id,
    sec.sections_section_number as section_number,
    sec.sections_external_expression as `period`,
    sec.sections_room as room,

    s.student_number as student_id,

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
    {{ ref("stg_powerschool__students") }} as s
    on sec.cc_studentid = s.id
    and {{ union_dataset_join_clause(left_alias="sec", right_alias="s") }}
    and s.enroll_status = 0
inner join
    {{ ref("stg_people__student_logins") }} as sas
    on s.student_number = sas.student_number
inner join
    {{ ref("stg_powerschool__schools") }} as sch
    on sec.sections_schoolid = sch.school_number
    and {{ union_dataset_join_clause(left_alias="sec", right_alias="sch") }}
inner join
    {{ ref("int_people__staff_roster") }} as scw
    on sec.teachernumber = scw.powerschool_teacher_number
where
    sec.cc_academic_year = {{ var("current_academic_year") }}
    and not sec.is_dropped_section
    and sec.courses_credittype != 'LOG'
