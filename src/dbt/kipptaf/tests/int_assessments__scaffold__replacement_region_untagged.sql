select
    source,
    assessment_id,
    region,
    powerschool_school_id,
    student_number,
    illuminate_student_id,
    student_assessment_id,
    canonical_assessment_id,
from {{ ref("int_assessments__scaffold") }}
where is_internal_assessment and is_replacement and not is_region_tagged
