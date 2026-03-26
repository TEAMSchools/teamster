{{
    config(
        severity="warn",
        store_failures=true,
        store_failures_as="view",
    )
}}

select *,
from {{ ref("rpt_gsheets__gpa_flags_report") }}
where test_failure_reason = 'unweighted exceeds weighted'
