select
    og.observation_group_id,

    ogo._id as observee_id,
    ogo.name as observee_name,
    ogo.email as observee_email,
from {{ ref("stg_schoolmint_grow__schools__observation_groups") }} as og
cross join unnest(og.observation_group_observees) as ogo
