select
    `Name` as location_name,
    `Region` as business_unit,
    `PowerSchool_School_ID` as powerschool_school_id,
    `Reporting_School_ID` as reporting_school_id,
    `Grade_Band` as grade_band,
    `Is_Campus` as is_campus,
    `Is_Pathways` as is_pathways,
    `Abbreviation` as abbreviation,
    `Deanslist_School_ID` as deanslist_school_id,
    `Dagster_Code_Location` as dagster_code_location,
    `Head_of_Schools_Employee_Number` as head_of_schools_employee_number,
    `SmartRecruiters_Location_ID` as smartrecruiters_location_id,
    `Grow_Location_ID` as grow_location_id,
    `Campus_Name` as campus_name,
    `Address` as address,
    `City` as city,
    `Postal_Code` as postal_code,

    case
        `Dagster_Code_Location`
        when 'kippnewark'
        then 'Newark'
        when 'kippcamden'
        then 'Camden'
        when 'kippmiami'
        then 'Miami'
        when 'kipppaterson'
        then 'Paterson'
    end as region,
from {{ source("google_sheets", "src_google_sheets__people__locations") }}
