select s.id, cfv.custom_field_id, cfv.number, cfv.date, cfv.select,
from {{ source("overgrad", "src_overgrad__students") }} as s
cross join unnest(s.custom_field_values) as cfv
