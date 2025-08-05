select
    dcid.int_value as dcid,
    grade_level.int_value as grade_level,
    id.int_value as id,
    schoolid.int_value as schoolid,
    studentid.int_value as studentid,
    termid.int_value as termid,
    testid.int_value as testid,
    test_date,
    psguid,
from {{ source("powerschool", "src_powerschool__studenttest") }}
