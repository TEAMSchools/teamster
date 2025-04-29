select
    academic_year,
    test_name,
    test_code,
    region,
    comparison_entity,
    percent_proficient,
    total_number_of_students,
from {{ source("assessments", "src_assessments__state_test_comparison") }}
