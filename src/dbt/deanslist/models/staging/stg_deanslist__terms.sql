select
    safe_cast(nullif(termid, '') as int) as `term_id`,

    safe_cast(nullif(academicyearid, '') as int) as `academic_year_id`,
    safe_cast(nullif(integrationid, '') as int) as `integration_id`,
    safe_cast(nullif(schoolid, '') as int) as `school_id`,
    safe_cast(nullif(secondaryintegrationid, '') as int) as `secondary_integration_id`,
    safe_cast(nullif(termtypeid, '') as int) as `term_type_id`,

    nullif(academicyearname, '') as `academic_year_name`,
    nullif(`days`, '') as `days`,
    nullif(gradekey, '') as `grade_key`,
    nullif(secondarygradekey, '') as `secondary_grade_key`,
    nullif(termname, '') as `term_name`,
    nullif(termtype, '') as `term_type`,

    storedgrades as `stored_grades`,

    {# records #}
    startdate.timezone_type as `start_date_timezone_type`,
    nullif(startdate.timezone, '') as `start_date_timezone`,
    safe_cast(nullif(startdate.date, '') as datetime) as `start_date_date`,
    enddate.timezone_type as `end_date_timezone_type`,
    nullif(enddate.timezone, '') as `end_date_timezone`,
    safe_cast(nullif(enddate.date, '') as datetime) as `end_date_date`,
from {{ source("deanslist", "src_deanslist__terms") }}
