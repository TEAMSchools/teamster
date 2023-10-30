with
    assessment_responses as (
        select
            ais.assessment_id,
            ais.title as assessment_title,
            ais.academic_year_clean as academic_year,
            ais.administered_at,
            ais.subject_area,

            agl.grade_level,

            rt.code as term_code,
            rt.name as administration_round,

            asr.student_id as illuminate_student_id,
            asr.performance_band_level as overall_performance_band,
            asr.percent_correct as overall_percent_correct,
            asr.number_of_questions,

            s.local_student_id as student_number,

            round(
                safe_divide(asr.percent_correct, 100) * asr.number_of_questions, 0
            ) as overall_number_correct,
        from {{ ref("base_illuminate__assessments") }} as ais
        inner join
            {{ ref("stg_illuminate__assessment_grade_levels") }} as agl
            on ais.assessment_id = agl.assessment_id
        inner join
            {{ ref("stg_reporting__terms") }} as rt
            on ais.administered_at between rt.start_date and rt.end_date
            and rt.type = 'ACT'
        inner join
            {{ ref("stg_illuminate__agg_student_responses_overall") }} as asr
            on ais.assessment_id = asr.assessment_id
        inner join
            {{ ref("stg_illuminate__students") }} as s on asr.student_id = s.student_id
        where ais.scope = 'ACT Prep'
    ),

    scaled as (  -- noqa: ST03
        select
            ld.student_number,
            ld.illuminate_student_id,
            ld.academic_year,
            ld.grade_level,
            ld.assessment_id,
            ld.assessment_title,
            ld.administration_round,
            ld.administered_at,
            ld.term_code,
            ld.subject_area,
            ld.number_of_questions,
            ld.overall_number_correct,
            ld.overall_percent_correct,
            ld.overall_performance_band,

            ssk.scale_score,
        from assessment_responses as ld
        left join
            {{ ref("stg_assessments__act_scale_score_key") }} as ssk
            on ld.academic_year = ssk.academic_year
            and ld.grade_level = ssk.grade_level
            and ld.term_code = ssk.administration_round
            and ld.subject_area = ssk.subject
            and ld.overall_number_correct
            between ssk.raw_score_low and ssk.raw_score_high
    ),

    overall_scores as (
        {{
            dbt_utils.deduplicate(
                relation="scaled",
                partition_by="student_number, academic_year, subject_area, term_code",
                order_by="overall_number_correct desc",
            )
        }}

        union all

        select
            student_number,
            illuminate_student_id,
            academic_year,
            grade_level,

            null as assessment_id,
            null as assessment_title,

            administration_round,

            min(administered_at) as administered_at,

            term_code,

            'Composite' as subject_area,

            sum(number_of_questions) as number_of_questions,
            sum(overall_number_correct) as overall_number_correct,
            round(
                (sum(overall_number_correct) / sum(number_of_questions)) * 100, 0
            ) as overall_percent_correct,
            null as overall_performance_band,
            if(count(scale_score) = 4, round(avg(scale_score), 0), null) as scale_score,
        from scaled
        group by
            student_number,
            illuminate_student_id,
            academic_year,
            grade_level,
            administration_round,
            term_code
    ),

    sub as (
        select
            student_number,
            illuminate_student_id,
            academic_year,
            grade_level,
            assessment_id,
            assessment_title,
            term_code,
            administration_round,
            administered_at,
            subject_area,
            number_of_questions,
            overall_number_correct,
            overall_percent_correct,
            overall_performance_band,
            scale_score,

            lag(scale_score, 1) over (
                partition by student_number, academic_year, subject_area
                order by administered_at
            ) as prev_scale_score,

            max(if(administration_round = 'Pre-Test', scale_score, null)) over (
                partition by student_number, academic_year, subject_area
            ) as pretest_scale_score,

            if(
                administration_round = 'Pre-Test',
                null,
                scale_score
            ) - max(if(administration_round = 'Pre-Test', scale_score, null)) over (
                partition by student_number, academic_year, subject_area
            ) as growth_from_pretest,

            row_number() over (
                partition by student_number, subject_area, academic_year
                order by term_code desc
            ) as rn_student_subject_year,
        from overall_scores
    )

select
    sub.student_number,
    sub.academic_year,
    sub.grade_level,
    sub.assessment_id,
    sub.assessment_title,
    sub.term_code,
    sub.administration_round,
    sub.administered_at,
    sub.subject_area,
    sub.number_of_questions,
    sub.overall_number_correct,
    sub.overall_percent_correct,
    sub.overall_performance_band,
    sub.scale_score,
    sub.prev_scale_score,
    sub.pretest_scale_score,
    sub.growth_from_pretest,
    sub.rn_student_subject_year,

    std.percent_correct as standard_percent_correct,
    std.mastered as standard_mastered,
    std.custom_code as standard_code,
    std.standard_description,
    std.root_standard_description as standard_strand,

    row_number() over (
        partition by
            sub.student_number,
            sub.subject_area,
            sub.academic_year,
            sub.administration_round
        order by sub.student_number asc
    ) as rn_student_assessment,
from sub
left join
    {{ ref("base_illuminate__agg_student_responses_standard") }} as std
    on sub.assessment_id = std.assessment_id
    and sub.illuminate_student_id = std.student_id
