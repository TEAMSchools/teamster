with
    diagnostics as (
        select
            dr.subject,
            dr.test_round,
            dr.overall_scale_score,

            sy.student_number,
            sy.academic_year,
        from {{ ref("int_iready__diagnostic_results") }} as dr
        inner join
            {{ ref("int_ignite__student_years") }} as sy
            on dr.student_id = sy.student_number
            and dr.academic_year_int = sy.academic_year
        where
            dr.student_grade_int between 9 and 12
            and dr.test_round in ('BOY', 'EOY')
            and dr.rn_subj_round = 1
    )

select
    student_number,
    academic_year,

    max(
        if(subject = 'Reading' and test_round = 'BOY', overall_scale_score, null)
    ) as iready_boy_score_r,
    max(
        if(subject = 'Reading' and test_round = 'EOY', overall_scale_score, null)
    ) as iready_eoy_score_r,
    max(
        if(subject = 'Math' and test_round = 'BOY', overall_scale_score, null)
    ) as iready_boy_score_m,
    max(
        if(subject = 'Math' and test_round = 'EOY', overall_scale_score, null)
    ) as iready_eoy_score_m,
from diagnostics
group by student_number, academic_year
