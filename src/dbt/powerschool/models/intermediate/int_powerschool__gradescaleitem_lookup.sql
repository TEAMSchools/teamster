select
    parent.id as gradescaleid,
    parent.name as gradescale_name,

    items.name as letter_grade,
    items.grade_points,
    items.cutoffpercentage as min_cutoffpercentage,

    lead(items.cutoffpercentage, 1, 1000) over (
        partition by parent.id order by items.cutoffpercentage
    )
    - 0.1 as max_cutoffpercentage,
from {{ ref("stg_powerschool__gradescaleitem") }} as parent
inner join
    {{ ref("stg_powerschool__gradescaleitem") }} as items
    on parent.id = items.gradescaleid
where parent.gradescaleid = -1
