select
    psguid,

    cast(dcid as int) as dcid,
    cast(grade_level as int) as grade_level,
    cast(id as int) as id,
    cast(schoolid as int) as schoolid,
    cast(studentid as int) as studentid,
    cast(termid as int) as termid,
    cast(testid as int) as testid,
    cast(test_date as date) as test_date,
from {{ source("powerschool_dlt", "studenttest") }}
