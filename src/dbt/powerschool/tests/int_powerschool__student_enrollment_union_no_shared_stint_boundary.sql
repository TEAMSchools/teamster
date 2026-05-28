with
    stints as (
        select
            student_number,
            entrydate,
            exitdate,
            lead(entrydate) over (
                partition by student_number order by entrydate, exitdate
            ) as next_entrydate,
        from {{ ref("int_powerschool__student_enrollment_union") }}
        where entrydate is not null and exitdate is not null
    )

select student_number, entrydate, exitdate, next_entrydate,
from stints
where next_entrydate = exitdate
