{{- config(enabled=false) -}}

select *,
from {{ source("illuminate", "grade_levels") }}
where not _fivetran_deleted
