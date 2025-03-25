select
    s._dbt_source_relation,
    s.studentsdcid,
    s.earnedcredits as earned_credits,
    s.enrolledcredits as enrolled_credits,
    s.requestedcredits as requested_credits,
    s.waivedcredits as waived_credits,
    s.requiredcredits as required_credits,
    s.isadvancedplan,

    g.plan_id,
    g.plan_gpversionid,
    g.plan_parentid,
    g.plan_name,
    g.plan_credit_capacity,
    g.discipline_id,
    g.discipline_name,
    g.discipline_credit_capacity,
    g.subject_id,
    g.subject_name,
    g.subject_credit_capacity,
from {{ ref("stg_powerschool__gpprogresssubject") }} as s
inner join
    {{ ref("int_powerschool__gpnode") }} as g
    on s.gpnodeid = g.plan_id
    and s.nodetype = g.nodetype
    and {{ union_dataset_join_clause(left_alias="s", right_alias="g") }}
