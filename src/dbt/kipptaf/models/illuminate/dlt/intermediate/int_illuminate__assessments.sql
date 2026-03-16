select
    a.assessment_id,
    a.title,
    a.description,
    a.user_id,
    a.created_at,
    a.updated_at,
    a.administered_at,
    a.code_scope_id,
    a.code_subject_area_id,
    a.reports_db_virtual_table_id,
    a.academic_year,
    a.local_assessment_id,
    a.intel_assess_guid,
    a.guid,
    a.tags,
    a.edusoft_guid,
    a.performance_band_set_id,
    a.als_guid,
    a.curriculum_associate_guid,
    a.allow_duplicates,
    a.itembank_assessment_id,
    a.locked,
    a.show_in_parent_portal,
    a.administration_window_start_date,
    a.administration_window_end_date,
    a.is_hybrid_x_obsolete,
    a.assessment_type,
    a.duplicate_from_assessment_id,
    a.is_grade_k_1,

    u.local_user_id as creator_local_user_id,
    u.username as creator_username,
    u.first_name as creator_first_name,
    u.last_name as creator_last_name,
    u.email1 as creator_email_1,

    pbs.description as performance_band_set_description,

    dsa.code_translation as subject_area,

    a.academic_year - 1 as academic_year_clean,

    if(
        ds.code_translation in ('Cumulative Review Quizzes', 'Cold Read Quizzes')
        and a.is_grade_k_1,
        'Checkpoint',
        ds.code_translation
    ) as scope,
from {{ ref("stg_illuminate__dna_assessments__assessments") }} as a
inner join {{ ref("stg_illuminate__public__users") }} as u on a.user_id = u.user_id
inner join
    {{ ref("stg_illuminate__dna_assessments__performance_band_sets") }} as pbs
    on a.performance_band_set_id = pbs.performance_band_set_id
left join
    {{ ref("stg_illuminate__codes__dna_scopes") }} as ds on a.code_scope_id = ds.code_id
left join
    {{ ref("stg_illuminate__codes__dna_subject_areas") }} as dsa
    on a.code_subject_area_id = dsa.code_id
where a.deleted_at is null
