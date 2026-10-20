-- Illuminate realignment tracked in Asana 1219715733778308
select
    a.assessment_id,
    a.title,
    s.custom_code,
    s.description,

    count(distinct ast.standard_id) as standard_record_count,
from {{ ref("int_illuminate__assessments") }} as a
inner join
    {{ ref("stg_illuminate__dna_assessments__assessment_standards") }} as ast
    on a.assessment_id = ast.assessment_id
inner join
    {{ ref("stg_illuminate__standards__standards") }} as s
    on ast.standard_id = s.standard_id
where a.academic_year_clean = {{ var("current_academic_year") }}
group by a.assessment_id, a.title, s.custom_code, s.description
having count(distinct ast.standard_id) > 1
