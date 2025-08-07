select
    *,

    case
        when audit_flag_name in ('qt_effort_grade_missing', 'w_grade_inflation')
        then 'W'
        when audit_flag_name = 'qt_formative_grade_missing'
        then 'F'
        when audit_flag_name = 'qt_summative_grade_missing'
        then 'S'
    end as alt_code,

from {{ source("google_sheets", "src_google_sheets__gradebook_flags") }}
