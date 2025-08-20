{{ config(enabled=(var("powerschool_external_source_type") == "odbc")) }}

with
    transformations as (
        select
            * except (id, studentsdcid),

            /* column transformations */
            id.int_value as id,
            studentsdcid.int_value as studentsdcid,

            coalesce(whenmodified, whencreated) as when_modified_or_created,
        from {{ source("powerschool_odbc", "src_powerschool__u_clg_et_stu") }}
    )

    {{
        dbt_utils.deduplicate(
            relation="transformations",
            partition_by="studentsdcid, exit_date",
            order_by="when_modified_or_created desc",
        )
    }}
