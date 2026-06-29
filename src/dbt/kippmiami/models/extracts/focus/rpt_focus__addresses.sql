select
    student_id,
    address,
    address2,
    city,
    state,
    zipcode,
    phone,
    mailing,
    mail_address,
    mail_address2,
    mail_city,
    mail_state,
from {{ source("kipptaf_extracts", "rpt_focus__addresses") }}
