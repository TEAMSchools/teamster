select
    position_id,
    academic_year,
    additional_earnings_code,
    additional_earnings_description,
    sum(gross_pay) as gross_pay_total,
from {{ ref("stg_adp_workforce_now__additional_earnings_report") }}
group by
    position_id,
    academic_year,
    additional_earnings_code,
    additional_earnings_description
