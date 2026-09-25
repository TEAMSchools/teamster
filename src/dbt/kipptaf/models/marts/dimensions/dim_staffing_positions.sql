with
    live_keys as (
        -- grain projection: one row per seat key; not a mask for upstream dups
        select distinct academic_year, staffing_model_id,
        from {{ ref("stg_google_appsheet__seat_tracker__seats") }}
    )

select
    {{ dbt_utils.generate_surrogate_key(["s.dbt_scd_id"]) }} as staffing_position_key,

    loc.location_key,

    if(
        s.teammate is not null
        and s.teammate not in (0, 1, 2, 999995, 999996, 999997, 999998, 999999),
        {{ dbt_utils.generate_surrogate_key(["s.teammate"]) }},
        cast(null as string)
    ) as incumbent_staff_key,

    if(
        s.recruiter is not null
        and s.recruiter not in (0, 1, 2, 999995, 999996, 999997, 999998, 999999),
        {{ dbt_utils.generate_surrogate_key(["s.recruiter"]) }},
        cast(null as string)
    ) as recruiter_staff_key,

    s.academic_year,
    s.recruitment_group,
    s.adp_dept as home_department_name,
    s.adp_title as title,
    s.staffing_status as status,
    s.status_detail,
    s.mid_year_hire as is_mid_year_hire,

    if(s.plan_status in ('Active', 'TRUE'), true, false) as is_active,

    cast(s.dbt_valid_from as date) as effective_start_date,
    cast(s.dbt_valid_to as date) as effective_end_date,
from {{ ref("snapshot_seat_tracker__seats") }} as s
inner join
    live_keys as lk
    on s.academic_year = lk.academic_year
    and s.staffing_model_id = lk.staffing_model_id
left join
    {{ ref("int_people__location_crosswalk") }} as loc
    on s.adp_location = loc.location_name
    and not loc.location_is_pathways
    and loc.location_clean_name <> 'KIPP Whittier Elementary'
