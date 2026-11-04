with
    transformations as (
        select
            exit_code,
            whocreated,
            whencreated,
            whomodified,
            whenmodified,

            cast(exit_date as date) as exit_date,
            cast(id as int) as id,
            cast(studentsdcid as int) as studentsdcid,
            coalesce(whenmodified, whencreated) as when_modified_or_created,
        from {{ source("powerschool_dlt", "u_clg_et_stu") }}
    )

    {{
        dbt_utils.deduplicate(
            relation="transformations",
            partition_by="studentsdcid, exit_date",
            order_by="when_modified_or_created desc",
        )
    }}
