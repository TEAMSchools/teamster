with
    gpnode as (
        select
            _dbt_source_relation,

            /* unpivot columns */
            degree_plan_section,
            id,
            name,
            credit_capacity,
            safe_cast(credit_capacity as string) as credit_capacity_string,

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
    ),

    subjects as (
        select
            gp._dbt_source_relation,
            gp.id,
            gp.degree_plan_section,
            gp.name,

            sub.studentsdcid,
            coalesce(sub.requiredcredits, gp.credit_capacity) as requiredcredits,
            sub.enrolledcredits,
            sub.requestedcredits,
            sub.earnedcredits,
            sub.waivedcredits,
            sub.appliedwaivedcredits,

            row_number() over (
                partition by
                    gp._dbt_source_relation,
                    sub.studentsdcid,
                    gp.id,
                    gp.degree_plan_section,
                    gp.name,
                    gp.credit_capacity_string
            ) as rn_distinct,

        from gpnode as gp
        inner join
            {{ ref("stg_powerschool__gpprogresssubject") }} as sub
            on gp.id = sub.gpnodeid
            and {{ union_dataset_join_clause(left_alias="gp", right_alias="sub") }}
    )

select *
from subjects
where rn_distinct = 1
