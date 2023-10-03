with
    responses as (
        select
            a.academic_year,
            a.illuminate_student_id,
            a.powerschool_student_number,
            a.scope,  -- ACT or SAT
            a.assessment_id,
            a.title as assessment_title,
            concat(
                format_date('%b', a.administered_at),
                ' ',
                format_date('%g', a.administered_at)
            ) as administration_round,
            a.subject_area,
            a.date_taken as test_date,
            a.response_type,  -- Group or overall
            a.response_type_description,  -- Group name
            a.points,  -- Points earned... looks to be # of questions correct on Illuminate
            round(a.percent_correct/100, 2) as percent_correct,  -- % correct field on Illuminate

            count(distinct a.subject_area) over (
                partition by
                    a.academic_year,
                    a.powerschool_student_number,
                    ssk.administration_round

            ) as total_subjects_tested,

            ssk.administration_round as scope_round,
            -- Uses the approx raw score to bring a scale score
            -- Convert the scale scores to be ready to add 
            -- for sat composite score from the gsheet
            if(
                response_type = 'overall',
                case
                    when
                        a.scope = 'SAT'
                        and a.subject_area in ('Reading', 'Writing')
                        and ssk.grade_level in (9, 10)
                    then (ssk.scale_score * 10)
                    else ssk.scale_score
                end,
                null
            ) as scale_score,

        from {{ ref("int_assessments__response_rollup") }} as a
        inner join
            {{ ref("stg_assessments__act_scale_score_key") }} as ssk
            on a.assessment_id = ssk.assessment_id
            and a.points between ssk.raw_score_low and ssk.raw_score_high
        where
            a.scope in ('ACT', 'SAT')
            and a.academic_year = {{ var("current_academic_year") }}
            and a.response_type in ('group', 'overall')
    )

select
    academic_year,
    powerschool_student_number,

    scope,
    scope_round,

    assessment_id,
    assessment_title,
    administration_round,

    subject_area,
    test_date,

    response_type,
    response_type_description,

    points,
    percent_correct,

    total_subjects_tested,

    scale_score

from responses
where response_type = 'group'

union all

select
    academic_year,
    powerschool_student_number,

    scope,
    scope_round,

    null as assessment_id,
    'NA' as assessment_title,
    administration_round,

    'Composite' as subject_area,
    test_date,

    'NA' as response_type,
    'NA' as response_type_description,

    points,
    percent_correct,

    total_subjects_tested,

    round(
        avg(scale_score) over (
            partition by
                academic_year,
                powerschool_student_number,
                scope_round,
                administration_round
        ),
        0
    ) as scale_score,

from responses
where scope = 'ACT' and response_type = 'overall' and total_subjects_tested = 4

union all

select
    academic_year,
    powerschool_student_number,

    scope,
    scope_round,

    null as assessment_id,
    'NA' as assessment_title,
    administration_round,

    'Composite' as subject_area,
    test_date,

    'NA' as response_type,
    'NA' as response_type_description,

    points,
    percent_correct,

    total_subjects_tested,

    round(
        sum(scale_score) over (
            partition by
                academic_year,
                powerschool_student_number,
                scope_round,
                administration_round
        ),
        0
    ) as scale_score,

from responses
where scope = 'SAT' and response_type = 'overall' and total_subjects_tested = 3
