with
    terms_attendance_code as (
        select t.firstday, t.lastday, t.schoolid, t.yearid, ac.id,
        from {{ ref("stg_powerschool__terms") }} as t
        left join
            {{ ref("stg_powerschool__attendance_code") }} as ac
            on t.schoolid = ac.schoolid
            and t.yearid = ac.yearid
            and ac.description = 'Present'
        where t.isyearrec = 1
    ),

    aci as (
        select attendance_value, fteid, attendance_conversion_id, input_value,
        from {{ ref("stg_powerschool__attendance_conversion_items") }}
        where conversion_mode_code = 'codeday'
    )

select
    mv.studentid,
    mv.schoolid,
    mv.calendardate,
    mv.fteid,
    mv.attendance_conversion_id,
    mv.grade_level,
    mv.ontrack,
    mv.offtrack,
    mv.student_track,

    tac.yearid,

    if(ada_0.id is not null, 0, aci_real.attendance_value)
    * mv.ontrack as attendancevalue,

    if(ada_1.id is not null, 0, aci_potential.attendance_value)
    * mv.ontrack as potential_attendancevalue,

    case
        when adm_0.id is not null
        then 0
        when mv.studentmembership < mv.calendarmembership
        then mv.studentmembership
        else mv.calendarmembership
    end
    * mv.ontrack as membershipvalue,
from {{ ref("int_powerschool__ps_membership_reg") }} as mv
left join
    terms_attendance_code as tac
    on mv.calendardate between tac.firstday and tac.lastday
    and mv.schoolid = tac.schoolid
left join
    {{ ref("int_powerschool__ps_attendance_daily") }} as ada_0
    on mv.studentid = ada_0.studentid
    and mv.calendardate = ada_0.att_date
    and ada_0.count_for_ada = 0
left join
    {{ ref("int_powerschool__ps_attendance_daily") }} as ada_1
    on mv.studentid = ada_1.studentid
    and mv.calendardate = ada_1.att_date
    and ada_1.count_for_ada = 1
left join
    {{ ref("int_powerschool__ps_attendance_daily") }} as adm_0
    on mv.studentid = adm_0.studentid
    and mv.calendardate = adm_0.att_date
    and adm_0.count_for_adm = 0
left join
    aci as aci_real
    on mv.fteid = aci_real.fteid
    and mv.attendance_conversion_id = aci_real.attendance_conversion_id
    and ifnull(ada_1.attendance_codeid, tac.id) = aci_real.input_value
left join
    aci as aci_potential
    on mv.fteid = aci_potential.fteid
    and mv.attendance_conversion_id = aci_potential.attendance_conversion_id
    and tac.id = aci_potential.input_value
