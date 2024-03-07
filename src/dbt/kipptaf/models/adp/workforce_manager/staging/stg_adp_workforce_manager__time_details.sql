with
    source as (
        select
            _dagster_partition_date as symbolic_period_begin,
            location as budget_location,
            job,
            employee_payrule,
            transaction_type,
            transaction_apply_to,
            transaction_in_exceptions,
            transaction_out_exceptions,
            days,
            hours,
            money,
            _dagster_partition_fiscal_year - 1 as academic_year,
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
            if(location like '%/%', split(location, '/')[0], null) as org,
            if(location like '%/%', split(location, '/')[1], null) as payroll_code,
            if(location like '%/%', split(location, '/')[2], location) as location,
            if(location like '%/%', split(location, '/')[3], null) as department,
            if(
                transaction_in_exceptions = 'Missed In Punch', true, false
            ) as missed_in_punch,
            if(
                transaction_out_exceptions = 'Missed Out Punch', true, false
            ) as missed_out_punch,
        from
            {{
                source(
                    "adp_workforce_manager", "src_adp_workforce_manager__time_details"
                )
            }}
    )

select
    *,

    row_number() over (
        partition by worker_id, transaction_apply_date
        order by symbolic_period_begin desc, is_previous_sched_period desc
    ) as rn_worker_date,
from source
