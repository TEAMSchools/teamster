select
    *,
    case
        when
            current_date('{{ var("local_timezone") }}')
            between `start_date` and end_date
        then true
        when
            end_date
            = max(end_date) over (partition by `type`, academic_year, school_id)
        then true
        else false
    end as is_current,
from {{ source("reporting", "src_reporting__terms") }}
where code is not null
