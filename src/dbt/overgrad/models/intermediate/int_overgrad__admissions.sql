select a.*, cf.* except (id, source_object),
from {{ ref("stg_overgrad__admissions") }} as a
left join
    {{ ref("int_overgrad__custom_fields_pivot") }} as cf
    on a.id = cf.id
    and cf.source_object = 'admissions'
