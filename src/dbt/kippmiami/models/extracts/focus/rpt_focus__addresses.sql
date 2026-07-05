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
        where
            f.student_id is null
            -- don't import a blank/partial address: presence-based import-once
            -- would create an empty Focus address record and then suppress the
            -- student forever, so the real address never syncs. Defer until the
            -- mailable address is complete. See #4320.
            and d.address is not null
            and d.city is not null
            and d.state is not null
            and d.zipcode is not null
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
