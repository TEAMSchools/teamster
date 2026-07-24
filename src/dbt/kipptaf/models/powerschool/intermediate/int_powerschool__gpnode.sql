select
    p._dbt_source_relation,
    p.nodetype,
    p.id as plan_id,
    p.gpversionid as plan_gpversionid,
    p.parentid as plan_parentid,
    p.name as plan_name,
    p._dbt_source_project,

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
    and p._dbt_source_project = o._dbt_source_project
inner join
    {{ ref("stg_powerschool__gpnode") }} as d
    on o.id = d.parentid
    and o._dbt_source_project = d._dbt_source_project
left join
    {{ ref("stg_powerschool__gpnode") }} as s
    on d.id = s.parentid
    and d._dbt_source_project = s._dbt_source_project
where p.parentid is null
