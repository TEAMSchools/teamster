select
    p._dbt_source_relation,
    p.id as plan_id,
    p.gpversionid as plan_gpversionid,
    p.parentid as plan_parentid,
    p.name as plan_name,

    o.creditcapacity as plan_credit_capacity,

    d.id as discipline_id,
    d.name as discipline_name,
    d.creditcapacity as discipline_credit_capacity,

    s.id as subject_id,
    s.name as subject_name,
    s.creditcapacity as subject_credit_capacity,

    ps.id as gpprogresssubject_id,
    ps.studentsdcid,

    psen.ccdcid,

    psea.storedgradesdcid,
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
left join
    {{ ref("stg_powerschool__gpprogresssubject") }} as ps
    on s.id = ps.gpnodeid
    and {{ union_dataset_join_clause(left_alias="s", right_alias="ps") }}
left join
    {{ ref("stg_powerschool__gpprogresssubjectenrolled") }} as psen
    on ps.id = psen.gpprogresssubjectid
    and {{ union_dataset_join_clause(left_alias="ps", right_alias="psen") }}
left join
    {{ ref("stg_powerschool__gpprogresssubjectearned") }} as psea
    on ps.id = psea.gpprogresssubjectid
    and {{ union_dataset_join_clause(left_alias="ps", right_alias="psea") }}
where p.parentid is null and p.name in ('NJ State Diploma', 'HS Distinction Diploma')

union all

select
    p._dbt_source_relation,
    p.id as plan_id,
    p.gpversionid as plan_gpversionid,
    p.parentid as plan_parentid,
    p.name as plan_name,
    p.creditcapacity as plan_credit_capacity,

    d.id as discipline_id,
    d.name as discipline_name,
    d.creditcapacity as discipline_credit_capacity,

    s.id as subject_id,
    s.name as subject_name,
    s.creditcapacity as subject_credit_capacity,

    null as gpprogresssubject_id,
    null as studentsdcid,
    null as ccdcid,
    null as storedgradesdcid,
from {{ ref("stg_powerschool__gpnode") }} as p
left join
    {{ ref("stg_powerschool__gpnode") }} as d
    on p.id = d.parentid
    and {{ union_dataset_join_clause(left_alias="p", right_alias="d") }}
left join
    {{ ref("stg_powerschool__gpnode") }} as s
    on d.id = s.parentid
    and {{ union_dataset_join_clause(left_alias="d", right_alias="s") }}
where
    p.parentid is null and p.name not in ('NJ State Diploma', 'HS Distinction Diploma')
