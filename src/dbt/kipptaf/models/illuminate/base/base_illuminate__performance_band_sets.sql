{% set ref_pbs = ref("stg_illuminate__performance_band_sets") %}
{% set ref_pb = ref("stg_illuminate__performance_bands") %}

select
    {{ dbt_utils.star(from=ref_pbs, relation_alias="pbs") }},

    {{
        dbt_utils.star(
            from=ref_pb, relation_alias="pb", except=["performance_band_set_id"]
        )
    }},
    
    lead(minimum_value, 1, 9999) over (
        partition by pbs.performance_band_set_id order by pb.label_number
    )
    - 0.1 as maximum_value,
from {{ ref_pbs }} as pbs
inner join
    {{ ref_pb }} as pb on pbs.performance_band_set_id = pb.performance_band_set_id
