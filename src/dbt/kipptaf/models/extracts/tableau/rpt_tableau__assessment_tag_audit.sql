with
    standards_grouped as (
        select fs.field_id, string_agg(s.custom_code, '; ') as standard_codes,
        from {{ ref("stg_illuminate__field_standards") }} as fs
        inner join
            {{ ref("stg_illuminate__standards") }} as s
            on fs.standard_id = s.standard_id
        group by fs.field_id
    ),

    fields_reporting_groups as (
        select rg.label, frg.field_id, frg.reporting_group_id,
        from {{ ref("stg_illuminate__reporting_groups") }} as rg
        inner join
            {{ ref("stg_illuminate__fields_reporting_groups") }} as frg
            on rg.reporting_group_id = frg.reporting_group_id
        where
            rg.label
            in ('Multiple Choice', 'Open Ended Response', 'Open-Ended Response')
    ),

    assessment_grade_levels as (
        select agl.assessment_id, gr.short_name,
        from {{ ref("stg_illuminate__assessment_grade_levels") }} as agl
        inner join
            {{ ref("stg_illuminate__grade_levels") }} as gr
            on agl.grade_level_id = gr.grade_level_id
    )

select
    a.assessment_id,
    a.title,
    a.academic_year_clean as academic_year,
    a.administered_at,
    a.scope,
    a.subject_area,
    a.tags,
    a.creator_first_name || ' ' || a.creator_last_name as created_by,
    a.module_type,
    a.module_number,
    a.is_internal_assessment as is_normed_scope,

    f.field_id,
    f.sheet_label as question_number,
    f.maximum as question_points_possible,
    f.extra_credit as question_extra_credit,
    f.is_rubric as question_is_rubric,

    pbs.description as performance_band_set_description,

    agl.short_name as assessment_grade_level,

    frg.label as question_reporting_group,

    sg.standard_codes as question_standard_codes,
from {{ ref("base_assessments__assessments") }} as a
inner join
    {{ ref("stg_illuminate__assessment_fields") }} as f
    on a.assessment_id = f.assessment_id
left join
    {{ ref("stg_illuminate__performance_band_sets") }} as pbs
    on a.performance_band_set_id = pbs.performance_band_set_id
left join assessment_grade_levels as agl on a.assessment_id = agl.assessment_id
left join fields_reporting_groups as frg on f.field_id = frg.field_id
left join standards_grouped as sg on f.field_id = sg.field_id
