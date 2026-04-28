with
    /* dbt_utils.deduplicate references this CTE by string name */
    -- trunk-ignore(sqlfluff/ST03)
    earnings_unnested as (
        select
            wa.item_id,
            wa.effective_date_start,

            ar.itemid as earning_item_id,
            ar.namecode.codevalue as earning_code,
            ar.rate.amountvalue as rate_amount,

            coalesce(
                ar.namecode.longname, ar.namecode.shortname
            ) as earning_description,
            date(ar.effectivedate) as earning_effective_date,
        from {{ ref("int_adp_workforce_now__workers__work_assignments") }} as wa
        cross join unnest(wa.additional_remunerations) as ar
        where ar.effectivedate is not null
    ),

    earnings_deduped as (
        {{
            dbt_utils.deduplicate(
                relation="earnings_unnested",
                partition_by="item_id, earning_item_id, earning_effective_date",
                order_by="effective_date_start desc",
            )
        }}
    ),

    windowed as (
        select
            item_id,
            earning_item_id,
            earning_code,
            earning_description,
            rate_amount,
            earning_effective_date as effective_date_start,

            coalesce(
                date_sub(
                    lead(earning_effective_date) over (
                        partition by item_id, earning_item_id
                        order by earning_effective_date asc
                    ),
                    interval 1 day
                ),
                date '9999-12-31'
            ) as effective_date_end,
        from earnings_deduped
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "item_id",
                "earning_item_id",
                "effective_date_start",
            ]
        )
    }} as work_assignment_additional_earnings_key,

    {{ dbt_utils.generate_surrogate_key(["item_id"]) }} as work_assignment_key,

    effective_date_start as effective_start_date_key,
    effective_date_end as effective_end_date_key,

    earning_code,
    earning_description,
    rate_amount,

    if(effective_date_end = '9999-12-31', true, false) as is_current,
from windowed
