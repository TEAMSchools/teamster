select a.*, cf.*,
from {{ ref("stg_overgrad__admissions") }} as a
left join
    {{ ref("int_overgrad__custom_fields_pivot") }} as cf
    on s.id = cf.id
    and cf.source_object = 'admissions'
