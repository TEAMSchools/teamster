select *, cast(regexp_extract(respondent_name, r'(\d{6})') as int) as employee_number,
from {{ source("surveys", "src_surveys__staff_info_archive") }}
