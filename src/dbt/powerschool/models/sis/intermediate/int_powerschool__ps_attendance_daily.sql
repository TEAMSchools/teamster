select
    att.id,
    att.studentid,
    att.schoolid,
    att.att_date,
    att.attendance_codeid,
    att.att_mode_code,
    att.calendar_dayid,
    att.programid,
    att.total_minutes,

    ac.att_code,
    ac.presence_status_cd,
    ac.calculate_ada_yn as count_for_ada,
    ac.calculate_adm_yn as count_for_adm,

    cd.a,
    cd.b,
    cd.c,
    cd.d,
    cd.e,
    cd.f,
    cd.insession,
    cd.cycle_day_id,

    cy.abbreviation,
from {{ ref("stg_powerschool__attendance") }} as att
inner join
    {{ ref("stg_powerschool__attendance_code") }} as ac on att.attendance_codeid = ac.id
inner join
    {{ ref("stg_powerschool__calendar_day") }} as cd on att.calendar_dayid = cd.id
inner join {{ ref("stg_powerschool__cycle_day") }} as cy on cd.cycle_day_id = cy.id
where att.att_mode_code = 'ATT_ModeDaily'
