with
    responses as (
        select
            a.academic_year,
            a.illuminate_student_id,
            a.powerschool_student_number,
            a.scope,  -- ACT or SAT
            'Practice' as test_type,
            a.assessment_id,
            a.title as assessment_title,
            concat(
                format_date('%b', a.administered_at),
                ' ',
                format_date('%g', a.administered_at)
            ) as administration_round,
            case
                when a.subject_area = 'Mathematics' then 'Math' else a.subject_area
            end as subject_area,
            a.date_taken as test_date,
            a.response_type,  -- Group or overall
            a.response_type_description,  -- Group name
            a.points,  -- Points earned... looks to be # of questions correct on Illuminate
            round(a.percent_correct / 100, 2) as percent_correct,  -- % correct field on Illuminate

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
    ),

    practice_scale_score_by_subject as (
        select
            r.academic_year,
            r.powerschool_student_number,
            r.assessment_id,

            r.points as raw_score,
            case
                when
                    r.scope = 'SAT'
                    and r.subject_area in ('Reading', 'Writing')
                    and ssk.grade_level in (9, 10)
                then (ssk.scale_score * 10)
                else ssk.scale_score
            end as scale_score

        from responses as r
        inner join
            {{ ref("stg_assessments__act_scale_score_key") }} as ssk
            on r.assessment_id = ssk.assessment_id
            and r.points between ssk.raw_score_low and ssk.raw_score_high
        where r.response_type = 'overall'
    )

select
    r.academic_year,
    r.powerschool_student_number,

    r.scope,
    r.scope_round,

    r.assessment_id,
    r.assessment_title,
    r.administration_round,

    r.subject_area,
    r.test_date,

    r.response_type,
    r.response_type_description,

    r.points,
    r.percent_correct,

    r.total_subjects_tested,

    s.raw_score,
    s.scale_score

from responses as r
left join
    practice_scale_score_by_subject as s
    on r.academic_year = s.academic_year
    and r.powerschool_student_number = s.powerschool_student_number
    and r.assessment_id = s.assessment_id
where r.response_type = 'group'

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

    sum(points) over (
        partition by
            academic_year, powerschool_student_number, scope_round, administration_round
    ) as points,

    null as percent_correct,

    total_subjects_tested,

    sum(points) over (
        partition by
            academic_year, powerschool_student_number, scope_round, administration_round
    ) as raw_score,

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

    sum(points) over (
        partition by
            academic_year, powerschool_student_number, scope_round, administration_round
    ) as points,

    null as percent_correct,

    total_subjects_tested,

    sum(points) over (
        partition by
            academic_year, powerschool_student_number, scope_round, administration_round
    ) as raw_score,

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
