-- trunk-ignore(sqlfluff/ST06): column order fixed by the Branching Minds template
select
    concat(
        bi.incident_id, '-', cast(i.student_school_id as string)
    ) as incident_detail_id,
    bi.incident_id,
    cast(i.student_school_id as string) as student_id,
from {{ ref("rpt_branchingminds__behavior_incident") }} as bi
inner join
    {{ ref("int_deanslist__incidents") }} as i
    on bi.incident_id = cast(i.incident_id as string)
