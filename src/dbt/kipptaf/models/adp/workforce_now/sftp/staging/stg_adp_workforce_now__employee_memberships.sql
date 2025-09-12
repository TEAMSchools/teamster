with
    employee_memberships as (
        select
            associate_id,
            membership_code,
            membership_description,
            category_code,
            category_description,

            parse_date('%m/%d/%Y', effective_date) as effective_date,
            parse_date('%m/%d/%Y', expiration_date) as expiration_date,
        from
            {{
                source(
                    "adp_workforce_now", "src_adp_workforce_now__employee_memberships"
                )
            }}
    )

select
    *,

    if(
        category_description = 'Program - Leader Development', true, false
    ) as is_leader_development_program,

    if(
        category_description = 'Program - Teacher Development', true, false
    ) as is_teacher_development_program,

    if(
        current_date('{{ var("local_timezone") }}')
        between effective_date and expiration_date,
        true,
        false
    ) as is_current,
from employee_memberships
