select
    academic_year, test_name, test_code, region, comparison_entity, percent_proficient,
from {{ source("assessments", "src_assessments__state_test_comparison") }}
