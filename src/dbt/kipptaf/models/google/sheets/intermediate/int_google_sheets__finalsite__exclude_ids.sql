select finalsite_student_id,
from {{ ref("stg_google_sheets__finalsite__exclude_ids") }}

union distinct

select text_value as finalsite_student_id,
from {{ ref("int_google_forms__form_responses") }}
where
    form_id = '1iH4Cjy_RIc8TWJf6Ts0sxhpVmCnx4paiT5RSNOS2Rn4'
    and text_value is not null
