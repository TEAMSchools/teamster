with
    checked as (
        select
            student_number,
            discipline,
            grade_level,
            grad_eligibility,

            met_ela and attempted_njgpa_ela as counts_ela,
            met_math and attempted_njgpa_math as counts_math,

            not attempted_njgpa_ela and not attempted_njgpa_math as attempted_nothing,
        from {{ ref("int_students__graduation_path_codes") }}
        where grade_level >= 11
    ),

    contradictions as (
        select
            student_number,
            discipline,
            grade_level,
            grad_eligibility,
            counts_ela,
            counts_math,

            case
                when grad_eligibility in ('Grad Eligible', 'No FAFSA')
                then
                    not (counts_ela and counts_math)
                    and not (grade_level = 11 and attempted_nothing)
                when grad_eligibility like 'ELA Only%'
                then not counts_ela or counts_math
                when grad_eligibility like 'Math Only%'
                then not counts_math or counts_ela
                when grad_eligibility in ('FAFSA Only', 'Not Grad Eligible')
                then counts_ela or counts_math
                else false
            end as contradicts_the_subjects,
        from checked
    )

select
    student_number, discipline, grade_level, grad_eligibility, counts_ela, counts_math,
from contradictions
where contradicts_the_subjects
