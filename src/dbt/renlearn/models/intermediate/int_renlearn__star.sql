select
    *,

    row_number() over (
        partition by
            _dagster_partition_subject,
            _dagster_partition_fiscal_year,
            student_identifier,
            screening_period_window_name
        order by completed_date desc
    ) as rn_subject_round,

    row_number() over (
        partition by
            _dagster_partition_subject,
            _dagster_partition_fiscal_year,
            student_identifier
        order by completed_date desc
    ) as rn_subject_year,
from {{ ref("stg_renlearn__star") }}
