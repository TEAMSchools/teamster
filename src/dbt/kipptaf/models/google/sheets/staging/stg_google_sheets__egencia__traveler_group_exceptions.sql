select *, from {{ source("google_sheets", "src_egencia__traveler_group_exceptions") }}
