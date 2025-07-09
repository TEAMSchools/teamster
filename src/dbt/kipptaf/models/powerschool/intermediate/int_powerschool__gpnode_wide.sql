select
    p._dbt_source_relation,
    p.id as root_node_id,
    p.name as root_node_name,
    p.id as plan_id,
    p.name as plan_name,

    o.creditcapacity as plan_credit_capacity,

    d.id as discipline_id,
    d.name as discipline_name,
    d.creditcapacity as discipline_credit_capacity,

    s.id as subject_id,
    s.name as subject_name,
    s.creditcapacity as subject_credit_capacity,

from {{ ref("stg_powerschool__gpnode") }} as p
left join
    {{ ref("stg_powerschool__gpnode") }} as o
    on p.id = o.parentid
    and {{ union_dataset_join_clause(left_alias="p", right_alias="o") }}
left join
    {{ ref("stg_powerschool__gpnode") }} as d
    on o.id = d.parentid
    and {{ union_dataset_join_clause(left_alias="o", right_alias="d") }}
left join
    {{ ref("stg_powerschool__gpnode") }} as s
    on d.id = s.parentid
    and {{ union_dataset_join_clause(left_alias="d", right_alias="s") }}
where p.parentid is null
