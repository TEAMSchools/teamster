select
    storedgrades as stored_grades,

    /* records */
    startdate.timezone_type as start_date_timezone_type,
    enddate.timezone_type as end_date_timezone_type,

    /* transformations */
    cast(termid as int) as term_id,
    cast(academicyearid as int) as academic_year_id,
    cast(integrationid as int) as integration_id,
    cast(schoolid as int) as school_id,
    cast(secondaryintegrationid as int) as secondary_integration_id,
    cast(termtypeid as int) as term_type_id,

    nullif(academicyearname, '') as academic_year_name,
    nullif(`days`, '') as `days`,
    nullif(gradekey, '') as grade_key,
    nullif(secondarygradekey, '') as secondary_grade_key,
    nullif(termname, '') as term_name,
    nullif(termtype, '') as term_type,

    nullif(startdate.timezone, '') as start_date_timezone,
    nullif(enddate.timezone, '') as end_date_timezone,

    safe_cast(nullif(startdate.date, '') as datetime) as start_date_date,
    safe_cast(nullif(enddate.date, '') as datetime) as end_date_date,
from {{ source("deanslist", "src_deanslist__terms") }}
