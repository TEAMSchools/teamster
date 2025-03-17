{{-
    config(
        severity="warn",
        store_failures=true,
        store_failures_as="view",
        enabled=true,
    )
-}}

select *,
from {{ ref("model_name") }}
where grad_eligibility = 'New category. Need new logic.'
