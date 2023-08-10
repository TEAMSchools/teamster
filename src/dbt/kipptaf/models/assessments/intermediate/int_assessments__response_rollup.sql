with
    scaffold_responses as (
        select
            s.illuminate_student_id,
            s.powerschool_student_number,
            s.assessment_id,
            s.title,
            s.scope,
            s.subject_area,
            s.academic_year,
            s.administered_at,
            s.module_type,
            s.module_number,
            s.performance_band_set_id,
            s.powerschool_school_id,
            s.grade_level_id,
            s.is_internal_assessment,
            s.is_replacement,
            s.student_assessment_id,
            s.date_taken,

            asr.response_type,
            asr.response_type_id,
            asr.response_type_code,
            asr.response_type_description,
            asr.response_type_root_description,
            asr.points_possible,
            asr.points,
            asr.percent_correct,
        from {{ ref("int_assessments__scaffold") }} as s
        left join
            {{ ref("int_illuminate__agg_student_responses") }} as asr
            on s.student_assessment_id = asr.student_assessment_id
    ),

    internal_assessment_rollup as (
        select
            illuminate_student_id,
            powerschool_student_number,
            academic_year,
            scope,
            subject_area,
            module_type,
            module_number,
            is_internal_assessment,
            is_replacement,
            response_type,
            response_type_id,
            response_type_code,
            response_type_description,
            response_type_root_description,
            powerschool_school_id,
            min(assessment_id) as assessment_id,
            min(title) as title,
            min(grade_level_id) as grade_level_id,
            min(administered_at) as administered_at,
            min(performance_band_set_id) as performance_band_set_id,
            min(date_taken) as date_taken,
            sum(points) as points,
            round(
                safe_divide(sum(points), sum(points_possible)) * 100, 1
            ) as percent_correct,
        from scaffold_responses
        where is_internal_assessment
        group by
            illuminate_student_id,
            powerschool_student_number,
            academic_year,
            scope,
            subject_area,
            module_type,
            module_number,
            is_internal_assessment,
            is_replacement,
            response_type,
            response_type_id,
            response_type_code,
            response_type_description,
            response_type_root_description,
            powerschool_school_id
    ),

    response_union as (
        select
            illuminate_student_id,
            powerschool_student_number,
            academic_year,
            scope,
            subject_area,
            module_type,
            module_number,
            is_internal_assessment,
            is_replacement,
            response_type,
            response_type_id,
            response_type_code,
            response_type_description,
            response_type_root_description,
            date_taken,
            points,
            percent_correct,
            powerschool_school_id,
            if(
                not is_replacement,
                min(title) over (
                    partition by
                        academic_year,
                        scope,
                        subject_area,
                        module_number,
                        grade_level_id,
                        is_replacement
                ),
                title
            ) as title,
            if(
                not is_replacement,
                min(assessment_id) over (
                    partition by
                        academic_year,
                        scope,
                        subject_area,
                        module_number,
                        grade_level_id,
                        is_replacement
                ),
                assessment_id
            ) as assessment_id,
            if(
                not is_replacement,
                min(administered_at) over (
                    partition by
                        academic_year,
                        scope,
                        subject_area,
                        module_number,
                        grade_level_id,
                        is_replacement
                ),
                administered_at
            ) as administered_at,
            if(
                not is_replacement,
                min(performance_band_set_id) over (
                    partition by
                        academic_year,
                        scope,
                        subject_area,
                        module_number,
                        grade_level_id,
                        is_replacement,
                        response_type,
                        response_type_id
                ),
                performance_band_set_id
            ) as performance_band_set_id,
        from internal_assessment_rollup

        union all

        select
            illuminate_student_id,
            powerschool_student_number,
            academic_year,
            scope,
            subject_area,
            module_type,
            module_number,
            is_internal_assessment,
            is_replacement,
            response_type,
            response_type_id,
            response_type_code,
            response_type_description,
            response_type_root_description,
            date_taken,
            points,
            percent_correct,
            powerschool_school_id,
            title,
            assessment_id,
            administered_at,
            performance_band_set_id,
        from scaffold_responses
        where not is_internal_assessment
    )

select
    ru.illuminate_student_id,
    ru.powerschool_student_number,
    ru.academic_year,
    ru.scope,
    ru.subject_area,
    ru.module_type,
    ru.module_number,
    ru.is_internal_assessment,
    ru.is_replacement,
    ru.response_type,
    ru.response_type_id,
    ru.response_type_code,
    ru.response_type_description,
    ru.response_type_root_description,
    ru.date_taken,
    ru.points,
    ru.percent_correct,
    ru.title,
    ru.assessment_id,
    ru.administered_at,
    ru.performance_band_set_id,

    pbl.label as performance_band_label,
    pbl.label_number as performance_band_label_number,
    pbl.is_mastery,

    rta.name as term_administered,

    rtt.name as term_taken,
from response_union as ru
left join
    {{ ref("base_illuminate__performance_band_sets") }} as pbl
    on ru.performance_band_set_id = pbl.performance_band_set_id
    and ru.percent_correct between pbl.minimum_value and pbl.maximum_value
left join
    {{ ref("stg_reporting__terms") }} as rta
    on ru.administered_at between rta.start_date and rta.end_date
    and ru.powerschool_school_id = rta.school_id
    and rta.type = 'RT'
left join
    {{ ref("stg_reporting__terms") }} as rtt
    on ru.date_taken between rtt.start_date and rtt.end_date
    and ru.powerschool_school_id = rtt.school_id
    and rtt.type = 'RT'
