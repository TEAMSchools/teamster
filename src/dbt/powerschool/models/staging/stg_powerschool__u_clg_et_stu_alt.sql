with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("powerschool", "src_powerschool__u_clg_et_stu_alt"),
                partition_by="id.int_value",
                order_by="_file_name desc",
            )
        }}
    ),

    transformations as (
        select
            * except (id, studentsdcid),

            /* column transformations */
            id.int_value as id,
            studentsdcid.int_value as studentsdcid,

            coalesce(whenmodified, whencreated) as when_modified_or_created,
        from deduplicate
    )

    {{
        dbt_utils.deduplicate(
            relation="transformations",
            partition_by="studentsdcid, exit_date",
            order_by="when_modified_or_created desc",
        )
    }}
