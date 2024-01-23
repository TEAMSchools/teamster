with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("powerschool", "src_powerschool__studenttest"),
                partition_by="dcid.int_value",
                order_by="_file_name desc",
            )
        }}
    ),

    staging as (
        select
            dcid.int_value as dcid,
            grade_level.int_value as grade_level,
            id.int_value as id,
            schoolid.int_value as schoolid,
            studentid.int_value as studentid,
            termid.int_value as termid,
            testid.int_value as testid,
            test_date,
            psguid,
        from deduplicate
    )

select *,
from staging
