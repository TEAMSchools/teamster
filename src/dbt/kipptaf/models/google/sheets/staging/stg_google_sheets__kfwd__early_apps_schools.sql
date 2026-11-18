select overgrad_school_name, school_key,
from {{ source("google_sheets", "src_google_sheets__kfwd__early_apps_schools") }}
where overgrad_school_name is not null
