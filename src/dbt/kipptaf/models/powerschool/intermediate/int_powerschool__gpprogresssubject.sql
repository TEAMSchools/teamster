select
    ps._dbt_source_relation,
    ps.id,
    ps.gpnodeid,
    ps.studentsdcid,
    ps.requiredcredits,
    ps.enrolledcredits,
    ps.requestedcredits,
    ps.earnedcredits,
    ps.waivedcredits,

    psen.ccdcid as grade_dcid,

    'Enrolled' as credit_status,
from {{ ref("stg_powerschool__gpprogresssubject") }} as ps
left join
    {{ ref("stg_powerschool__gpprogresssubjectenrolled") }} as psen
    on ps.id = psen.gpprogresssubjectid
    and {{ union_dataset_join_clause(left_alias="ps", right_alias="psen") }}

union all

select
    ps._dbt_source_relation,
    ps.id,
    ps.gpnodeid,
    ps.studentsdcid,
    ps.requiredcredits,
    ps.enrolledcredits,
    ps.requestedcredits,
    ps.earnedcredits,
    ps.waivedcredits,

    psea.storedgradesdcid as grade_dcid,

    'Earned' as credit_status,
from {{ ref("stg_powerschool__gpprogresssubject") }} as ps
left join
    {{ ref("stg_powerschool__gpprogresssubjectearned") }} as psea
    on ps.id = psea.gpprogresssubjectid
    and {{ union_dataset_join_clause(left_alias="ps", right_alias="psea") }}
