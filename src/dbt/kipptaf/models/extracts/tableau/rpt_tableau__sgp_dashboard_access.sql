with
    school_leader_access as (
        select
            school_leader_staff_key as staff_key,
            location_key,

            true as is_school_leader_access,
            false as is_head_of_school_access,
        from {{ ref("dim_locations") }}
        where school_leader_staff_key is not null
    ),

    head_of_school_access as (
        select
            h.head_of_school_staff_key as staff_key,

            l.location_key,

            false as is_school_leader_access,
            true as is_head_of_school_access,
        from {{ ref("dim_locations") }} as h
        inner join {{ ref("dim_locations") }} as l on h.region_key = l.region_key
        where h.head_of_school_staff_key is not null
    ),

    access as (
        select
            staff_key, location_key, is_school_leader_access, is_head_of_school_access,
        from school_leader_access

        union all

        select
            staff_key, location_key, is_school_leader_access, is_head_of_school_access,
        from head_of_school_access
    )

select
    a.location_key,

    s.active_directory_username as tableau_username,

    logical_or(a.is_school_leader_access) as is_school_leader_access,
    logical_or(a.is_head_of_school_access) as is_head_of_school_access,
from access as a
inner join
    {{ ref("dim_staff") }} as s
    on a.staff_key = s.staff_key
    and s.active_directory_username is not null
group by a.location_key, s.active_directory_username
