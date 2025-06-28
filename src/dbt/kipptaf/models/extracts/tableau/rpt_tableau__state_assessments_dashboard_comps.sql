select *
from {{ ref("int_tableau__state_assessments_demographic_comps_cubed") }}
where
    academic_year is not null and assessment_name is not null and test_code is not null
