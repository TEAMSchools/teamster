select
    school_id,
    school_name,
    school_zip,
    school_address,
    school_city,
    school_state,
    principal_email,
    school_phone,
    principal_first_name,
    principal_last_name,
from {{ source("kipptaf_extracts", "rpt_parentsquare__schools") }}
where code_location = '{{ project_name }}'
