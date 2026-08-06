with
    students as (
        select
            student_number,
            _dbt_source_project as code_location,

            cast(schoolid as string) as school_id,
        from {{ ref("int_extracts__student_enrollments") }}
        where
            -- Every NJ region is in scope and each district wrapper filters this
            -- view down to its own `code_location`. Miami is excluded because it
            -- rosters from Focus rather than PowerSchool — the same carve-out the
            -- six rpt_clever__* feeds make.
            _dbt_source_project != 'kippmiami'
            and academic_year = {{ var("current_academic_year") }}
            and rn_year = 1
            and not is_out_of_district
            and enroll_status in (0, -1)
    ),

    contact_source as (
        -- contact_1 and contact_2 are the Finalsite Household 1 parent slots.
        -- ParentSquare's parents file carries one voice fallback, so the typed
        -- home phone is preferred and work is the backstop.
        select
            student_number,
            contact_first_name,
            contact_last_name,
            relationship,
            email_current,
            phone_mobile,
            _dbt_source_project as code_location,

            coalesce(phone_home, phone_work) as phone_secondary,
        from {{ ref("int_students__contacts") }}
        where
            _dbt_source_project != 'kippmiami'
            and contact_slot in ('contact_1', 'contact_2')
    ),

    contact_digits as (
        -- int_students__contacts carries E.164 (+1..., optional xNNN extension)
        -- for Finalsite-sourced contacts. Reduce to digits so the truncation
        -- below operates on plain digits, and normalize a digitless value to null
        -- so it does not read as a phone number.
        select
            student_number,
            contact_first_name,
            contact_last_name,
            relationship,
            email_current,
            code_location,

            nullif(
                regexp_replace(phone_mobile, r'[^0-9]', ''), ''
            ) as phone_mobile_digits,
            nullif(
                regexp_replace(phone_secondary, r'[^0-9]', ''), ''
            ) as phone_secondary_digits,
        from contact_source
    ),

    contact_candidates as (
        -- Drop the US country code and keep 10 digits, which also truncates any
        -- extension digits the strip above concatenated onto the number.
        select
            student_number,
            contact_first_name,
            contact_last_name,
            relationship,
            email_current,
            code_location,

            left(
                regexp_replace(phone_mobile_digits, r'^1', ''), 10
            ) as mobile_candidate,
            left(
                regexp_replace(phone_secondary_digits, r'^1', ''), 10
            ) as secondary_candidate,
        from contact_digits
    ),

    contacts as (
        -- ParentSquare requires exactly 10 digits. A shorter value is an upstream
        -- data-entry typo, so drop the number rather than send one ParentSquare
        -- would reject along with the rest of the row.
        select
            student_number,
            contact_first_name,
            contact_last_name,
            relationship,
            email_current,
            code_location,

            if(length(mobile_candidate) = 10, mobile_candidate, null) as mobile,
            if(
                length(secondary_candidate) = 10, secondary_candidate, null
            ) as secondary_phone,
        from contact_candidates
    )

select
    c.contact_first_name as first_name,
    c.contact_last_name as last_name,
    c.relationship,
    c.mobile,
    c.secondary_phone,
    c.email_current as email,

    s.school_id,
    s.code_location,

    cast(s.student_number as string) as student_id,
from contacts as c
inner join
    students as s
    on c.student_number = s.student_number
    and c.code_location = s.code_location
-- ParentSquare needs an email or a mobile number to create a contactable parent
-- account, so a parent carrying neither is not deliverable and is dropped.
where c.email_current is not null or c.mobile is not null
