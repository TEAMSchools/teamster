with
    fte_conversion as (
        -- grain projection, not dup-masking
        select distinct mr.schoolid, mr.yearid, mr.fteid, mr.attendance_conversion_id,
        from {{ ref("int_powerschool__ps_membership_reg") }} as mr
        inner join
            {{ ref("stg_powerschool__fte") }} as f
            on mr.fteid = f.id
            and mr.schoolid = f.schoolid
            and mr.yearid = f.yearid
    )

select
    fc.schoolid,
    fc.yearid,
    fc.fteid,
    fc.attendance_conversion_id,

    ac.id as attendance_codeid,
    ac.att_code,
from fte_conversion as fc
inner join
    {{ ref("stg_powerschool__attendance_code") }} as ac
    on fc.schoolid = ac.schoolid
    and fc.yearid = ac.yearid
    and ac.calculate_ada_yn = 1
left join
    {{ ref("stg_powerschool__attendance_conversion_items") }} as aci
    on fc.fteid = aci.fteid
    and fc.attendance_conversion_id = aci.attendance_conversion_id
    and ac.id = aci.input_value
    and aci.conversion_mode_code = 'codeday'
where aci.id is null
