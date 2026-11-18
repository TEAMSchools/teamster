select
    g.assignment_id,
    g.goal_tag_id,

    tu.internal_id_int as teacher_employee_number,

    cu.internal_id_int as creator_employee_number,

    g.created as assignment_created_timestamp,
    g.created_date_local as assignment_date,
    g.goal_type_name,
    g.goal_name,
    g.strand_name,
    g.bucket_name,
from {{ ref("int_schoolmint_grow__assignments__goals") }} as g
inner join
    {{ ref("stg_schoolmint_grow__users") }} as tu
    on g.user_id = tu.user_id
    and tu.internal_id_int is not null
left join {{ ref("stg_schoolmint_grow__users") }} as cu on g.creator_id = cu.user_id
