select
    id as finalsite_enrollment_id,
    first_name,
    middle_name,
    last_name,
    gender,
    status,
    enrollment_type,

    grade.canonical_name as grade_canonical_name,
    school_year.start_year as school_year_start,

    safe_cast(birth_date as date) as birth_date,

    households[safe_offset(0)].address_1 as address_1,
    households[safe_offset(0)].address_2 as address_2,
    households[safe_offset(0)].city as city,
    households[safe_offset(0)].state as state,
    households[safe_offset(0)].zip as zip,

    (
        select any_value(av.value),
        from unnest(custom_attributes) as av
        where av.field_name = 'race_ms'
    ) as race_ms,
    (
        select any_value(av.value),
        from unnest(custom_attributes) as av
        where av.field_name = 'latino_hispanic_yn'
    ) as latino_hispanic_yn,
    (
        select any_value(av.value),
        from unnest(custom_attributes) as av
        where av.field_name = 'assigned_school_ss'
    ) as assigned_school_ss,
    (
        select any_value(av.value),
        from unnest(custom_attributes) as av
        where av.field_name = 'sped_received_yn'
    ) as sped_received_yn,
    (
        select any_value(av.value),
        from unnest(id_attributes) as av
        where av.field_name = 'mdcps_id_txt'
    ) as mdcps_id_txt,
    (
        select any_value(av.value),
        from unnest(id_attributes) as av
        where av.field_name = 'powerschool_student_number'
    ) as powerschool_student_number,
from {{ source("finalsite", "contacts") }}
