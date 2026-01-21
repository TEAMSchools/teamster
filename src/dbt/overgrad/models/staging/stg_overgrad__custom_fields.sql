select * except (custom_field_options),
from {{ source("overgrad", "src_overgrad__custom_fields") }}
