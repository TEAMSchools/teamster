-- TODO(#6174): read the marts once they carry the PowerSchool section id and
-- section term id
select
    fg.student_number,
    fg.schoolid,
    fg.term_grade_points as gpa_points,
    fg.term_letter_grade_adjusted as grade,
    fg.storecode,
    fg._dbt_source_project as code_location,

    ce.students_grade_level as grade_level,
    ce.courses_credittype as credit_type,
    ce.cc_course_number as course_number,
    ce.courses_course_name as course_name,
    ce.teacher_lastfirst as teacher_name,
    ce.cc_sectionid as sectionid,
    ce.courses_gradescale_name as gradescale_name,
    ce.school_name as schoolname,
    ce.sections_termid as termid,
    ce.school_level_alt as school_level,

    0 as `PotentialCrHrs`,
    0 as `EarnedCrHrs`,

    least(fg.term_percent_grade_adjusted, 100) as `percent`,

    if(ce.school_level_alt = 'HS', fg.comment_value, null) as `Comment`,
from {{ ref("int_students__final_grades") }} as fg
inner join
    {{ ref("int_students__course_enrollments") }} as ce
    on fg.cc_dcid = ce.cc_dcid
    and fg._dbt_source_project = ce._dbt_source_project
where
    fg.term_percent_grade_adjusted is not null
    -- revisit if 0-credit courses ever need storing
    and fg.potential_credit_hours != 0
    and not ce.is_homeroom
    -- grade 5 and up is stored at every NJ school; ES grades are not
    and ce.school_level_alt in ('MS', 'HS')
