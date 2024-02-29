select
    w.associateoid as associate_oid,

    /* workAssignments */
    wa.itemid as item_id,

    /* workAssignments.baseRemuneration */
    wa.baseremuneration.effectivedate as base_remuneration__effective_date,

    wa.baseremuneration.annualrateamount.amountvalue
    as base_remuneration__annual_rate_amount__amount_value,
    wa.baseremuneration.annualrateamount.currencycode
    as base_remuneration__annual_rate_amount__currency_code,
    wa.baseremuneration.annualrateamount.namecode.codevalue
    as base_remuneration__annual_rate_amount__name_code__code_value,
    wa.baseremuneration.annualrateamount.namecode.shortname
    as base_remuneration__annual_rate_amount__name_code__short_name,

    wa.baseremuneration.dailyrateamount.amountvalue
    as base_remuneration__daily_rate_amount__amount_value,
    wa.baseremuneration.dailyrateamount.currencycode
    as base_remuneration__daily_rate_amount__currency_code,
    wa.baseremuneration.dailyrateamount.namecode.codevalue
    as base_remuneration__daily_rate_amount__name_code__code_value,
    wa.baseremuneration.dailyrateamount.namecode.shortname
    as base_remuneration__daily_rate_amount__name_code__short_name,

    wa.baseremuneration.hourlyrateamount.amountvalue
    as base_remuneration__hourly_rate_amount__amount_value,
    wa.baseremuneration.hourlyrateamount.currencycode
    as base_remuneration__hourly_rate_amount__currency_code,
    wa.baseremuneration.hourlyrateamount.namecode.codevalue
    as base_remuneration__hourly_rate_amount__name_code__code_value,
    wa.baseremuneration.hourlyrateamount.namecode.shortname
    as base_remuneration__hourly_rate_amount__name_code__short_name,

    wa.baseremuneration.payperiodrateamount.amountvalue
    as base_remuneration__pay_period_rate_amount__amount_value,
    wa.baseremuneration.payperiodrateamount.currencycode
    as base_remuneration__pay_period_rate_amount__currency_code,
    wa.baseremuneration.payperiodrateamount.namecode.codevalue
    as base_remuneration__pay_period_rate_amount__name_code__code_value,
    wa.baseremuneration.payperiodrateamount.namecode.shortname
    as base_remuneration__pay_period_rate_amount__name_code__short_name,

    timestamp(
        w._dagster_partition_date, '{{ var("local_timezone")}}'
    ) as as_of_date_timestamp,

    {{ dbt_utils.generate_surrogate_key(["to_json_string(w.workassignments)"]) }}
    as surrogate_key,
from {{ source("adp_workforce_now", "src_adp_workforce_now__workers") }} as w
cross join unnest(w.workassignments) as wa
