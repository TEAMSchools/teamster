select distinct mail as email,
from {{ ref("rpt_tableau__survey_completion") }}
where
    mail is not null
    and is_current
    and completion = 0
    and academic_year = {{ var("current_academic_year") }}
    and survey not in ('Gallup Q12 Survey', 'TNTP Insight')
