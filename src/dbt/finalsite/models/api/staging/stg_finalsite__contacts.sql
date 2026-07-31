select
    id as finalsite_enrollment_id,
    first_name,
    middle_name,
    last_name,
    full_name,
    preferred_name,
    email,
    gender,
    gender_display,
    gender_full_text,
    status,
    enrollment_type,
    inquiry_submit_date,
    application_submit_date,
    contract_submit_date,

    grade.canonical_name as grade_canonical_name,
    grade.name as grade_name,
    grade.school_level as grade_school_level,

    prospect_entry_grade.canonical_name as prospect_entry_grade_canonical_name,

    school_year.start_year as school_year_start,
    prospect_entry_year.start_year as prospect_entry_year_start,

    phone_1.phone_type as phone_1_type,
    phone_2.phone_type as phone_2_type,
    phone_3.phone_type as phone_3_type,

    custom_attributes,
    id_attributes,
    track_attributes,
    households,

    safe_cast(birth_date as date) as birth_date,

    households[safe_offset(0)].id as household_1_id,

    -- normalize the household address: Finalsite emits empty strings (not null)
    -- and mixed-case states, which flow unchanged into the Focus ADDRESS and
    -- CONTACTS feeds. Blank -> null; uppercase the state code.
    nullif(trim(households[safe_offset(0)].address_1), '') as address_1,
    nullif(trim(households[safe_offset(0)].address_2), '') as address_2,
    nullif(trim(households[safe_offset(0)].city), '') as city,
    nullif(upper(trim(households[safe_offset(0)].state)), '') as state,
    nullif(trim(households[safe_offset(0)].zip), '') as zip,
    households[safe_offset(0)].country as country,

    array(
        select h.id, from unnest(households) as h where h.id is not null
    ) as household_ids,

    -- normalize to E.164 here, the earliest point each phone is a scalar
    -- column, so every consumer reads one format: the Focus CONTACTS /
    -- ADDRESS import feeds and the SIS-agnostic contact models alike.
    -- Finalsite emits bare 10-digit numbers almost everywhere; anything not
    -- confidently parseable passes through de-garbled rather than nulling.
    {{ clean_phone("phone_1.number") }} as phone_1_number,
    {{ clean_phone("phone_2.number") }} as phone_2_number,
    {{ clean_phone("phone_3.number") }} as phone_3_number,
from {{ source("finalsite", "contacts") }}
