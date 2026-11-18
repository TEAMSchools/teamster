with
    enrolled_school_years as (
        -- grain projection, not dup-masking
        select distinct schoolid, yearid,
        from {{ ref("int_powerschool__ps_membership_reg") }}
    )

select esy.schoolid, esy.yearid,
from enrolled_school_years as esy
left join
    {{ ref("stg_powerschool__attendance_code") }} as ac
    on esy.schoolid = ac.schoolid
    and esy.yearid = ac.yearid
    and ac.description = 'Present'
where ac.id is null
