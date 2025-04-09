select distinct preferred_name_lastfirst as `name`, mail as email,
from {{ ref("rpt_tableau__survey_completion") }}
where
    is_current and completion = 0 and academic_year = {{ var("current_academic_year") }}
