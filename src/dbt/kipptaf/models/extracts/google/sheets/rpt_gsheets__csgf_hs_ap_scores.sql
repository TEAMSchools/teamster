select
    e1.student_number as studentid,

    cast(a.academic_year as string)
    || '-'
    || cast(a.academic_year + 1 as string) as test_year,

    e2.grade_level as grade_level_when_taken,

    round(a.exam_score, 0) as score,

    case
        a.ap_course_name
        when 'AP US History'
        then 'AP United States History'
        when 'AP US Government and Politics'
        then 'AP United States Government and Politics'
        when 'AP Pre-Calculus'
        then 'AP Precalculus'
        else a.ap_course_name
    end as aptest_name,

from {{ ref("int_extracts__student_enrollments") }} as e1
inner join
    {{ ref("int_assessments__ap_assessments") }} as a
    on e1.student_number = a.powerschool_student_number
    and a.rn_highest = 1
inner join
    {{ ref("int_extracts__student_enrollments") }} as e2
    on a.academic_year = e2.academic_year
    and a.powerschool_student_number = e2.student_number
    and e2.rn_year = 1
where
    e1.academic_year = {{ var("current_academic_year") - 1 }}
    and e1.school_level = 'HS'
    and e1.rn_year = 1
    and e1.is_enrolled_recent
