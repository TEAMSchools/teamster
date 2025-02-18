with recursive
    standards as (
        select standard_id as root_standard_id, parent_standard_id, standard_id,
        from {{ ref("stg_illuminate__standards") }}
        where parent_standard_id = 0

        union all

        select s1.root_standard_id, s2.parent_standard_id, s2.standard_id,
        from standards as s1
        inner join
            {{ ref("stg_illuminate__standards") }} as s2
            on s1.standard_id = s2.parent_standard_id
    )

select root_standard_id, parent_standard_id, standard_id,
from standards
