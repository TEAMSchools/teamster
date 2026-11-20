select distinct mail as email,
from {{ ref("rpt_tableau__survey_completion") }}
where
    mail is not null
    and is_current
    and completion = 0
    and survey != 'Leader Intent to Return Survey'
    and academic_year = {{ var("current_academic_year") }}
