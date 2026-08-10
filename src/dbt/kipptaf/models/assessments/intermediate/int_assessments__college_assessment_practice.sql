with
    sheet_assessments as (
        select distinct
            assessment_id,
            academic_year,
            test_type,
            administration_round,
            subject,
            grade_level,
        from {{ ref("stg_google_sheets__kippfwd__act_scale_score_key") }}
    ),

    responses as (
        select
            a.academic_year,
            a.illuminate_student_id,
            a.powerschool_student_number,
            a.scope,
            a.assessment_id,
            a.title as assessment_title,
            a.date_taken as test_date,
            a.response_type,
            a.response_type_description,
            a.points,

            sa.administration_round as scope_round,

            'Practice' as test_type,

            format_date('%B', a.date_taken) as test_month,

            round(a.percent_correct / 100, 2) as percent_correct,

            coalesce(
                concat(
                    format_date('%b', a.administered_at),
                    ' ',
                    format_date('%g', a.administered_at)
                ),
                sa.administration_round
            ) as administration_round,

            if(sa.subject = 'Mathematics', 'Math', sa.subject) as subject_area,

            case
                when sa.subject in ('Reading', 'Writing', 'English')
                then 'ENG'
                when sa.subject in ('Math')
                then 'MATH'
                else 'NA'
            end as course_discipline,

            if(
                a.response_type = 'overall',
                case
                    when
                        a.scope = 'SAT'
                        and sa.subject in ('Reading', 'Writing')
                        and sa.grade_level in (9, 10)
                    then (ssk.scale_score * 10)
                    else ssk.scale_score
                end,
                null
            ) as scale_score,

            count(distinct sa.subject) over (
                partition by
                    a.academic_year,
                    a.powerschool_student_number,
                    sa.administration_round
            ) as total_subjects_tested,

            countif(sa.subject = 'Reading and Writing') over (
                partition by
                    a.academic_year,
                    a.powerschool_student_number,
                    sa.administration_round
            ) as reading_writing_sections,

        from {{ ref("int_assessments__response_rollup") }} as a
        inner join sheet_assessments as sa on a.assessment_id = sa.assessment_id
        left join
            {{ ref("stg_google_sheets__kippfwd__act_scale_score_key") }} as ssk
            on a.assessment_id = ssk.assessment_id
            and a.points between ssk.raw_score_low and ssk.raw_score_high
        where a.response_type in ('group', 'overall')
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
            end as scale_score,

        from responses as r
        inner join
            {{ ref("stg_google_sheets__kippfwd__act_scale_score_key") }} as ssk
            on r.assessment_id = ssk.assessment_id
            and r.points between ssk.raw_score_low and ssk.raw_score_high
        where r.response_type = 'overall'
    ),

    two_section_totals as (
        select
            academic_year,
            powerschool_student_number,
            scope,
            scope_round,
            test_type,
            administration_round,
            total_subjects_tested,

            max(test_date) as test_date,

            sum(points) as points,

            if(count(scale_score) = 2, round(sum(scale_score), 0), null) as scale_score,

        from responses
        where
            response_type = 'overall'
            and total_subjects_tested = 2
            and reading_writing_sections > 0
        group by
            academic_year,
            powerschool_student_number,
            scope,
            scope_round,
            test_type,
            administration_round,
            total_subjects_tested
    )

select
    r.academic_year,
    r.powerschool_student_number,
    r.scope,
    r.scope_round,
    r.test_type,
    r.assessment_id,
    r.assessment_title,
    r.administration_round,
    r.course_discipline,
    r.subject_area,
    r.test_date,
    r.test_month,
    r.response_type,
    r.response_type_description,
    r.points,
    r.percent_correct,
    r.total_subjects_tested,
    s.raw_score,
    s.scale_score,

from responses as r
left join
    practice_scale_score_by_subject as s
    on r.academic_year = s.academic_year
    and r.powerschool_student_number = s.powerschool_student_number
    and r.assessment_id = s.assessment_id
where r.response_type = 'group'

union all

select distinct
    academic_year,
    powerschool_student_number,
    scope,
    scope_round,
    test_type,
    null as assessment_id,
    'NA' as assessment_title,
    administration_round,
    course_discipline,
    'Composite' as subject_area,
    test_date,
    test_month,
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

select distinct
    academic_year,
    powerschool_student_number,
    scope,
    scope_round,
    test_type,
    null as assessment_id,
    'NA' as assessment_title,
    administration_round,
    course_discipline,
    'Combined' as subject_area,
    test_date,
    test_month,
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

union all

select
    academic_year,
    powerschool_student_number,
    scope,
    scope_round,
    test_type,
    null as assessment_id,
    'NA' as assessment_title,
    administration_round,
    'NA' as course_discipline,
    'Combined' as subject_area,
    test_date,
    format_date('%B', test_date) as test_month,
    'NA' as response_type,
    'NA' as response_type_description,
    points,
    null as percent_correct,
    total_subjects_tested,
    points as raw_score,
    scale_score,
from two_section_totals
