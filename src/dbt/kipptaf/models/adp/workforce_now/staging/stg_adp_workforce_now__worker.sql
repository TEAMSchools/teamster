select
    * except (custom_miami_aces_number),

    safe_cast(custom_miami_aces_number as int) as custom_miami_aces_number,
from {{ source("adp_workforce_now", "worker") }}
