with
    max_completion_date as (
        select
            student_id, academic_year, subject, max(completion_date) as completion_date,
        from {{ ref("base_iready__diagnostic_results") }}
        where academic_year_int = {{ var("current_academic_year") }}
        group by academic_year, subject, student_id
    ),

    diagnostic_results as (
        select
            student_id,
            academic_year,
            academic_year_int,
            subject,
            completion_date,
            test_round,
            percentile,
            overall_placement,
            overall_scale_score,
            percent_progress_to_annual_typical_growth_percent,
            percent_progress_to_annual_stretch_growth_percent,
            rn_subj_round,

            case
                test_round
                when 'BOY'
                then 'Fall ' || left(academic_year, 4)
                when 'MOY'
                then 'Winter ' || right(academic_year, 4)
                when 'EOY'
                then 'Spring ' || right(academic_year, 4)
            end as test_round_date,
            case
                when test_round = 'BOY'
                then 'Beginning-of-year'
                when test_round = 'MOY'
                then 'Middle-of-year'
                when test_round = 'EOY'
                then 'End-of-year'
            end as test_round_display,
            case
                test_round
                when 'BOY'
                then 'Aug ' || "'" || right(left(academic_year, 4), 2)
                when 'MOY'
                then 'Jan ' || "'" || right(academic_year, 2)
                when 'EOY'
                then 'May ' || "'" || right(academic_year, 2)
            end as test_round_display_short,
            if(
                overall_placement like 'Level%',
                regexp_replace(overall_placement, 'Level', 'Grade'),
                overall_placement
            ) as overall_placement_display,
        from {{ ref("base_iready__diagnostic_results") }}
        where academic_year_int >= {{ var("current_academic_year") }} - 1
    )

select
    student_id as student_number,
    academic_year_int as academic_year,
    subject,
    completion_date,
    test_round,
    test_round_date,
    test_round_display,
    test_round_display_short,
    percentile,
    overall_placement,
    overall_scale_score,
    overall_placement_display,
    percent_progress_to_annual_typical_growth_percent as pct_progress_typical,
    percent_progress_to_annual_stretch_growth_percent as pct_progress_stretch,

    'Test Rounds' as `domain`,
from diagnostic_results
where rn_subj_round = 1 and test_round != 'Outside Round'

union all

select
    ir.student_id as student_number,
    ir.academic_year_int as academic_year,
    ir.subject,
    ir.completion_date,
    ir.test_round,
    ir.test_round_date,
    ir.test_round_display,
    ir.test_round_display_short,
    ir.percentile,
    ir.overall_placement,
    ir.overall_scale_score,
    ir.overall_placement_display,
    ir.percent_progress_to_annual_typical_growth_percent as pct_progress_typical,
    ir.percent_progress_to_annual_stretch_growth_percent as pct_progress_stretch,

    'YTD Growth' as `domain`,
from diagnostic_results as ir
inner join
    max_completion_date as mcd
    on ir.student_id = mcd.student_id
    and ir.academic_year = mcd.academic_year
    and ir.subject = mcd.subject
    and ir.completion_date = mcd.completion_date
where ir.academic_year_int = {{ var("current_academic_year") }}
