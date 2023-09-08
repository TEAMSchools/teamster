select
    'Test Rounds' as domain,
    left(ir.academic_year, 4) as academic_year,
    ir.student_id as student_number,
    ir.subject,
    cast(ir.completion_date as date) as completion_date,
    ir.test_round,
    ir.test_round_date,
    ir.percentile,
    ir.overall_scale_score,
    ir.percent_progress_to_annual_typical_growth as pct_progress_typical,
    ir.percent_progress_to_annual_stretch_growth as pct_progress_stretch
from {{ ref("base_iready__diagnostic_results") }} as ir
where ir.rn_subj_round = 1 and ir.test_round != 'Outside Round'
union all
select
    'YTD Growth' as domain,
    left(ir.academic_year, 4) as academic_year,
    ir.student_id as student_number,
    ir.subject,
    cast(ir.completion_date as date) as completion_date,
    ir.test_round,
    ir.test_round_date,
    ir.percentile,
    ir.overall_scale_score,
    ir.percent_progress_to_annual_typical_growth as pct_progress_typical,
    ir.percent_progress_to_annual_stretch_growth as pct_progress_stretch
from {{ ref("base_iready__diagnostic_results") }} as ir
inner join
    (
        select
            academic_year,
            subject,
            student_id,
            max(completion_date) as max_completion_date
        from {{ ref("base_iready__diagnostic_results") }}
        group by academic_year, subject, student_id
    ) as sub
    on ir.academic_year = sub.academic_year
    and ir.student_id = sub.student_id
    and ir.subject = sub.subject
    and ir.completion_date = sub.max_completion_date
where cast(left(ir.academic_year, 4) as int) = {{ var("current_academic_year") }}
