select *, fiscal_year - 1 as academic_year,
from {{ source("finance", "src_finance__enrollment_targets") }}
where fiscal_year is not null
