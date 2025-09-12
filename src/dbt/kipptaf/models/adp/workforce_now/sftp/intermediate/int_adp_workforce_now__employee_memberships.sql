select
    associate_id,
    is_current,

    max(is_leader_development_program) as is_leader_development_program,
    max(is_teacher_development_program) as is_teacher_development_program,

    string_agg(membership_description, ', ') as mememberships,
from {{ ref("stg_adp_workforce_now__employee_memberships") }}
where membership_code is not null
group by associate_id, is_current
