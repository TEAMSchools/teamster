select
    cast(nullif(dlrosterid, '') as int) as dl_roster_id,
    cast(nullif(dlschoolid, '') as int) as dl_school_id,
    cast(nullif(dlstudentid, '') as int) as dl_student_id,
    cast(nullif(integrationid, '') as int) as integration_id,
    cast(nullif(secondaryintegrationid, '') as int) as secondary_integration_id,
    cast(nullif(secondarystudentid, '') as int) as secondary_student_id,
    cast(nullif(studentschoolid, '') as int) as student_school_id,

    nullif(firstname, '') as first_name,
    nullif(gradelevel, '') as grade_level,
    nullif(lastname, '') as last_name,
    nullif(middlename, '') as middle_name,
    nullif(rostername, '') as roster_name,
    nullif(schoolname, '') as school_name,
from {{ source("deanslist", "src_deanslist__roster_assignments") }}
