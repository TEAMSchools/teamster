select cf.id, cfo.id as option_id, cfo.created_at, cfo.updated_at, cfo.label,
from {{ source("overgrad", "src_overgrad__custom_fields") }} as cf
cross join unnest(cf.custom_field_options) as cfo
