select *, from {{ source("reporting", "src_reporting__promo_status_cutoffs") }}
