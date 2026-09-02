-- Every Focus section should resolve a lead teacher through the staff roster
-- (by ein, falling back to email). Scoped to the Focus population by year --
-- int_students__course_sections also carries the frozen Miami PowerSchool
-- archive under _dbt_source_project = 'kippmiami', and that history predates
-- the staff roster and will never resolve. See properties.yml for what the
-- current floor is made of.
with
    focus_academic_year_boundary as (
        select min(academic_year) as min_academic_year,
        from {{ ref("int_focus__schedule") }}
    )

select cs.sections_dcid, cs._dbt_source_project,
from {{ ref("int_students__course_sections") }} as cs
cross join focus_academic_year_boundary as fay
where
    cs._dbt_source_project = 'kippmiami'
    and cs.teachernumber is null
    and cs.terms_academic_year >= fay.min_academic_year
