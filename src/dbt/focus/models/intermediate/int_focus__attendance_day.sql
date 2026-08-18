select
    ad.id as student_attendance_day_id,
    ad.syear as academic_year,
    ad.student_id,
    ad.school_date,
    ad.marking_period_id,
    ad.daily_code,
    ad.state_value,
    ad.minutes_present,
    ad.minutes_absent,
    ad.time_in,
    ad.time_out,
    ad.comment,
    ad.note_approved,
    ad.note_message,
    ad.notified_callouts,
    ad.admin_user_id,
    ad.last_updated_user,
    ad.last_updated_date,
    ad.imported,

    mkp.school_id as schoolid,
    mkp.title as marking_period_title,
    mkp.short_name as marking_period_short_name,
    mkp.type as marking_period_type,
    mkp.start_date as marking_period_start_date,
    mkp.end_date as marking_period_end_date,

    ac.id as daily_code_id,
    ac.title as daily_code_title,
    ac.type as daily_code_type,
    ac.state_code as daily_code_state_code,
    ac.excused as daily_code_excused,
    ac.tardy as daily_code_tardy,
    ac.chronic_absenteeism as daily_code_chronic_absenteeism,
    ac.truancy as daily_code_truancy,
    ac.state_attendance_type as daily_code_state_attendance_type,

from {{ ref("stg_focus__attendance_day") }} as ad
-- left, not inner: a few rows carry a marking_period_id that does not resolve,
-- and they must not drop. schoolid is null on those, so the code join below
-- yields null labels for them too.
left join
    {{ ref("stg_focus__marking_periods") }} as mkp
    on ad.marking_period_id = mkp.marking_period_id
-- daily_code holds a short_name, NOT an id — unlike attendance_period, whose
-- codes are ids. short_name is unique only within a school and year, so both
-- scope the join.
left join
    {{ ref("stg_focus__attendance_codes") }} as ac
    on ad.syear = ac.syear
    and mkp.school_id = ac.school_id
    and ad.daily_code = ac.short_name
