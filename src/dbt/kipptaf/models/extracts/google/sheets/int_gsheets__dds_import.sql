select
    cc.students_student_number,
    cc.teacher_lastfirst,

    s.school_name,
    s.grade_level,

    p.preferred_name_given_name as teacher_first,
    p.preferred_name_family_name as teacher_last,

    regexp_replace(s.first_name, r'\W', '') as student_first,
    regexp_replace(s.last_name, r'\W', '') as student_last,

    lower(p.mail) as teacher_mail,

    s.school_abbreviation
    || ' - '
    || s.grade_level
    || '.'
    || cc.sections_section_number
    || ' - '
    || p.preferred_name_family_name as class_name,
from {{ ref("base_powerschool__course_enrollments") }} as cc
inner join
    {{ ref("base_powerschool__student_enrollments") }} as s
    on cc.students_student_number = s.student_number
    and cc.cc_academic_year = s.academic_year
    and s.rn_year = 1
    and s.grade_level in (7, 8)
inner join
    {{ ref("base_people__staff_roster") }} as p
    on cc.teachernumber = p.powerschool_teacher_number
where
    cc.cc_academic_year = {{ var("current_academic_year") }}
    and cc.courses_credittype = 'ENG'
    and not cc.is_dropped_section
