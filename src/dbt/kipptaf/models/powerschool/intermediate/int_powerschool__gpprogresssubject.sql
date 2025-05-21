with
    gpnode as (
        select
            _dbt_source_relation,

            /* unpivot columns */
            degree_plan_section,
            id,
            name,
            max(credit_capacity) as credit_capacity,

        from
            {{ ref("int_powerschool__gpnode") }} unpivot (
                (id, name, credit_capacity) for degree_plan_section in (
                    (plan_id, plan_name, plan_credit_capacity) as 'Plan',
                    (
                        discipline_id, discipline_name, discipline_credit_capacity
                    ) as 'Discipline',
                    (subject_id, subject_name, subject_credit_capacity) as 'Subject'
                )
            )
        group by _dbt_source_relation, degree_plan_section, id, name
    ),

    subjects as (
        select
            gp._dbt_source_relation,
            gp.id,
            gp.degree_plan_section,
            gp.name,

            sub.studentsdcid,
            sub.enrolledcredits,
            sub.requestedcredits,
            sub.earnedcredits,
            sub.waivedcredits,
            sub.appliedwaivedcredits,

            coalesce(sub.requiredcredits, gp.credit_capacity) as requiredcredits,

        from gpnode as gp
        inner join
            {{ ref("stg_powerschool__gpprogresssubject") }} as sub
            on gp.id = sub.gpnodeid
            and {{ union_dataset_join_clause(left_alias="gp", right_alias="sub") }}
    )

select
    _dbt_source_relation,
    id,
    degree_plan_section,
    name,
    studentsdcid,
    requiredcredits,
    enrolledcredits,
    requestedcredits,
    earnedcredits,
    waivedcredits,
    appliedwaivedcredits,

from subjects
