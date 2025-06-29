select b.*,
from {{ ref("int_tableau__state_assessments_demographic_comps_cubed") }} as b
where
    b.academic_year is not null
    and b.assessment_name is not null
    and b.test_code is not null
    and b.district_state is not null
