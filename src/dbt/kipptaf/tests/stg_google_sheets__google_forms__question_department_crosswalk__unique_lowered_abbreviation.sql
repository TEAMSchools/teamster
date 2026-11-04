select lower(abbreviation) as abbreviation, count(*) as crosswalk_rows,
from {{ ref("stg_google_sheets__google_forms__question_department_crosswalk") }}
where abbreviation is not null
group by lower(abbreviation)
having count(*) > 1
