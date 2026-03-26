select
    sar.student_assessment_response_id,
    sar.student_assessment_id,
    sar.assessment_id,
    sar.version_id,
    sar.field_id,

    f.`order` as field_order,

    sar.response_id,
    r.response,

    fr.points > 0 as is_correct,
    fr.points,
    sar.manual_score,
from {{ ref("stg_illuminate__dna_assessments__students_assessments_responses") }} as sar
inner join
    {{ ref("stg_illuminate__dna_assessments__responses") }} as r
    on sar.response_id = r.response_id
inner join
    {{ ref("stg_illuminate__dna_assessments__field_responses") }} as fr
    on sar.field_id = fr.field_id
    and sar.response_id = fr.response_id
    and sar.version_id = fr.version_id
inner join
    {{ ref("stg_illuminate__dna_assessments__fields") }} as f
    on sar.field_id = f.field_id
