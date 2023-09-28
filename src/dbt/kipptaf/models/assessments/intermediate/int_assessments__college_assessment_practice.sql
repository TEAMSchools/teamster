with
    responses as (
        select
            a.assessment_id,
            a.title as assessment_title,
            a.scope,
            a.subject_area,
            a.academic_year_clean as academic_year,
            concat(
                format_date('%b', a.administered_at),
                ' ',
                format_date('%g', a.administered_at)
            ) as administration_round,
            a.administered_at as test_date

            asr.student_id,
            asr.response_type,
            asr.response_type_description,
            asr.points,
            asr.points_possible,
            asr.performance_band_level,

            ssk.administration_round as scope_round,
            -- Uses the approx raw score to bring a scale score
            -- Convert the scale scores to be ready to add 
            -- for sat composite score from the gsheet
            case
                when
                    a.scope = 'SAT'
                    and a.subject_area in ('Reading', 'Writing')
                    and ssk.grade_level in (9, 10)
                then (ssk.scale_score * 10)
                else ssk.scale_score
            end as scale_score,

            -- Determine if we have enough scores to calculate the composite
            count(distinct a.subject_area) over (
                partition by a.academic_year, asr.student_id, ssk.administration_round
            ) as total_subjects_tested,
        from {{ ref("base_illuminate__assessments") }} as a
        inner join
            {{ ref("int_illuminate__agg_student_responses") }} as asr
            on a.assessment_id = asr.assessment_id
            and asr.response_type in ('overall', 'group')
        inner join
            {{ ref("stg_assessments__act_scale_score_key") }} as ssk
            on asr.assessment_id = ssk.assessment_id
            and asr.points between ssk.raw_score_low and ssk.raw_score_high
        where a.scope in ('ACT', 'SAT') and a.academic_year >= 2023  -- first year
    )

select
    assessment_id,
    assessment_title,
    scope,
    scope_round,
    administration_round,
    test_date,
    subject_area,
    academic_year,
    student_id,
    response_type,
    response_type_description,

    performance_band_level,
    points,
    points_possible,
    scale_score,
from responses
where response_type = 'group'

union all

select
    null as assessment_id,
    null as assessment_title,
    scope,
    scope_round,
    administration_round,
    test_date,
    'Composite' as subject_area,
    academic_year,
    student_id,

    null as response_type,
    null as response_type_description,
    null as performance_band_level,

    sum(points) as points,
    sum(points_possible) as points_possible,
    safe_cast(round(avg(scale_score), 0) as int) as scale_score,
from responses
where scope = 'ACT' and response_type = 'overall' and total_subjects_tested = 4
group by scope, academic_year, student_id, administration_round

union all

select
    null as assessment_id,
    null as assessment_title,
    scope,
    scope_round,
    administration_round,
    test_date,
    'Composite' as subject_area,
    academic_year,
    student_id,
    null as response_type,
    null as response_type_description,
    null as performance_band_level,

    sum(points) as points,
    sum(points_possible) as points_possible,
    sum(scale_score) as scale_score,
from responses
where scope = 'SAT' and response_type = 'overall' and total_subjects_tested = 3
group by scope, academic_year, student_id, administration_round
