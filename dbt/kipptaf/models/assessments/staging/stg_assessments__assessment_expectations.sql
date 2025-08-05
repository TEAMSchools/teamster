select *, from {{ source("assessments", "src_assessments__assessment_expectations") }}
