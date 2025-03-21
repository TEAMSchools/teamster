with
    students as (
        select
            s._dbt_source_relation,
            s.studentsdcid,
            s.gpnodeid,
            s.earnedcredits,  -- from stored grades
            s.enrolledcredits,  -- from cc table
            s.requestedcredits,  -- from schedule requests table
            s.requiredcredits,
            s.waivedcredits,
            s.isadvancedplan,

            g.gpversionid,
            g.parentid,
            g.id,
            g.name,

        from {{ ref("stg_powerschool__gpprogresssubject") }} as s
        inner join
            {{ ref("stg_powerschool__gpnode") }} as g
            on s.gpnodeid = g.id
            and s.nodetype = g.nodetype
            and {{ union_dataset_join_clause(left_alias="s", right_alias="g") }}
    )

select
    p._dbt_source_relation,
    p.studentsdcid,
    p.gpversionid as plan_gpversionid,
    p.id as plan_id,
    p.parentid as plan_parentid,
    p.name as plan_name,
    p.isadvancedplan,

    o.requiredcredits as plan_credits,
    o.enrolledcredits as plan_enrolled_credits,

    d.id as discpline_id,
    d.name as discipline_name,
    d.requiredcredits as discipline_required_credits,
    d.earnedcredits as discipline_earned_credits,
    d.enrolledcredits as discipline_enrolled_credits,
    d.requestedcredits as discipline_requested_credits,
    d.waivedcredits as discipline_waived_credits,

    s.id as subject_id,
    s.name as subject_name,
    s.requiredcredits as subject_required_credits,
    s.earnedcredits as subject_earned_credits,
    s.enrolledcredits as subject_enrolled_credits,
    s.requestedcredits as subject_requested_credits,
    s.waivedcredits as subject_waived_credits,

from students as p
inner join
    students as o
    on p.id = o.parentid
    and p.studentsdcid = o.studentsdcid
    and {{ union_dataset_join_clause(left_alias="p", right_alias="o") }}
inner join
    students as d
    on o.id = d.parentid
    and o.studentsdcid = d.studentsdcid
    and {{ union_dataset_join_clause(left_alias="o", right_alias="d") }}
inner join
    students as s
    on d.id = s.parentid
    and d.studentsdcid = s.studentsdcid
    and {{ union_dataset_join_clause(left_alias="d", right_alias="s") }}
where p.parentid is null
