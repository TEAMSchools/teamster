select
    s.studentsdcid,
    s.earnedcredits,  -- from stored grades
    s.enrolledcredits,  -- from cc table
    s.requestedcredits,  -- from schedule requests table
    s.requiredcredits,
    s.waivedcredits,
    s.isadvancedplan,

    g.id as subject_id,
    g.name as subject_name,

from {{ ref("stg_powerschool__gpprogresssubject") }} as s
inner join
    {{ ref("stg_powerschool__gpnode") }} as g
    on s.gpnodeid = g.id
    and s.nodetype = g.nodetype
    and {{ union_dataset_join_clause(left_alias="s", right_alias="g") }}
    and g.name not in ('Total Credits', 'Overall Credits')
    and g.creditcapacity is not null
