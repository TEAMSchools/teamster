select
    og.observation_group_id,

    ogo._id as observer_id,
    ogo.name as observer_name,
    ogo.email as observer_email,
from {{ ref("stg_schoolmint_grow__schools__observation_groups") }} as og
cross join unnest(og.observation_group_observers) as ogo
