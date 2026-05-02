with
    scaffold_responses as (
        select
            s.illuminate_student_id,
            s.powerschool_student_number,
            s.assessment_id,
            s.title,
            s.scope,
            s.subject_area,
            s.discipline,
            s.academic_year,
            s.administered_at,
            s.module_type,
            s.module_code,
            s.region,
            s.performance_band_set_id,
            s.powerschool_school_id,
            s.grade_level_id,
            s.is_internal_assessment,
            s.is_replacement,
            s.student_assessment_id,
            s.date_taken,
            s.canonical_assessment_id,
            s.canonical_title,
            s.canonical_administered_at,
            s.canonical_performance_band_set_id,

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
            powerschool_school_id,
            region,
            canonical_assessment_id as assessment_id,
            is_internal_assessment,
            is_replacement,
            response_type,
            response_type_id,
            response_type_code,
            response_type_description,
            response_type_root_description,

            any_value(canonical_title) as title,
            any_value(canonical_administered_at) as administered_at,
            any_value(canonical_performance_band_set_id) as performance_band_set_id,
            any_value(academic_year) as academic_year,
            any_value(scope) as scope,
            any_value(subject_area) as subject_area,
            any_value(discipline) as discipline,
            any_value(module_type) as module_type,
            any_value(module_code) as module_code,

            min(grade_level_id) as grade_level_id,
            min(date_taken) as date_taken,

            count(distinct assessment_id) as n_assessments,

            sum(points) as points,

            array_agg(distinct assessment_id) as assessment_ids,

            round(
                safe_divide(sum(points), sum(points_possible)) * 100, 1
            ) as percent_correct,
        from scaffold_responses
        where is_internal_assessment
        group by
            illuminate_student_id,
            powerschool_student_number,
            powerschool_school_id,
            region,
            canonical_assessment_id,
            is_internal_assessment,
            is_replacement,
            response_type,
            response_type_id,
            response_type_code,
            response_type_description,
            response_type_root_description
    ),

    response_union as (
        select
            illuminate_student_id,
            powerschool_student_number,
            academic_year,
            scope,
            subject_area,
            discipline,
            module_type,
            module_code,
            region,
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
            n_assessments,
            assessment_ids,
            powerschool_school_id,
            title,
            assessment_id,
            administered_at,
            performance_band_set_id,

            if(n_assessments > 1, true, false) as is_multipart_assessment,
        from internal_assessment_rollup

        union all

        select
            illuminate_student_id,
            powerschool_student_number,
            academic_year,
            scope,
            subject_area,
            discipline,
            module_type,
            module_code,
            region,
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

            1 as n_assessments,

            [canonical_assessment_id] as assessment_ids,

            powerschool_school_id,
            canonical_title as title,
            canonical_assessment_id as assessment_id,
            canonical_administered_at as administered_at,
            canonical_performance_band_set_id as performance_band_set_id,

            false as is_multipart_assessment,
        from scaffold_responses
        where not is_internal_assessment
    )

select
    ru.illuminate_student_id,
    ru.powerschool_student_number,
    ru.academic_year,
    ru.scope,
    ru.subject_area,
    ru.discipline,
    ru.module_type,
    ru.module_code,
    ru.region,
    ru.powerschool_school_id,
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
    ru.n_assessments,
    ru.is_multipart_assessment,
    ru.assessment_ids,

    pbl.label as performance_band_label,
    pbl.label_number as performance_band_label_number,
    pbl.is_mastery,

    rta.name as term_administered,

    rtt.name as term_taken,
from response_union as ru
left join
    {{ ref("int_illuminate__performance_band_sets") }} as pbl
    on ru.performance_band_set_id = pbl.performance_band_set_id
    and ru.percent_correct between pbl.minimum_value and pbl.maximum_value
left join
    {{ ref("stg_google_sheets__reporting__terms") }} as rta
    on ru.administered_at between rta.start_date and rta.end_date
    and ru.powerschool_school_id = rta.school_id
    and rta.type = 'RT'
left join
    {{ ref("stg_google_sheets__reporting__terms") }} as rtt
    on ru.date_taken between rtt.start_date and rtt.end_date
    and ru.powerschool_school_id = rtt.school_id
    and rtt.type = 'RT'
