select
    person_id,
    title,
    first_name,
    middle_name,
    last_name,
    email,
    email_opt_out,
    birthdate,
    education_level,
    primary_language,
    imported,
    people_import_key,
    uuid,
    created_at,
    updated_at,
from {{ source("focus", "people") }}
where deleted is null
