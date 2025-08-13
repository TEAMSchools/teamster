select
    * except (region),

    case
        when region in ('Newark', 'TEAM Academy Charter School')
        then 'Newark'
        when region in ('Camden', 'KIPP Cooper Norcross Academy')
        then 'Camden'
        when region in ('KIPP Miami', 'Miami')
        then 'Miami'
        when region in ('KIPP Paterson')
        then 'Paterson'
    end as city,

    case
        when
            current_date('{{ var("local_timezone") }}')
            between `start_date` and end_date
        then true
        when
            academic_year < {{ var("current_academic_year") }}
            and end_date
            = max(end_date) over (partition by `type`, academic_year, school_id)
        then true
        else false
    end as is_current,
from {{ source("reporting", "src_reporting__terms") }}
where code is not null
