with
    max_completion_date as (
        select
            student_id, academic_year, subject, max(completion_date) as completion_date,
        from {{ ref("base_iready__diagnostic_results") }}
        where academic_year_int = {{ var("current_academic_year") }}
        group by academic_year, subject, student_id
    )

select
    student_id as student_number,
    academic_year_int as academic_year,
    subject,
    completion_date,
    test_round,
    test_round_date,
    test_round_display,
    percentile,
    overall_placement,
    overall_scale_score,
    percent_progress_to_annual_typical_growth_percent as pct_progress_typical,
    percent_progress_to_annual_stretch_growth_percent as pct_progress_stretch,

    'Test Rounds' as `domain`,

    if(
        overall_placement like 'Level%',
        regexp_replace(overall_placement, 'Level', 'Grade'),
        overall_placement
    ) as overall_placement_display,
from {{ ref("base_iready__diagnostic_results") }}
where
    rn_subj_round = 1
    and test_round != 'Outside Round'
    and academic_year_int >= {{ var("current_academic_year") }} - 1

union all

select
    ir.student_id as student_number,
    ir.academic_year_int as academic_year,
    ir.subject,
    ir.completion_date,
    ir.test_round,
    ir.test_round_date,
    ir.test_round_display,
    ir.percentile,
    ir.overall_placement,
    ir.overall_scale_score,
    ir.percent_progress_to_annual_typical_growth_percent as pct_progress_typical,
    ir.percent_progress_to_annual_stretch_growth_percent as pct_progress_stretch,

    'YTD Growth' as `domain`,

    if(
        ir.overall_placement like 'Level%',
        regexp_replace(ir.overall_placement, 'Level', 'Grade'),
        ir.overall_placement
    ) as overall_placement_display,
from {{ ref("base_iready__diagnostic_results") }} as ir
inner join
    max_completion_date as mcd
    on ir.student_id = mcd.student_id
    and ir.academic_year = mcd.academic_year
    and ir.subject = mcd.subject
    and ir.completion_date = mcd.completion_date
where ir.academic_year_int = {{ var("current_academic_year") }}
