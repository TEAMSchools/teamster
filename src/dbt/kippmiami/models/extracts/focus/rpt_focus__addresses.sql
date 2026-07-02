with
    -- students who already have an address in Focus; import once, never overwrite
    focus_address as (
        select distinct cast(student_id as string) as student_id,
        from {{ ref("stg_focus__students_join_address") }}
    ),

    diffed as (
        select d.*,
        from {{ source("kipptaf_extracts", "rpt_focus__addresses") }} as d
        left join focus_address as f on d.student_id = f.student_id
        where f.student_id is null
    )

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
from diffed
