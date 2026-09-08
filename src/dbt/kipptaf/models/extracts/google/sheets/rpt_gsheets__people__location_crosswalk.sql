select
    location_name as `Name`,
    location_clean_name as `Clean_Name`,
    location_abbreviation as `Abbreviation`,
    location_grade_band as `Grade_Band`,
    location_region as `Region`,
    location_powerschool_school_id as `PowerSchool_School_ID`,
    location_deanslist_school_id as `Deanslist_School_ID`,
    location_reporting_school_id as `Reporting_School_ID`,
    location_is_campus as `Is_Campus`,
    location_is_pathways as `Is_Pathways`,
    location_dagster_code_location as `Dagster_Code_Location`,
    location_head_of_schools_employee_number as `Head_of_Schools_Employee_Number`,
from {{ ref("int_people__location_crosswalk") }}
