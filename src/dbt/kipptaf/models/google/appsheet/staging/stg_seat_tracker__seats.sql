select
    * except (edited_at),

    coalesce(
        safe.parse_timestamp('%m/%d/%Y %T', edited_at, '{{ var("local_timezone") }}'),
        safe.parse_timestamp(
            '%a %b %d %Y %T', left(edited_at, 24), '{{ var("local_timezone") }}'
        )
    ) as edited_at,
from {{ source("google_appsheet", "src_seat_tracker__seats") }}
where academic_year is not null
