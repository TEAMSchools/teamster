-- Scoped to the Focus population by year: int_students__course_sections also
-- carries the frozen Miami PowerSchool archive under
-- _dbt_source_project = 'kippmiami', which predates the staff roster.
with
    focus_academic_year_boundary as (
        select min(academic_year) as min_academic_year,
        from {{ ref("int_focus__schedule") }}
    )

select
    cs.sections_dcid,
    cs.sections_schoolid,
    cs.terms_academic_year,
    cs._dbt_source_project,

    cp.period_id,
    cp.teacher_id,
from {{ ref("int_students__course_sections") }} as cs
cross join focus_academic_year_boundary as fay
inner join
    {{ ref("int_focus__course_periods") }} as cp
    on cs.sections_dcid = cp.course_period_id
    and cs._dbt_source_project = cp._dbt_source_project
where
    cs._dbt_source_project = 'kippmiami'
    and cs.teachernumber is null
    and cs.terms_academic_year >= fay.min_academic_year
    and cp.teacher_id is not null
