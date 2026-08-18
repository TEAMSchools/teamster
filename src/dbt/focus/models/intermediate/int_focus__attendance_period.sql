select
    ap.id as student_attendance_period_id,
    ap.student_id,
    ap.school_date,
    ap.period_id,
    ap.course_period_id,
    ap.marking_period_id,
    ap.attendance_code,
    ap.attendance_teacher_code,
    ap.attendance_reason,
    ap.hourly_attendance,
    ap.hours,
    ap.minutes_present,
    ap.minutes_absent,
    ap.breaks,
    ap.break_minutes,
    ap.break_times,
    ap.break_out_time,
    ap.admin,
    ap.admin_user_id,
    ap.mass_assigned,
    ap.notified,
    ap.notified_callouts,
    ap.last_updated_user,
    ap.last_updated_date,
    ap.imported,

    -- attendance_period has no syear of its own; the marking period supplies
    -- both the year and the school
    mkp.syear as academic_year,
    mkp.school_id as schoolid,
    mkp.title as marking_period_title,
    mkp.short_name as marking_period_short_name,
    mkp.type as marking_period_type,
    mkp.start_date as marking_period_start_date,
    mkp.end_date as marking_period_end_date,

    ac.title as attendance_code_title,
    ac.short_name as attendance_code_short_name,
    ac.type as attendance_code_type,
    ac.state_code as attendance_code_state_code,
    ac.excused as attendance_code_excused,
    ac.tardy as attendance_code_tardy,
    ac.state_attendance_type as attendance_code_state_attendance_type,

    atc.title as attendance_teacher_code_title,
    atc.short_name as attendance_teacher_code_short_name,
    atc.state_code as attendance_teacher_code_state_code,
    atc.excused as attendance_teacher_code_excused,
    atc.tardy as attendance_teacher_code_tardy,

from {{ ref("stg_focus__attendance_period") }} as ap
left join
    {{ ref("stg_focus__marking_periods") }} as mkp
    on ap.marking_period_id = mkp.marking_period_id
-- both code columns are attendance_codes ids here, so no school/year scoping is
-- needed — unlike attendance_day, whose daily_code is a short_name
left join {{ ref("stg_focus__attendance_codes") }} as ac on ap.attendance_code = ac.id
left join
    {{ ref("stg_focus__attendance_codes") }} as atc
    on ap.attendance_teacher_code = atc.id
