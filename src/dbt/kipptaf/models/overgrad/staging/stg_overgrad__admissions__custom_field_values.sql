select a.id, cfv.custom_field_id, cfv.number, cfv.date, cfv.select,
from {{ source("overgrad", "src_overgrad__admissions") }} as a
cross join unnest(a.custom_field_values) as cfv
