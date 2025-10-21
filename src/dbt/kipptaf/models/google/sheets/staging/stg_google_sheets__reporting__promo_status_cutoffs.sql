select *,
from {{ source("google_sheets", "src_google_sheets__reporting__promo_status_cutoffs") }}
