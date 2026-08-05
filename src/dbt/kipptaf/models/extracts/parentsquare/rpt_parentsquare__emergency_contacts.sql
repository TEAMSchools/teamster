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
        -- emergency_1..4 are the Finalsite emergency-contact custom-field sets.
        -- ParentSquare's emergency file carries one phone, so collapse the typed
        -- columns to a single best number, mobile first.
        select
            student_number,
            contact_slot,
            contact_first_name,
            contact_last_name,
            email_current,
            _dbt_source_project as code_location,

            coalesce(phone_mobile, phone_home, phone_work, phone_primary) as phone_best,
        from {{ ref("int_students__contacts") }}
        where _dbt_source_project != 'kippmiami' and contact_slot like 'emergency_%'
    ),

    contact_digits as (
        -- Reduce to digits so the truncation below operates on plain digits, and
        -- normalize a digitless value to null so it does not read as a phone
        -- number.
        select
            student_number,
            contact_slot,
            contact_first_name,
            contact_last_name,
            email_current,
            code_location,

            nullif(regexp_replace(phone_best, r'[^0-9]', ''), '') as phone_digits,
        from contact_source
    ),

    contact_candidates as (
        -- Drop the US country code and keep 10 digits, which also truncates any
        -- extension digits the strip above concatenated onto the number.
        select
            student_number,
            contact_slot,
            contact_first_name,
            contact_last_name,
            email_current,
            code_location,

            left(regexp_replace(phone_digits, r'^1', ''), 10) as phone_candidate,
        from contact_digits
    ),

    contacts as (
        -- `contact_id` is keyed on (student, slot) rather than on
        -- `finalsite_contact_id`, which is null for every emergency row: these
        -- are scalar custom fields on the student's own Finalsite record, not
        -- linked contact records, so (student, slot) is the true grain. The key
        -- needs no region component — `student_number` is unique across the NJ
        -- regions this view covers.
        --
        -- ParentSquare requires exactly 10 digits. A shorter value is an upstream
        -- data-entry typo, so drop the number rather than send one ParentSquare
        -- would reject along with the rest of the row.
        select
            student_number,
            contact_first_name,
            contact_last_name,
            email_current,
            code_location,

            {{ dbt_utils.generate_surrogate_key(["student_number", "contact_slot"]) }}
            as contact_id,

            if(length(phone_candidate) = 10, phone_candidate, null) as phone,
        from contact_candidates
    )

select
    c.contact_id,
    c.contact_first_name as first_name,
    c.contact_last_name as last_name,
    c.phone,
    c.email_current as email,

    s.school_id,
    s.code_location,

    cast(s.student_number as string) as student_id,
from contacts as c
inner join
    students as s
    on c.student_number = s.student_number
    and c.code_location = s.code_location
-- ParentSquare needs an email or a phone to reach an emergency contact with Smart
-- and Urgent Alerts, so a contact carrying neither is dropped.
where c.email_current is not null or c.phone is not null
