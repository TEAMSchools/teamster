select *,
from {{ source("assessments", "src_assessments__state_test_comparison") }}
where total_number_of_students is not null
