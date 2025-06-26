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

    psen.ccdcid,

    psea.storedgradesdcid,
from {{ ref("stg_powerschool__gpprogresssubject") }} as ps
left join
    {{ ref("stg_powerschool__gpprogresssubjectenrolled") }} as psen
    on ps.id = psen.gpprogresssubjectid
    and {{ union_dataset_join_clause(left_alias="ps", right_alias="psen") }}
left join
    {{ ref("stg_powerschool__gpprogresssubjectearned") }} as psea
    on ps.id = psea.gpprogresssubjectid
    and {{ union_dataset_join_clause(left_alias="ps", right_alias="psea") }}
