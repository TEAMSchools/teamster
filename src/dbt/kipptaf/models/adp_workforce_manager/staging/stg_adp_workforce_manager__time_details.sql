select
    _dagster_partition_date as symbolic_period_begin,
    employee_payrule,
    location,
    job,
    transaction_type,
    transaction_apply_to,
    transaction_in_exceptions,
    transaction_out_exceptions,
    days,
    hours,
    money,
    regexp_extract(employee_name, r'\((\w+)\)') as worker_id,
    parse_date('%b %d, %Y', transaction_apply_date) as transaction_apply_date,
    parse_datetime(
        '%b %d, %Y %I:%M %p', transaction_start_date_time
    ) as transaction_start_date_time,
    parse_datetime(
        '%b %d, %Y %I:%M %p', transaction_end_date_time
    ) as transaction_end_date_time,
    if(
        _dagster_partition_symbolic_id = 'Previous_SchedPeriod', true, false
    ) as is_previous_sched_period,
from {{ source("adp_workforce_manager", "src_adp_workforce_manager__time_details") }}
