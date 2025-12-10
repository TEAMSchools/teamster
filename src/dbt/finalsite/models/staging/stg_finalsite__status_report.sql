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

    cast(`timestamp` as date) as effective_date,

    cast(left(enrollment_year, 4) as int) as academic_year,
from {{ source("finalsite", "status_report") }}
