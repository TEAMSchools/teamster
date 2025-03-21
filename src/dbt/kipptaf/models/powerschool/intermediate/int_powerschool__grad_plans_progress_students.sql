with
    students as (
        select
            s._dbt_source_relation,
            s.studentsdcid,
            s.gpnodeid as plan_id,
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
    )

select
    p.*,

    s.studentsdcid,
    s.isadvancedplan as advanced_plan,
    s.earnedcredits as subject_earnedcredits,
    s.enrolledcredits as subject_enrolledcredits,
    s.requestedcredits as subject_requestedcredits,
    s.requiredcredits as subject_requiredcredits,
    s.waivedcredits as subject_waivedcredits,

from {{ ref("int_powerschool__grad_plans") }} as p
left join
    students as s
    on p.subject_id = s.subject_id
    and {{ union_dataset_join_clause(left_alias="p", right_alias="s") }}
