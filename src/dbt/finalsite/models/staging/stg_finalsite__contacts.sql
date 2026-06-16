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

    school_year.start_year as school_year_start,

    phone_1.phone_type as phone_1_type,
    phone_1.number as phone_1_number,
    phone_2.phone_type as phone_2_type,
    phone_2.number as phone_2_number,
    phone_3.phone_type as phone_3_type,
    phone_3.number as phone_3_number,

    custom_attributes,
    id_attributes,

    safe_cast(birth_date as date) as birth_date,

    households[safe_offset(0)].address_1 as address_1,
    households[safe_offset(0)].address_2 as address_2,
    households[safe_offset(0)].city as city,
    households[safe_offset(0)].state as state,
    households[safe_offset(0)].zip as zip,
    households[safe_offset(0)].country as country,
from {{ source("finalsite", "contacts") }}
