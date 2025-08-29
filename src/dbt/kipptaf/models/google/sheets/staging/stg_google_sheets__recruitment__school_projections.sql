select *,
from {{ source("google_sheets", "src_google_sheets__recruitment__school_projections") }}
