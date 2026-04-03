select
    * replace (
        cast(label_number as numeric) as label_number,
        cast(minimum_value as numeric) as minimum_value
    ),
from {{ source("illuminate_dna_assessments", "performance_bands") }}
