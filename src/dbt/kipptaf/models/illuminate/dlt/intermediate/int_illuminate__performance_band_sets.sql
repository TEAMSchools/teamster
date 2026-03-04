select
    pbs.*,

    pb.* except (performance_band_set_id),

    lead(pb.minimum_value, 1, 9999) over (
        partition by pbs.performance_band_set_id order by pb.label_number
    )
    - 0.1 as maximum_value,
from {{ ref("stg_illuminate__dna_assessments__performance_band_sets") }} as pbs
inner join
    {{ ref("stg_illuminate__dna_assessments__performance_bands") }} as pb
    on pbs.performance_band_set_id = pb.performance_band_set_id
