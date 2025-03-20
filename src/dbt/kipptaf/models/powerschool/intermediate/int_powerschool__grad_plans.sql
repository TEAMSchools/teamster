select
    p._dbt_source_relation,
    p.gpversionid as plan_gpversionid,
    p.parentid as plan_parentid,

    /* foreign key to int_powerschool__grad_plans_progress_students.gpnodeid */
    p.id as plan_id,
    p.name as plan_name,

    o.creditcapacity as plan_credits,

    d.id as discipline_id,
    d.name as discipline_name,
    d.creditcapacity as discipline_credits,

    c.id as subject_id,
    c.name as subject_name,
    c.creditcapacity as subject_credits,

from {{ ref("stg_powerschool__gpnode") }} as p
inner join {{ ref("stg_powerschool__gpnode") }} as o on p.id = o.parentid
inner join {{ ref("stg_powerschool__gpnode") }} as d on o.id = d.parentid
left join {{ ref("stg_powerschool__gpnode") }} as c on d.id = c.parentid
where p.parentid is null and p.name in ('NJ State Diploma', 'HS Distinction Diploma')
order by o.sortorder, d.sortorder, c.sortorder
