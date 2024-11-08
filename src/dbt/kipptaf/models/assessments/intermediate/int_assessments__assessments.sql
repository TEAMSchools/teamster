{#- TODO: drop previous years after migrating to appsheet table -#}
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
    iae.regions_report_card,
    iae.regions_progress_report,

    coalesce(iae.administered_at, a.administered_at) as administered_at,
    coalesce(iae.subject, a.subject_area) as subject_area,

    if(iae.assessment_id is not null, true, false) as is_internal_assessment,
from {{ ref("int_illuminate__assessments") }} as a
left join
    {{ ref("stg_google_appsheet__illuminate_assessments_extension") }} as iae
    on a.assessment_id = iae.assessment_id
where a.academic_year >= 2025  /* first year using appsheet table */

union all

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

    regexp_replace(
        coalesce(
            regexp_extract(a.title, ias.module_number_pattern_1 || r'\s?\d+'),
            regexp_extract(a.title, ias.module_number_pattern_2 || r'\s?\d+')
        ),
        r'\s',
        ''
    ) as module_code,

    ias.module_type,

    null as module_sequence,
    null as grade_level,
    null as illuminate_grade_level_id,

    case
        when left(a.title, 3) = 'FL-'
        then 'Miami'
        when right(a.title, 2) = 'FL'
        then 'Miami'
        else 'Newark,Camden,Miami'
    end as regions_assessed,

    null as regions_report_card,
    null as regions_progress_report,

    a.administered_at,
    a.subject_area,

    if(ias.scope is not null, true, false) as is_internal_assessment,
from {{ ref("int_illuminate__assessments") }} as a
left join
    /* hardcode disabled model */
    kipptaf_assessments.stg_assessments__internal_assessment_scopes as ias
    on a.scope = ias.scope
    and a.academic_year_clean = ias.academic_year
where a.academic_year < 2025 or a.academic_year is null
