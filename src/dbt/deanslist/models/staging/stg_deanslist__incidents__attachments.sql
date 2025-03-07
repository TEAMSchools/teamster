select
    i.incident_id,

    a.attachmenttype as attachment_type,
    a.contenttype as content_type,
    a.entityname as entity_name,
    a.entitytype as entity_type,
    a.internalfilename as internal_filename,
    a.internalfolder as internal_folder,
    a.minuserlevel as min_user_level,
    a.minuserlevelgroupname as min_user_level_group_name,
    a.publicfilename as public_filename,
    a.reporttype as report_type,
    a.sourcetype as source_type,
    a.url,

    a.filepostedat.timezone as file_posted_at__timezone,
    a.filepostedat.timezone_type as file_posted_at__timezone_type,

    cast(a.attachmentid as int) as attachment_id,
    cast(a.bytes as int) as bytes,
    cast(a.entityid as int) as entity_id,
    cast(a.schoolid as int) as school_id,
    cast(a.sourceid as int) as source_id,
    cast(a.studentid as int) as student_id,
    cast(a.termid as int) as term_id,

    cast(a.reportdate as date) as report_date,

    cast(a.filepostedat.`date` as datetime) as file_posted_at__date,
from {{ ref("stg_deanslist__incidents") }} as i
cross join unnest(i.attachments) as a
