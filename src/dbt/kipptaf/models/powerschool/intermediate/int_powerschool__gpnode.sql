select
    p._dbt_source_relation,
    p.nodetype,
    p.id as plan_id,
    p.gpversionid as plan_gpversionid,
    p.parentid as plan_parentid,
    p.name as plan_name,

    o.creditcapacity as plan_credit_capacity,

    d.id as discipline_id,
    d.name as discipline_name,
    d.creditcapacity as discipline_credit_capacity,

    coalesce(s.id, d.id) as subject_id,
    coalesce(s.name, d.name) as subject_name,
    coalesce(s.creditcapacity, d.creditcapacity) as subject_credit_capacity,
from {{ ref("stg_powerschool__gpnode") }} as p
inner join
    {{ ref("stg_powerschool__gpnode") }} as o
    on p.id = o.parentid
    and {{ union_dataset_join_clause(left_alias="p", right_alias="o") }}
inner join
    {{ ref("stg_powerschool__gpnode") }} as d
    on o.id = d.parentid
    and {{ union_dataset_join_clause(left_alias="o", right_alias="d") }}
left join
    {{ ref("stg_powerschool__gpnode") }} as s
    on d.id = s.parentid
    and {{ union_dataset_join_clause(left_alias="d", right_alias="s") }}
where p.parentid is null
