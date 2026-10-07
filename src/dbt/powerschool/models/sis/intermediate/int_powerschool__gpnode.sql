select
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
inner join {{ ref("stg_powerschool__gpnode") }} as o on p.id = o.parentid
inner join {{ ref("stg_powerschool__gpnode") }} as d on o.id = d.parentid
left join {{ ref("stg_powerschool__gpnode") }} as s on d.id = s.parentid
where p.parentid is null
