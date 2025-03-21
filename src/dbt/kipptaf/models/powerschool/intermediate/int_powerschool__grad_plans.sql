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

    s.id as subject_id,
    s.name as subject_name,
    s.creditcapacity as subject_credits,

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
    on d.id = s.id
    and {{ union_dataset_join_clause(left_alias="d", right_alias="s") }}
where p.parentid is null
order by o.sortorder, d.sortorder, s.sortorder
