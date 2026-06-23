select
    id,
    object_id,
    date,
    type,
    failed,
    ip_address,
    user_agent,
    username,
    token_type,
    hostname,
from {{ source("focus", "login_history") }}
