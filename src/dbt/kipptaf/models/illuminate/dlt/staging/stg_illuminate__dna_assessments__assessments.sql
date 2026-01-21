select
    *,

    (
        select true, from unnest(split(tags, ',')) as t where t in ('1', '2')
    ) as is_grade_k_1,
from {{ source("illuminate_dna_assessments", "assessments") }}
where deleted_at is null
