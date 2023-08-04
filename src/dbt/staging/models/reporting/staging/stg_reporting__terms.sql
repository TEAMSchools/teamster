select
    `type`,
    code,
    `name`,
    `start_date`,
    end_date,
    academic_year,
    fiscal_year,
    powerschool_year_id,
    powerschool_term_id,
    school_id,
    grade_band,
    case
        when current_date('America/New_York') between `start_date` and end_date
        then true
        when
            end_date
            = max(end_date) over (partition by `type`, academic_year, school_id)
        then true
        else false
    end as is_current,
from {{ source("reporting", "src_reporting__terms") }}
