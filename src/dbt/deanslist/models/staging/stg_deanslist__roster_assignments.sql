select
    safe_cast(nullif(dlrosterid, '') as int) as `dl_roster_id`,

    safe_cast(nullif(dlstudentid, '') as int) as `dl_student_id`,
    safe_cast(nullif(dlschoolid, '') as int) as `dl_school_id`,
    safe_cast(nullif(integrationid, '') as int) as `integration_id`,
    safe_cast(nullif(secondaryintegrationid, '') as int) as `secondary_integration_id`,
    safe_cast(nullif(secondarystudentid, '') as int) as `secondary_student_id`,
    safe_cast(nullif(studentschoolid, '') as int) as `student_school_id`,

    nullif(rostername, '') as `roster_name`,
    nullif(schoolname, '') as `school_name`,
    nullif(gradelevel, '') as `grade_level`,
    nullif(firstname, '') as `first_name`,
    nullif(middlename, '') as `middle_name`,
    nullif(lastname, '') as `last_name`,
from {{ source("deanslist", "src_deanslist__roster_assignments") }}
