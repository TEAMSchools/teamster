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

    custom_attributes,
    id_attributes,
    track_attributes,
    households,

    safe_cast(birth_date as date) as birth_date,

    -- Finalsite emits an unset phone type as an empty string on a contact
    -- record, but as NULL in the emrg_N custom-field sets that feed the
    -- emergency contact slots. Normalize to NULL so every consumer tests for an
    -- untyped phone the same way -- the same blank-to-null treatment the
    -- household address fields get below.
    nullif(phone_1.phone_type, '') as phone_1_type,
    nullif(phone_2.phone_type, '') as phone_2_type,
    nullif(phone_3.phone_type, '') as phone_3_type,

    households[safe_offset(0)].id as household_1_id,

    nullif(trim(households[safe_offset(0)].address_1), '') as address_1,
    nullif(trim(households[safe_offset(0)].address_2), '') as address_2,
    nullif(trim(households[safe_offset(0)].city), '') as city,
    nullif(upper(trim(households[safe_offset(0)].state)), '') as state,
    nullif(trim(households[safe_offset(0)].zip), '') as zip,
    households[safe_offset(0)].country as country,

    array(
        select h.id, from unnest(households) as h where h.id is not null
    ) as household_ids,

    {{ clean_phone("phone_1.number") }} as phone_1_number,
    {{ clean_phone("phone_2.number") }} as phone_2_number,
    {{ clean_phone("phone_3.number") }} as phone_3_number,
from {{ source("finalsite", "contacts") }}
