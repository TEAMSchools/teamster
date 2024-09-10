with
    transformations as (
        select
            * except (dcid, id, programid, schoolid, gradelevel, studentid),

            /* column transformations */
            dcid.int_value as dcid,
            id.int_value as id,
            programid.int_value as programid,
            schoolid.int_value as schoolid,
            gradelevel.int_value as gradelevel,
            studentid.int_value as studentid,

            {{
                teamster_utils.date_to_fiscal_year(
                    date_field="enter_date", start_month=7, year_source="start"
                )
            }} as academic_year,
        from {{ source("powerschool", "src_powerschool__spenrollments") }}
    )

    {{
        dbt_utils.deduplicate(
            relation="transformations",
            partition_by="studentid, programid, academic_year",
            order_by="enter_date desc",
        )
    }}
