with
    staff_roster as (
        select powerschool_teacher_number, google_email,
        from {{ ref("int_people__staff_roster") }}

        union all

        select employee_id as powerschool_teacher_number, google_email,
        from {{ ref("int_people__temp_staff") }}
    )

select
    sec.sections_schoolid as school_id,
    sec.sections_course_number as course_id,
    sec.sections_id as section_id,
    sec.sections_termid as term_id,
    sec.sections_section_number as section_number,
    sec.sections_external_expression as `period`,
    sec.sections_room as room,
    sec.students_student_number as student_id,
    sec.school_name,

    sas.google_email as student_gsuite_email,

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
inner join staff_roster as scw on sec.teachernumber = scw.powerschool_teacher_number
where
    sec.cc_academic_year = {{ var("current_academic_year") }}
    and not sec.is_dropped_section
    and sec.courses_credittype != 'LOG'
