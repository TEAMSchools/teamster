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
        select
            student_number,
            contact_first_name,
            contact_last_name,
            relationship,
            email_current,
            _dbt_source_project as code_location,

            coalesce(phone_mobile, phone_untyped) as phone_mobile,
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
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    deliverable as (
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

            (
                if(c.mobile is not null, 1, 0)
                + if(c.secondary_phone is not null, 1, 0)
                + if(c.email_current is not null, 1, 0)
            ) as contactable_fields,
        from contacts as c
        inner join
            students as s
            on c.student_number = s.student_number
            and c.code_location = s.code_location
        where c.email_current is not null or c.mobile is not null
    ),

    -- TODO(#4776): Finalsite holds duplicate contact records for one human --
    -- two finalsite_enrollment_ids, same person -- and both qualify as parent
    -- candidates, so int_finalsite__student_contacts ranks them into contact_1
    -- AND contact_2 for the same student. Nine Newark students are affected,
    -- and this feed would create duplicate ParentSquare accounts for their
    -- parents. The upstream fix is to rank one row per PERSON rather than per
    -- contact record; until that lands, collapse here on the grain ParentSquare
    -- itself keys on, preferring the row carrying the most contact detail so a
    -- merge never drops a phone number or email the other copy had.
    --
    -- Two genuinely different people who share a name for one student would
    -- also collapse. That is the destination's constraint, not a choice this
    -- model makes -- ParentSquare cannot represent them separately either.
    deduped as (
        {{
            dbt_utils.deduplicate(
                relation="deliverable",
                partition_by="student_id, first_name, last_name",
                order_by="contactable_fields desc",
            )
        }}
    )

select
    first_name,
    last_name,
    relationship,
    mobile,
    secondary_phone,
    email,
    school_id,
    code_location,
    student_id,
from deduped
