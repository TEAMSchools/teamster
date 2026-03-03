select *
from {{ ref("stg_google_sheets__gradebook_exceptions") }}
where is_quarter_end_date_range is null
