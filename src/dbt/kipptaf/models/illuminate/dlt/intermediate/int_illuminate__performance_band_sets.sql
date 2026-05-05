select
    pbs.performance_band_set_id,
    pbs.description,
    pbs.district_default,
    pbs.hidden,
    pbs.user_id,
    pbs.created_at,
    pbs.updated_at,
    pbs.deleted_at,

    pb.performance_band_id,
    pb.color,
    pb.is_mastery,
    pb.label,
    pb.label_number,
    pb.minimum_value,

    lead(pb.minimum_value, 1, 9999) over (
        partition by pbs.performance_band_set_id order by pb.label_number
    )
    - 0.1 as maximum_value,
from {{ ref("stg_illuminate__dna_assessments__performance_band_sets") }} as pbs
inner join
    {{ ref("stg_illuminate__dna_assessments__performance_bands") }} as pb
    on pbs.performance_band_set_id = pb.performance_band_set_id
