select
    finalsite_student_id,
    enrollment_year,
    enrollment_type,
    `status`,
    last_name,
    first_name,
    grade_level,
    school,

    cast(powerschool_student_number as int) as powerschool_student_number,

    cast(left(enrollment_year, 4) as int) as academic_year,

    parse_date('%m/%d/%y', `timestamp`) as effective_date,
from {{ source("finalsite", "status_report") }}
