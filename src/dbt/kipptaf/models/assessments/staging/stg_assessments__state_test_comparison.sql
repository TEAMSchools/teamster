select * from {{ source("assessments", "src_assessments__state_test_comparison") }}
