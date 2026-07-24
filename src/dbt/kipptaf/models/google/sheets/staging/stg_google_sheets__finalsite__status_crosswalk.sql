select *, cast(left(_dagster_partition_key, 4) as int) as file_year,

from {{ source("google_sheets", "src_google_sheets__finalsite__status_crosswalk") }}
