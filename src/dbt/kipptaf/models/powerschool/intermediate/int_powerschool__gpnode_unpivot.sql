with
    unpivoted as (
        select
            _dbt_source_relation,
            studentsdcid,

            /* unpivot columns */
            id,
            `name`,
            degree_plan_section,
            credit_capacity,
        from
            {{ ref("int_powerschool__gpnode") }} unpivot (
                (id, `name`, credit_capacity) for degree_plan_section in (
                    (plan_id, plan_name, plan_credit_capacity) as 'plan',
                    (
                        discipline_id, discipline_name, discipline_credit_capacity
                    ) as 'discipline',
                    (subject_id, subject_name, subject_credit_capacity) as 'subject'
                )
            )
    )

select
    _dbt_source_relation,
    studentsdcid,
    id,
    `name`,
    degree_plan_section,

    max(credit_capacity) as credit_capacity,
from unpivoted
group by _dbt_source_relation, studentsdcid, id, `name`, degree_plan_section
