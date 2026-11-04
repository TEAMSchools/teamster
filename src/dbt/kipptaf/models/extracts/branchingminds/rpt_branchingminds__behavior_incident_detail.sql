with
    incident_students as (
        select
            cast(incident_id as string) as incident_id,
            cast(student_school_id as string) as student_id,
        from {{ ref("int_deanslist__incidents") }}
    )

select
    bi.incident_id,

    ist.student_id,

    concat(bi.incident_id, '-', ist.student_id) as incident_detail_id,
from {{ ref("rpt_branchingminds__behavior_incident") }} as bi
inner join incident_students as ist on bi.incident_id = ist.incident_id
