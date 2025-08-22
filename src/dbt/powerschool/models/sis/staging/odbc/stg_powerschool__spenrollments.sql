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

            if(
                extract(month from enter_date) >= 7,
                extract(year from enter_date),
                extract(year from enter_date) - 1
            ) as academic_year,
        from {{ source("powerschool_odbc", "src_powerschool__spenrollments") }}
    )

select
    *,

    if(
        current_date('{{ var("local_timezone") }}') between enter_date and exit_date,
        true,
        false
    ) as is_current,

    row_number() over (
        partition by studentid, programid, academic_year order by enter_date desc
    ) as rn_student_program_year_desc,
from transformations
