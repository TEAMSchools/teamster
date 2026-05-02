with
    raw as (
        select
            a.assessment_id,
            a.title,
            a.academic_year,
            a.academic_year_clean,
            a.scope,
            a.creator_first_name,
            a.creator_last_name,
            a.performance_band_set_id,
            a.assessment_type,
            a.tags,

            iae.module_code,
            iae.module_type,
            iae.module_sequence,
            iae.grade_level,
            iae.illuminate_grade_level_id,
            iae.regions_assessed,
            iae.regions_assessed_array,
            iae.regions_report_card,
            iae.regions_progress_report,

            coalesce(iae.administered_at, a.administered_at) as administered_at,
            coalesce(iae.subject, a.subject_area) as subject_area,

            if(iae.assessment_id is not null, true, false) as is_internal_assessment,
        from {{ ref("int_illuminate__assessments") }} as a
        left join
            {{ ref("stg_google_appsheet__illuminate_assessments_extension") }} as iae
            on a.assessment_id = iae.assessment_id
    )

select
    assessment_id,
    title,
    academic_year,
    academic_year_clean,
    scope,
    creator_first_name,
    creator_last_name,
    performance_band_set_id,
    assessment_type,
    tags,
    module_code,
    module_type,
    module_sequence,
    grade_level,
    illuminate_grade_level_id,
    regions_assessed,
    regions_assessed_array,
    regions_report_card,
    regions_progress_report,
    administered_at,
    subject_area,
    is_internal_assessment,

    if(
        is_internal_assessment,
        first_value(assessment_id) over (
            partition by
                is_internal_assessment, academic_year, subject_area, module_code
            order by assessment_id
        ),
        assessment_id
    ) as canonical_assessment_id,

    if(
        is_internal_assessment,
        first_value(title) over (
            partition by
                is_internal_assessment, academic_year, subject_area, module_code
            order by assessment_id
        ),
        title
    ) as canonical_title,

    if(
        is_internal_assessment,
        first_value(administered_at) over (
            partition by
                is_internal_assessment, academic_year, subject_area, module_code
            order by assessment_id
        ),
        administered_at
    ) as canonical_administered_at,

    if(
        is_internal_assessment,
        first_value(performance_band_set_id) over (
            partition by
                is_internal_assessment, academic_year, subject_area, module_code
            order by assessment_id
        ),
        performance_band_set_id
    ) as canonical_performance_band_set_id,
from raw
