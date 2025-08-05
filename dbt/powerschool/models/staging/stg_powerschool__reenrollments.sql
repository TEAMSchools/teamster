select
    * except (
        dcid,
        id,
        studentid,
        schoolid,
        grade_level,
        `type`,
        enrollmentcode,
        fulltimeequiv_obsolete,
        membershipshare,
        tuitionpayer,
        fteid
    ),

    /* column transformations */
    dcid.int_value as dcid,
    id.int_value as id,
    studentid.int_value as studentid,
    schoolid.int_value as schoolid,
    grade_level.int_value as grade_level,
    type.int_value as `type`,
    enrollmentcode.int_value as enrollmentcode,
    fulltimeequiv_obsolete.double_value as fulltimeequiv_obsolete,
    membershipshare.double_value as membershipshare,
    tuitionpayer.int_value as tuitionpayer,
    fteid.int_value as fteid,
from {{ source("powerschool", "src_powerschool__reenrollments") }}
