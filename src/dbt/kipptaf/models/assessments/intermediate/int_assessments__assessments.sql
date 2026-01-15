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
