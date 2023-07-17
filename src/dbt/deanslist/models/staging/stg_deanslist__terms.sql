select
    nullif(academicyearid, '') as `academic_year_id`,
    nullif(academicyearname, '') as `academic_year_name`,
    nullif(`days`, '') as `days`,
    nullif(gradekey, '') as `grade_key`,
    nullif(integrationid, '') as `integration_id`,
    nullif(schoolid, '') as `school_id`,
    nullif(secondarygradekey, '') as `secondary_grade_key`,
    nullif(secondaryintegrationid, '') as `secondary_integration_id`,
    nullif(termid, '') as `term_id`,
    nullif(termname, '') as `term_name`,
    nullif(termtype, '') as `term_type`,
    nullif(termtypeid, '') as `term_type_id`,
    storedgrades as `stored_grades`,

    {# records #}
    startdate.timezone_type as `start_date_timezone_type`,
    nullif(startdate.timezone, '') as `start_date_timezone`,
    safe_cast(nullif(startdate.date, '') as datetime) as `start_date_date`,
    enddate.timezone_type as `end_date_timezone_type`,
    nullif(enddate.timezone, '') as `end_date_timezone`,
    safe_cast(nullif(enddate.date, '') as datetime) as `end_date_date`,
from {{ source("deanslist", "src_deanslist__terms") }}
