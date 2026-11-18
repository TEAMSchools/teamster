with
    transformations as (
        select
            de_course_name,
            de_semester,
            de_score,
            de_institution,

            cast(de_pass_yn as int) as de_pass_yn,
            cast(id as int) as id,
            cast(storedgradesdcid as int) as storedgradesdcid,
        from {{ source("powerschool_dlt", "u_storedgrades_de") }}
    )

    {{
        dbt_utils.deduplicate(
            relation="transformations",
            partition_by="storedgradesdcid, de_semester",
            order_by="(de_course_name is null) asc, (de_institution is null) asc, id desc",
        )
    }}
