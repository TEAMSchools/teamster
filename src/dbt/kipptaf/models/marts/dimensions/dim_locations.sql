select
    pl.location_key,
    pl.location_name as `name`,
    pl.grade_band,
    pl.is_campus,
    pl.address,
    pl.city,
    pl.postal_code,

    cc.name as campus,

    {{ dbt_utils.generate_surrogate_key(["pl.business_unit_code"]) }} as region_key,

    {{ staff_key("lc.head_of_school_employee_number", nullable=true) }}
    as head_of_school_staff_key,

    coalesce(pl.abbreviation, pl.location_name) as abbreviation,
from {{ ref("stg_google_sheets__people__locations") }} as pl
left join
    {{ ref("stg_google_sheets__people__campus_crosswalk") }} as cc
    on pl.location_name = cc.location_name
left join
    {{ ref("int_people__leadership_crosswalk") }} as lc
    on pl.powerschool_school_id = lc.home_work_location_powerschool_school_id
where not pl.is_pathways and pl.location_name <> 'KIPP Whittier Elementary'
