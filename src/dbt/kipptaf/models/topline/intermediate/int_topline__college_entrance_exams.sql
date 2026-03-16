{# TODO: add student/week scaffold #}
select
    school_specific_id,
    test_type,
    test_subject,
    score,
    dbt_scd_id,
    dbt_updated_at,
    dbt_valid_from,
    dbt_valid_to,
from {{ ref("snapshot_kippadb__standardized_test_rollup") }}
