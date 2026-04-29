select
    {{ dbt_utils.generate_surrogate_key(["`Name`"]) }} as location_key,

    `Name` as location_name,
    `Region` as location_region,
    `PowerSchool_School_ID` as powerschool_school_id,
    `Reporting_School_ID` as reporting_school_id,
    `Grade_Band` as grade_band,
    `Is_Campus` as is_campus,
    `Is_Pathways` as is_pathways,
    `Abbreviation` as abbreviation,
    `Deanslist_School_ID` as deanslist_school_id,
    `Dagster_Code_Location` as dagster_code_location,
    `Head_of_Schools_Employee_Number` as head_of_schools_employee_number,
    `ADP_Location_Code` as adp_location_code,
    `Grow_Location_ID` as grow_location_id,
    `Campus_Name` as campus_name,
    `Address` as address,
    `City` as city,
    `Postal_Code` as postal_code,

    case
        `Dagster_Code_Location`
        when 'kippnewark'
        then 'TEAM'
        when 'kippcamden'
        then 'KCNA'
        when 'kippmiami'
        then 'KIPP_MIAMI'
        when 'kipppaterson'
        then 'KPAT'
        else 'KIPP_TAF'
    end as business_unit_code,
from {{ source("google_sheets", "src_google_sheets__people__locations") }}
