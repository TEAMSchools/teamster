select
    page_id,
    page_fans,
    page_fan_adds,
    page_fan_removes,
    safe_cast(date as date) as `date`,
from {{ source("facebook_pages", "daily_page_metrics_total") }}
