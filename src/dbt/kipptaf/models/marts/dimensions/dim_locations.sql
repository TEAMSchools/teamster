with
    locations as (
        select
            *,

            count(*) over (
                partition by is_campus, powerschool_school_id
            ) as n_same_school_id,
        from {{ ref("stg_google_sheets__people__locations") }}
        where not is_pathways and location_name <> 'KIPP Whittier Elementary'
    )

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
    {{ staff_key("lc.sl_employee_number", nullable=true) }} as school_leader_staff_key,
    {{ staff_key("lc.dso_employee_number", nullable=true) }}
    as operations_director_staff_key,

    -- a school id the sheet repeats can't identify one school, so it stays null
    if(
        pl.is_campus or pl.n_same_school_id > 1, null, pl.powerschool_school_id
    ) as school_id,

    coalesce(pl.abbreviation, pl.location_name) as abbreviation,
from locations as pl
left join
    {{ ref("stg_google_sheets__people__campus_crosswalk") }} as cc
    on pl.location_name = cc.location_name
left join
    {{ ref("int_people__leadership_crosswalk") }} as lc
    on pl.powerschool_school_id = lc.home_work_location_powerschool_school_id
