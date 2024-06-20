select
    region,
    academic_year,
    `quarter`,
    week_number,
    assignment_category_code,
    expectation,

    concat(assignment_category_code, right(`quarter`, 1)) as assignment_category_term,
from
    {{ source("reporting", "src_reporting__gradebook_expectations") }}
    unpivot (expectation for assignment_category_code in (`W`, `F`, `S`))
