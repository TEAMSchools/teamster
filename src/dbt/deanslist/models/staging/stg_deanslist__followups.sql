with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("deanslist", "src_deanslist__followups"),
                partition_by="FollowupID",
                order_by="_file_name desc",
            )
        }}
    )

select
    safe_cast(nullif(followupid, '') as int) as `followup_id`,
    nullif(cfirst, '') as `c_first`,
    nullif(clast, '') as `c_last`,
    nullif(closeby, '') as `close_by`,
    nullif(cmiddle, '') as `c_middle`,
    nullif(ctitle, '') as `c_title`,
    nullif(firstname, '') as `first_name`,
    nullif(followupnotes, '') as `followup_notes`,
    nullif(followuptype, '') as `followup_type`,
    nullif(gradelevelshort, '') as `grade_level_short`,
    nullif(ifirst, '') as `i_first`,
    nullif(ilast, '') as `i_last`,
    nullif(imiddle, '') as `i_middle`,
    nullif(initnotes, '') as `init_notes`,
    nullif(ititle, '') as `i_title`,
    nullif(lastname, '') as `last_name`,
    nullif(longtype, '') as `long_type`,
    nullif(middlename, '') as `middle_name`,
    nullif(outstanding, '') as `outstanding`,
    nullif(responsetype, '') as `response_type`,
    nullif(ticketstatus, '') as `ticket_status`,
    nullif(tickettype, '') as `ticket_type`,
    nullif(tickettypeid, '') as `ticket_type_id`,
    nullif(`url`, '') as `url`,
    safe_cast(nullif(closets, '') as datetime) as `close_ts`,
    safe_cast(nullif(extstatus, '') as int) as `ext_status`,
    safe_cast(nullif(initby, '') as int) as `init_by`,
    safe_cast(nullif(initts, '') as datetime) as `init_ts`,
    safe_cast(nullif(opents, '') as datetime) as `open_ts`,
    safe_cast(nullif(responseid, '') as int) as `response_id`,
    safe_cast(nullif(schoolid, '') as int) as `school_id`,
    safe_cast(nullif(sourceid, '') as int) as `source_id`,
    safe_cast(nullif(studentid, '') as int) as `student_id`,
    safe_cast(nullif(studentschoolid, '') as int) as `student_school_id`,
from deduplicate
