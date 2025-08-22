select
    * except (
        dcid,
        enrollmentcode,
        fteid,
        grade_level,
        id,
        schoolid,
        studentid,
        tuitionpayer,
        `type`,
        fulltimeequiv_obsolete,
        membershipshare,
        entrydate,
        exitdate
    ),

    cast(dcid as int) as dcid,
    cast(enrollmentcode as int) as enrollmentcode,
    cast(fteid as int) as fteid,
    cast(grade_level as int) as grade_level,
    cast(id as int) as id,
    cast(schoolid as int) as schoolid,
    cast(studentid as int) as studentid,
    cast(tuitionpayer as int) as tuitionpayer,
    cast(`type` as int) as `type`,

    cast(fulltimeequiv_obsolete as float64) as fulltimeequiv_obsolete,
    cast(membershipshare as float64) as membershipshare,

    cast(entrydate as date) as entrydate,
    cast(exitdate as date) as exitdate,
from {{ source("powerschool_sftp", "src_powerschool__reenrollments") }}
