select g.*, initcap(regexp_extract(s._dbt_source_relation, r'kipp(\w+)_')) as region,
from {{ source("assessments", "src_assessments__academic_goals") }} as g
inner join {{ ref("stg_powerschool__schools") }} as s on g.school_id = s.school_number
