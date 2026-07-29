with
    staging as (
        select
            code1,
            code2,
            exitcode,
            sp_comment,
            psguid,

            cast(dcid as int) as dcid,
            cast(enter_date as date) as enter_date,
            cast(exit_date as date) as exit_date,
            cast(id as int) as id,
            cast(programid as int) as programid,
            cast(schoolid as int) as schoolid,
            cast(gradelevel as int) as gradelevel,
            cast(studentid as int) as studentid,
        from {{ source("powerschool_dlt", "spenrollments") }}
    ),

    transformations as (
        select
            *,

            if(
                extract(month from enter_date) >= 7,
                extract(year from enter_date),
                extract(year from enter_date) - 1
            ) as academic_year,

            if(
                current_date('{{ var("local_timezone") }}')
                between enter_date and exit_date,
                true,
                false
            ) as is_current,
        from staging
    )

select
    *,

    row_number() over (
        partition by studentid, programid, academic_year order by enter_date desc
    ) as rn_student_program_year_desc,
from transformations
