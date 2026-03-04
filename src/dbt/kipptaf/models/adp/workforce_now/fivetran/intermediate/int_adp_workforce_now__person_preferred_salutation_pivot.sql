select
    worker_id, legal_name, birth_name, former_name, preferred, alternate_preferred_name,
from
    {{ ref("stg_adp_workforce_now__person_preferred_salutation") }} pivot (
        max(salutation) for `type` in (
            'legal_name',
            'birth_name',
            'former_name',
            'preferred',
            'alternate_preferred_name'
        )
    )
