select
    lc.name as location_name,
    lc.clean_name as location_clean_name,
    lc.abbreviation as location_abbreviation,
    lc.grade_band as location_grade_band,
    lc.region as location_region,
    lc.powerschool_school_id as location_powerschool_school_id,
    lc.deanslist_school_id as location_deanslist_school_id,
    lc.reporting_school_id as location_reporting_school_id,
    lc.is_campus as location_is_campus,
    lc.is_pathways as location_is_pathways,
    lc.dagster_code_location as location_dagster_code_location,
    lc.head_of_schools_employee_number as location_head_of_schools_employee_number,

    cc.name as campus_name,

    ldap.sam_account_name as head_of_schools_sam_account_name,
from {{ ref("stg_people__location_crosswalk") }} as lc
left join
    {{ ref("stg_people__campus_crosswalk") }} as cc on lc.clean_name = cc.location_name
left join
    {{ ref("stg_ldap__user_person") }} as ldap
    on lc.head_of_schools_employee_number = ldap.employee_number
