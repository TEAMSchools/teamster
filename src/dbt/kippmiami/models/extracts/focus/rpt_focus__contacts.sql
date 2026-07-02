with
    -- students who already have a contact (person) in Focus; import once
    focus_contact as (
        select distinct cast(student_id as string) as student_id,
        from {{ ref("stg_focus__students_join_people") }}
    ),

    diffed as (
        select d.*,
        from {{ source("kipptaf_extracts", "rpt_focus__contacts") }} as d
        left join focus_contact as f on d.student_id = f.student_id
        where
            f.student_id is null
            -- don't import a nameless contact: presence-based import-once would
            -- create the Focus person record and then suppress the student
            -- forever, so a later-named contact never syncs. Unlike the address
            -- fields, first_name / last_name are NOT nullif-normalized upstream
            -- in stg_finalsite__contacts, and Finalsite emits empty strings for
            -- unset names, so guard against blank/whitespace here. See #4320.
            and (
                nullif(trim(d.first_name), '') is not null
                or nullif(trim(d.last_name), '') is not null
            )
    )

select
    student_id,
    student_relation,
    sort_order,
    first_name,
    middle_name,
    last_name,
    resides_with_stud,
    custody,
    emergency,
    pickup,
    address,
    address2,
    city,
    state,
    zipcode,
    email,
    contact1_type,
    contact1_value,
    contact1_blocked,
    contact1_unlisted,
    contact1_callout,
    contact2_type,
    contact2_value,
    contact2_blocked,
    contact2_unlisted,
    contact2_callout,
    contact3_type,
    contact3_value,
    contact3_blocked,
    contact3_unlisted,
    contact3_callout,
    contact4_type,
    contact4_value,
    contact4_blocked,
    contact4_unlisted,
    contact4_callout,
    contact5_type,
    contact5_value,
    contact5_blocked,
    contact5_unlisted,
    contact5_callout,
    contact6_type,
    contact6_value,
    contact6_blocked,
    contact6_unlisted,
    contact6_callout,
    contact7_type,
    contact7_value,
    contact7_blocked,
    contact7_unlisted,
from diffed
