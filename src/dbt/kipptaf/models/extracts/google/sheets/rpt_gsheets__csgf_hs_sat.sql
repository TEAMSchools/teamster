select
    e.student_number as studentid,

    if(
        a.subject_area = 'EBRW', 'Evidence-Based Reading and Writing', a.subject_area
    ) as `section`,

    round(a.scale_score, 0) as score,

from {{ ref("int_extracts__student_enrollments") }} as e
inner join
    {{ ref("int_assessments__college_assessment") }} as a
    on e.student_number = a.student_number
    and a.scope = 'SAT'
    and a.subject_area in ('Math', 'EBRW')
    and a.rn_highest = 1
where
    e.academic_year = {{ var("current_academic_year") - 1 }}
    and e.school_level = 'HS'
    and e.rn_year = 1
    and e.is_enrolled_recent
