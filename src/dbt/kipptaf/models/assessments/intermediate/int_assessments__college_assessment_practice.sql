with
    responses as (
        select
            a.academic_year_clean as academic_year,
            a.powerschool_student_number,
            a.student_id,
            a.assessment_id,
            a.title as assessment_title,
            a.scope,
            a.subject_area,

            concat(
                format_date('%b', a.administered_at),
                ' ',
                format_date('%g', a.administered_at)
            ) as administration_round,
            a.administered_at as test_date,

            a.response_type,
            a.response_type_description,
            a.points,
            a.points_possible,
            a.performance_band_level,

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

            count(distinct a.subject_area) over (
                partition by
                    a.academic_year,
                    a.powerschool_student_number,
                    ssk.administration_round

            ) as total_subjects_tested,
        from {{ ref("int_assessments__response_rollup") }} as a
        inner join
            {{ ref("stg_assessments__act_scale_score_key") }} as ssk
            on a.assessment_id = ssk.assessment_id
            and a.points between ssk.raw_score_low and ssk.raw_score_high
        where
            a.scope in ('ACT', 'SAT')
            and a.academic_year = {{ var("current_academic_year") }}  -- first year
            and a.response_type in ('overall', 'group')
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

    administered_at,
    powerschool_student_number,
    response_type,
    response_type_description,
    administration_round,
    performance_band_label,
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

    null as administered_at,
    powerschool_student_number,
    null as response_type,
    null as response_type_description,
    administration_round,
    null as performance_band_label,

    sum(points) as points,
    sum(points_possible) as points_possible,
    safe_cast(round(avg(scale_score), 0) as int) as scale_score,
from responses
where scope = 'ACT' and response_type = 'overall' and total_subjects_tested = 4
group by scope, academic_year, powerschool_student_number, administration_round

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

    null as administered_at,
    powerschool_student_number,
    null as response_type,
    null as response_type_description,
    administration_round,
    null as performance_band_label,

    sum(points) as points,
    sum(points_possible) as points_possible,
    sum(scale_score) as scale_score,
from responses
where scope = 'SAT' and response_type = 'overall' and total_subjects_tested = 3
group by scope, academic_year, student_id, administration_round
group by scope, academic_year, powerschool_student_number, administration_round
