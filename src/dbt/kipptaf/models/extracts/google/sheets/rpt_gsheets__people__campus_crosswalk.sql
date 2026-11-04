select
    cc.`Location_Name`,
    cc.`Name`,

    pl.location_region as `Region`,
    pl.grade_band as `Grade_Band`,
    pl.powerschool_school_id as `PowerSchool_School_ID`,
    pl.reporting_school_id as `Reporting_School_ID`,
    pl.abbreviation as `Abbreviation`,
    pl.is_pathways as `Is_Pathways`,
from {{ ref("stg_google_sheets__people__campus_crosswalk") }} as cc
left join
    {{ ref("stg_google_sheets__people__locations") }} as pl
    on cc.`Location_Name` = pl.location_name
