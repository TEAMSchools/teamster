select
    region,
    school_level,
    academic_year,
    `quarter`,
    week_number,
    assignment_category_code,
    expectation,
    notes,

    concat(assignment_category_code, right(`quarter`, 1)) as assignment_category_term,

    case
        assignment_category_code
        when 'W'
        then 'Work Habits'
        when 'F'
        then 'Formative Mastery'
        when 'S'
        then 'Summative Mastery'
    end as assignment_category_name,
from
    {{ source("reporting", "src_reporting__gradebook_expectations") }}
    unpivot (expectation for assignment_category_code in (`W`, `F`, `S`))
