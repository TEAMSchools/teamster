select *,
from {{ source("assessments", "src_assessments__college_readiness_expected_tests") }}
