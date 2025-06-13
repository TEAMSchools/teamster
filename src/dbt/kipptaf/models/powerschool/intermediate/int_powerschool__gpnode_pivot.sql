with
    unpivoted as (
        select
            _dbt_source_relation,
            plan_id,
            plan_name,
            discipline_id,
            discipline_name,
            subject_id,
            subject_name,
            plan_credit_capacity,
            discipline_credit_capacity,
            subject_credit_capacity,

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

select *,
from
    unpivoted pivot (
        max(credit_capacity) as credit_capacity
        for degree_plan_section in ('plan', 'discipline', 'subject')
    )
