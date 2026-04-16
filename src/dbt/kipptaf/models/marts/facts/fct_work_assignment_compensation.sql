with
    compensation_versions as (
        {{
            dbt_utils.deduplicate(
                relation=ref("int_adp_workforce_now__workers__work_assignments"),
                partition_by="item_id, base_remuneration__effective_date",
                order_by="effective_date_start desc",
            )
        }}
    ),

    windowed as (
        select
            item_id,
            base_remuneration__annual_rate_amount__amount_value as annual_rate,
            base_remuneration__hourly_rate_amount__amount_value as hourly_rate,
            base_remuneration__daily_rate_amount__amount_value as daily_rate,
            base_remuneration__pay_period_rate_amount__amount_value as period_rate,
            base_remuneration__effective_date as effective_date_start,

            coalesce(
                date_sub(
                    lead(base_remuneration__effective_date) over (
                        partition by item_id
                        order by base_remuneration__effective_date asc
                    ),
                    interval 1 day
                ),
                date '9999-12-31'
            ) as effective_date_end,
        from compensation_versions
        where base_remuneration__effective_date is not null
    )

select
    {{ dbt_utils.generate_surrogate_key(["item_id", "effective_date_start"]) }}
    as work_assignment_compensation_key,

    {{ dbt_utils.generate_surrogate_key(["item_id"]) }} as work_assignment_key,

    effective_date_start as effective_date_key,

    annual_rate,
    hourly_rate,
    daily_rate,
    period_rate,
    effective_date_start,
    effective_date_end,

    if(effective_date_end = '9999-12-31', true, false) as is_current_record,
from windowed
