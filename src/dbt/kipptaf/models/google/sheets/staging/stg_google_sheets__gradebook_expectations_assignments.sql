select
    *,

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
    {{
        source(
            "google_sheets", "src_google_sheets__gradebook_expectations_assignments"
        )
    }} unpivot (expectation for assignment_category_code in (`W`, `F`, `S`))
