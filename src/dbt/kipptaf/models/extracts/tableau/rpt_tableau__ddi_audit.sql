with
    grade_level as (
        select assessment_id, min(grade_level) as grade_level,
        from {{ ref("stg_illuminate__assessment_grade_levels") }}
        group by assessment_id
    )

select
    a.academic_year_clean as academic_year,
    a.assessment_id,
    a.title as assessment_title,
    a.subject_area as illuminate_subject_area,
    a.administered_at as date_first_administered,
    a.assessment_type,
    a.scope,
    a.module_type,
    a.module_code as module_number,

    g.grade_level,

    s.custom_code,
    s.description,

    rt.name as term_administered,

    ps.is_power_standard,

    coalesce(ps.qbl, 'No QBL mapped') as qbl,
from {{ ref("int_assessments__assessments") }} as a
left join grade_level as g on a.assessment_id = g.assessment_id
left join
    {{ ref("stg_illuminate__assessment_standards") }} as st
    on a.assessment_id = st.assessment_id
left join {{ ref("stg_illuminate__standards") }} as s on st.standard_id = s.standard_id
left join
    {{ ref("stg_reporting__terms") }} as rt
    on a.administered_at between rt.start_date and rt.end_date
    and rt.school_id = 0
    and rt.type = 'RT'
left join
    {{ ref("stg_assessments__qbls_power_standards") }} as ps
    on s.custom_code = ps.standard_code
    and rt.name = ps.term_name
    and a.subject_area = ps.illuminate_subject_area
    and g.grade_level = ps.grade_level
where
    a.scope in (
        'Cumulative Review Quizzes',
        'Cold Read Quizzes',
        'CMA - End-of-Module',
        'Mid-quarter quiz',
        'Power Standard Pre Quiz'
    )
    and a.academic_year_clean = {{ var("current_academic_year") }}
    and g.grade_level < 9

union all

select
    a.academic_year_clean as academic_year,
    a.assessment_id,
    a.title as assessment_title,
    a.subject_area as illuminate_subject_area,
    a.administered_at as date_first_administered,
    a.assessment_type,
    a.scope,
    a.module_type,
    a.module_code as module_number,

    g.grade_level,

    s.custom_code,
    s.description,

    rt.name as term_administered,

    ps.is_power_standard,

    coalesce(ps.qbl, 'No QBL mapped') as qbl,
from {{ ref("int_assessments__assessments") }} as a
left join grade_level as g on a.assessment_id = g.assessment_id
left join
    {{ ref("stg_illuminate__assessment_standards") }} as st
    on a.assessment_id = st.assessment_id
left join {{ ref("stg_illuminate__standards") }} as s on st.standard_id = s.standard_id
left join
    {{ ref("stg_reporting__terms") }} as rt
    on a.administered_at between rt.start_date and rt.end_date
    and rt.school_id = 0
    and rt.type = 'RT'
left join
    {{ ref("stg_assessments__qbls_power_standards") }} as ps
    on s.custom_code = ps.standard_code
    and rt.name = ps.term_name
    and a.subject_area = ps.illuminate_subject_area
where
    a.scope in ('HS Unit Quiz', 'Midterm or Final', 'Power Standard Pre Quiz')
    and a.academic_year_clean = {{ var("current_academic_year") }}
    and g.grade_level > 8
