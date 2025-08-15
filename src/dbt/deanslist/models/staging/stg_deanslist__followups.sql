with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("deanslist", "src_deanslist__followups"),
                partition_by="followupid",
                order_by="_file_name desc",
            )
        }}
    ),

    transformations as (
        select
            cast(nullif(followupid, '') as int) as followup_id,
            cast(nullif(extstatus, '') as int) as ext_status,
            cast(nullif(initby, '') as int) as init_by,
            cast(nullif(responseid, '') as int) as response_id,
            cast(nullif(schoolid, '') as int) as school_id,
            cast(nullif(sourceid, '') as int) as source_id,
            cast(nullif(studentid, '') as int) as student_id,
            cast(nullif(studentschoolid, '') as int) as student_school_id,
            cast(nullif(tickettypeid, '') as int) as ticket_type_id,

            cast(nullif(initts, '') as datetime) as init_ts,
            cast(nullif(opents, '') as datetime) as open_ts,
            cast(nullif(closets, '') as datetime) as close_ts,

            nullif(cfirst, '') as c_first,
            nullif(clast, '') as c_last,
            nullif(closeby, '') as close_by,
            nullif(cmiddle, '') as c_middle,
            nullif(ctitle, '') as c_title,
            nullif(firstname, '') as first_name,
            nullif(followupnotes, '') as followup_notes,
            nullif(followuptype, '') as followup_type,
            nullif(gradelevelshort, '') as grade_level_short,
            nullif(ifirst, '') as i_first,
            nullif(ilast, '') as i_last,
            nullif(imiddle, '') as i_middle,
            nullif(initnotes, '') as init_notes,
            nullif(ititle, '') as i_title,
            nullif(lastname, '') as last_name,
            nullif(longtype, '') as long_type,
            nullif(middlename, '') as middle_name,
            nullif(outstanding, '') as outstanding,
            nullif(responsetype, '') as response_type,
            nullif(ticketstatus, '') as ticket_status,
            nullif(tickettype, '') as ticket_type,
            nullif(`url`, '') as `url`,
        from deduplicate
    )

select *, concat(c_first, ' ', c_last) as c_first_last,
from transformations
