with
    agl_dedup as (
        select assessment_id, min(grade_level_id) as grade_level_id,
        from {{ ref("stg_illuminate__dna_assessments__assessment_grade_levels") }}
        group by assessment_id
    ),

    extended as (
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
            iae.illuminate_grade_level_id as tagged_grade_level_id,
            iae.regions_assessed,
            iae.regions_assessed_array,
            iae.regions_report_card,
            iae.regions_progress_report,

            'illuminate' as `source`,

            coalesce(iae.administered_at, a.administered_at) as administered_at,
            coalesce(iae.subject, a.subject_area) as subject_area,
            coalesce(
                iae.illuminate_grade_level_id, agl.grade_level_id
            ) as grade_level_id,

            if(iae.assessment_id is not null, true, false) as is_internal_assessment,
            if(iae.regions_assessed = 'Miami', true, false) as is_florida_assessment,
        from {{ ref("int_illuminate__assessments") }} as a
        left join
            {{ ref("stg_google_appsheet__illuminate_assessments_extension") }} as iae
            on a.assessment_id = iae.assessment_id
            and iae.source = 'illuminate'
        left join agl_dedup as agl on a.assessment_id = agl.assessment_id

        union all

        -- Apex is Miami-only, so it is internal and Florida with or without a tag
        select
            aa.assessment_id,
            aa.title,

            aa.academic_year + 1 as academic_year,

            aa.academic_year as academic_year_clean,

            cast(null as string) as scope,
            cast(null as string) as creator_first_name,
            cast(null as string) as creator_last_name,

            aa.band_set_id as performance_band_set_id,

            cast(null as string) as assessment_type,
            cast(null as string) as tags,

            iae.module_code,
            iae.module_type,
            iae.module_sequence,
            iae.illuminate_grade_level_id as tagged_grade_level_id,

            coalesce(iae.regions_assessed, 'Miami') as regions_assessed,
            coalesce(iae.regions_assessed_array, ['Miami']) as regions_assessed_array,

            iae.regions_report_card,
            iae.regions_progress_report,

            'apex' as `source`,

            coalesce(iae.administered_at, aa.administered_at) as administered_at,
            coalesce(iae.subject, aa.subject_area) as subject_area,

            iae.illuminate_grade_level_id as grade_level_id,

            true as is_internal_assessment,
            true as is_florida_assessment,
        from {{ ref("int_focus__apex_assessments") }} as aa
        left join
            {{ ref("stg_google_appsheet__illuminate_assessments_extension") }} as iae
            on aa.assessment_id = iae.assessment_id
            and iae.source = 'apex'
        -- keep in step with int_assessments__scaffold (apex_tested)
        where aa.academic_year >= 2026
    ),

    canonical as (
        select
            source,
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
            tagged_grade_level_id,
            regions_assessed,
            regions_assessed_array,
            regions_report_card,
            regions_progress_report,
            administered_at,
            subject_area,
            grade_level_id,
            is_internal_assessment,

            -- untagged Apex assessments share null tags, so grouping them would
            -- merge unrelated assessments; each is its own canonical group
            if(
                is_internal_assessment and source = 'illuminate',
                first_value(assessment_id) over canonical_w,
                assessment_id
            ) as canonical_assessment_id,
        from extended
        window
            canonical_w as (
                partition by
                    source,
                    is_internal_assessment,
                    is_florida_assessment,
                    academic_year,
                    scope,
                    subject_area,
                    module_code,
                    grade_level_id
                order by assessment_id
            )
    )

select
    source,
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
    tagged_grade_level_id,
    regions_assessed,
    regions_assessed_array,
    regions_report_card,
    regions_progress_report,
    administered_at,
    subject_area,
    grade_level_id,
    is_internal_assessment,
    canonical_assessment_id,
from canonical
