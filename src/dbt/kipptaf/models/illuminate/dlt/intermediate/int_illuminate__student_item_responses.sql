select
    sa.student_assessment_id,
    sa.student_id,
    sa.assessment_id,
    sa.date_taken,
    sa.created_at,
    sa.updated_at,

    sar.student_assessment_response_id,
    sar.manual_score,

    f.sheet_label,
    f.body,
    f.maximum,
    f.factor,
    f.field_order,
    f.is_rubric,
    f.is_advanced,
    f.is_extra_credit,
    f.is_partial_score,

    r.response,

    fr.points,
    fr.points > 0 as is_correct,
from {{ ref("stg_illuminate__dna_assessments__students_assessments") }} as sa
inner join
    {{ ref("stg_illuminate__dna_assessments__students_assessments_responses") }} as sar
    on sa.student_assessment_id = sar.student_assessment_id
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
