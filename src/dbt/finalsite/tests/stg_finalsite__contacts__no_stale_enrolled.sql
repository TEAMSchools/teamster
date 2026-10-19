select finalsite_enrollment_id, status, school_year_start, grade_name,
from {{ ref("stg_finalsite__contacts") }}
where
    status = 'enrolled'
    and school_year_start < {{ var("current_academic_year") }}
    and grade_canonical_name is distinct from '12th'
