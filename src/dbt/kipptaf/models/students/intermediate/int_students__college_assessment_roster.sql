select
    e._dbt_source_relation,
    e.academic_year,
    e.student_number,
    e.studentid,
    e.students_dcid,
    e.salesforce_id,
    e.grade_level,

    a.administration_round,
    a.test_type,
    a.test_date,
    a.test_month,
    a.scope,
    a.subject_area,
    a.course_discipline,
    a.score_type,
    a.scale_score,
    a.rn_highest,
    a.max_scale_score,
    a.superscore,

    /* i also have this as a reference table on the new CARAT g-sheet. when you move
       it over to the IN folder, i will replace this long case with a join to it */
    case
        when a.scope like 'PSAT%' and a.test_month in ('August', 'September', 'October')
        then 'BOY'
        when
            a.scope like 'PSAT%'
            and a.test_month in ('November', 'December', 'January', 'February', 'March')
        then 'MOY'
        when a.scope like 'PSAT%' and a.test_month in ('April', 'May', 'June', 'July')
        then 'EOY'
        when
            a.scope in ('SAT', 'ACT')
            and e.grade_level = 11
            and a.test_month in ('August', 'September')
        then 'BOY'
        when
            a.scope in ('SAT', 'ACT')
            and e.grade_level = 11
            and a.test_month
            in ('October', 'November', 'December', 'January', 'February', 'March')
        then 'MOY'
        when
            a.scope in ('SAT', 'ACT')
            and e.grade_level = 11
            and a.test_month in ('April', 'May', 'June', 'July')
        then 'EOY'
        when
            a.scope in ('SAT', 'ACT')
            and e.grade_level = 12
            and a.test_month in ('August', 'September', 'October')
        then 'BOY'
        when
            a.scope in ('SAT', 'ACT')
            and e.grade_level = 12
            and a.test_month in ('November', 'December', 'January', 'February', 'March')
        then 'MOY'
        when
            a.scope in ('SAT', 'ACT')
            and e.grade_level = 12
            and a.test_month in ('April', 'May', 'June', 'July')
        then 'EOY'
    end as admin_season,

from {{ ref("int_extracts__student_enrollments") }} as e
inner join
    {{ ref("int_assessments__college_assessment") }} as a
    on e.academic_year = a.academic_year
    and e.student_number = a.student_number
where e.school_level = 'HS' and e.rn_year = 1
