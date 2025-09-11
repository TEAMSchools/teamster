with
    memberships as (
        select associate_id, membership_description, category_description,
        from {{ ref("stg_adp_workforce_now__employee_memberships") }}
        where
            membership_code is not null
            and current_date('{{ var("local_timezone") }}')
            between effective_date and expiration_date
    ),

    memberships_concat as (
        select associate_id, string_agg(membership_description, ', ') as memberships,
        from memberships
        group by associate_id
    )

select
    mc.associate_id,
    mc.memberships,
    if(
        m.category_description = 'Program - Leader Development', true, false
    ) as is_in_leadership_program,
    if(
        m.category_description = 'Program - Teacher Development', true, false
    ) as is_in_teacher_program,
from memberships_concat as mc
inner join memberships as m on mc.associate_id = m.associate_id
