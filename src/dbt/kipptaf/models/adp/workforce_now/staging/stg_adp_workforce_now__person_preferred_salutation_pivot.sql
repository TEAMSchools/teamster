{{ config(tags="dagster") }}

select
    worker_id,
    legal_name as legal_name,
    birth_name as birth_name,
    former_name as former_name,
    preferred as preferred,
    alternate_preferred_name as alternate_preferred_name,
from
    {{ source("adp_workforce_now", "person_preferred_salutation") }} pivot (
        max(salutation) for `type` in (
            'legal_name',
            'birth_name',
            'former_name',
            'preferred',
            'alternate_preferred_name'
        )
    )
