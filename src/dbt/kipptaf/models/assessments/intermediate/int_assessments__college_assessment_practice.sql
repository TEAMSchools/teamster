with
    responses as (
        select
            a.assessment_id,
            a.title as assessment_title,
            a.scope,
            a.subject_area,
<<<<<<< HEAD
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
=======
            a.academic_year,
            a.administered_at,
            a.powerschool_student_number,
            a.response_type,
            a.response_type_description,
            a.points,
            a.points_possible,
            a.performance_band_label,

            ssk.administration_round,
>>>>>>> 4d3818f42a7007b4c0cf8a5642f16c71f8192790
            case
                when
                    a.scope = 'SAT'
                    and a.subject_area in ('Reading', 'Writing')
                    and ssk.grade_level in (9, 10)
                then (ssk.scale_score * 10)
                else ssk.scale_score
            end as scale_score,

            count(distinct a.subject_area) over (
<<<<<<< HEAD
                partition by a.academic_year, asr.student_id, ssk.administration_round
=======
                partition by
                    a.academic_year,
                    a.powerschool_student_number,
                    ssk.administration_round
>>>>>>> 4d3818f42a7007b4c0cf8a5642f16c71f8192790
            ) as total_subjects_tested,
        from {{ ref("int_assessments__response_rollup") }} as a
        inner join
            {{ ref("stg_assessments__act_scale_score_key") }} as ssk
            on a.assessment_id = ssk.assessment_id
            and a.points between ssk.raw_score_low and ssk.raw_score_high
        where
            a.scope in ('ACT', 'SAT')
            and a.academic_year >= 2023  -- first year
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
<<<<<<< HEAD
    student_id,
    response_type,
    response_type_description,

    performance_band_level,
=======
    administered_at,
    powerschool_student_number,
    response_type,
    response_type_description,
    administration_round,
    performance_band_label,
>>>>>>> 4d3818f42a7007b4c0cf8a5642f16c71f8192790
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
<<<<<<< HEAD
    student_id,

    null as response_type,
    null as response_type_description,
    null as performance_band_level,
=======
    null as administered_at,
    powerschool_student_number,
    null as response_type,
    null as response_type_description,
    administration_round,
    null as performance_band_label,
>>>>>>> 4d3818f42a7007b4c0cf8a5642f16c71f8192790

    sum(points) as points,
    sum(points_possible) as points_possible,
    safe_cast(round(avg(scale_score), 0) as int) as scale_score,
from responses
where scope = 'ACT' and response_type = 'overall' and total_subjects_tested = 4
<<<<<<< HEAD
group by scope, academic_year, student_id, administration_round
=======
group by scope, academic_year, powerschool_student_number, administration_round
>>>>>>> 4d3818f42a7007b4c0cf8a5642f16c71f8192790

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
<<<<<<< HEAD
    student_id,
    null as response_type,
    null as response_type_description,
    null as performance_band_level,
=======
    null as administered_at,
    powerschool_student_number,
    null as response_type,
    null as response_type_description,
    administration_round,
    null as performance_band_label,
>>>>>>> 4d3818f42a7007b4c0cf8a5642f16c71f8192790

    sum(points) as points,
    sum(points_possible) as points_possible,
    sum(scale_score) as scale_score,
from responses
where scope = 'SAT' and response_type = 'overall' and total_subjects_tested = 3
<<<<<<< HEAD
group by scope, academic_year, student_id, administration_round
=======
group by scope, academic_year, powerschool_student_number, administration_round
>>>>>>> 4d3818f42a7007b4c0cf8a5642f16c71f8192790
