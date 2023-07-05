with
    spenrollments_gen as (
        select
            sp.dcid,
            sp.id,
            sp.studentid,
            sp.programid,
            sp.gradelevel,
            sp.sp_comment,
            sp.enter_date,
            sp.exit_date,
            sp.exitcode,
            {{
                teamster_utils.date_to_fiscal_year(
                    date_field="sp.enter_date", start_month=7, year_source="start"
                )
            }} as academic_year,

            gen.name as specprog_name,
        from {{ ref("stg_powerschool__spenrollments") }} as sp
        inner join
            {{ ref("stg_powerschool__gen") }} as gen
            on sp.programid = gen.id
            and gen.cat = 'specprog'
    ),

    deuplicate as (
        {{
            dbt_utils.deduplicate(
                relation="spenrollments_gen",
                partition_by="studentid, programid, academic_year",
                order_by="enter_date desc",
            )
        }}
    )

select *
from deuplicate
