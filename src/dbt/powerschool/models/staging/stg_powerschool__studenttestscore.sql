with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("powerschool", "src_powerschool__studenttestscore"),
                partition_by="dcid.int_value",
                order_by="_file_name desc",
            )
        }}
    ),

    staging as (
        select
            dcid.int_value as dcid,
            id.int_value as id,
            studentid.int_value as studentid,
            testscoreid.int_value as testscoreid,
            studenttestid.int_value as studenttestid,
            numscore.double_value as numscore,
            percentscore.double_value as percentscore,
            readonly.int_value as `readonly`,
            alphascore,
            psguid,
            notes,
        from deduplicate
    )

select *,
from staging
