with
    bucket_memberships as (
        select
            student_id,
            syear,
            title,

            trim(split(title, '-')[safe_offset(1)]) as discipline,
        from {{ ref("int_focus__student_group_memberships") }}
        where title like 'Bucket%'
    )

select
    student_id,
    syear,
    discipline,

    count(*) as n_memberships,

    string_agg(title, ', ' order by title) as titles,
from bucket_memberships
group by student_id, syear, discipline
having count(*) > 1
