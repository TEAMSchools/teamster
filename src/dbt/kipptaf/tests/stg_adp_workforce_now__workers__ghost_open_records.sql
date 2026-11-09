-- depends_on: {{ ref("stg_adp_workforce_now__workers") }}
-- reads the raw source: the staging model drops these associates
with
    last_seen as (
        select
            associateoid as associate_oid,

            max(_dagster_partition_date) as last_seen_partition_date,
        from {{ source("adp_workforce_now", "src_adp_workforce_now__workers") }}
        group by associateoid
    ),

    partition_window as (
        select
            date_sub(
                max(last_seen_partition_date), interval 1 day
            ) as min_expected_last_seen_date,
        from last_seen
    )

select ls.associate_oid, ls.last_seen_partition_date,
from last_seen as ls
cross join partition_window as pw
where ls.last_seen_partition_date < pw.min_expected_last_seen_date
