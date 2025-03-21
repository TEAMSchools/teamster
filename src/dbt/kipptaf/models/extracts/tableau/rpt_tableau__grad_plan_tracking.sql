with
    plans as (
        select p.*
        from {{ ref("int_powerschool__grad_plans") }} as p
        inner join
            {{ ref("int_powerschool__grad_plans_progress_students") }} as s
            on p.plan_id = s.plan_id
            and {{ union_dataset_join_clause(left_alias="p", right_alias="s") }}
    )

select *
from plans
