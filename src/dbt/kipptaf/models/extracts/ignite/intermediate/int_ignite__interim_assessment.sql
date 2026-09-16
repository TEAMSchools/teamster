with
    diagnostics as (
        select
            student_id as student_number,
            academic_year_int as academic_year,
            subject,
            test_round,
            overall_scale_score,
        from {{ ref("int_iready__diagnostic_results") }}
        where
            academic_year_int in ({{ var("ignite_academic_years") | join(", ") }})
            and student_grade_int in ({{ var("ignite_grade_levels") | join(", ") }})
            and test_round in ('BOY', 'EOY')
            and rn_subj_round = 1
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
