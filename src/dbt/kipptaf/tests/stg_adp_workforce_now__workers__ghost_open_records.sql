with
    partition_window as (
        select
            date_sub(
                max(last_seen_partition_date), interval 1 day
            ) as min_expected_last_seen_date,
        from {{ ref("stg_adp_workforce_now__workers") }}
    )

select w.associate_oid, w.last_seen_partition_date,
from {{ ref("stg_adp_workforce_now__workers") }} as w
cross join partition_window as pw
where
    w.effective_date_end = '9999-12-31'
    and w.last_seen_partition_date < pw.min_expected_last_seen_date
