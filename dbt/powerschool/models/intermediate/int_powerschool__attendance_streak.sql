with
    att_mem as (
        select
            mem.studentid,
            mem.yearid,
            mem.calendardate,
            mem.attendancevalue,

            coalesce(att.att_code, 'P') as att_code,

            row_number() over (
                partition by mem.studentid, mem.yearid order by mem.calendardate asc
            ) as membership_day_number,
            row_number() over (
                partition by
                    mem.studentid, mem.yearid, safe_cast(mem.attendancevalue as string)
                order by mem.calendardate asc
            ) as rn_student_year_attendancevalue,

            row_number() over (
                partition by mem.studentid, mem.yearid, att.att_code
                order by mem.calendardate asc
            ) as rn_student_year_code,
        from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }} as mem
        left join
            {{ ref("int_powerschool__ps_attendance_daily") }} as att
            on mem.studentid = att.studentid
            and mem.calendardate = att.att_date
        where mem.membershipvalue = 1
    ),

    streaks_long as (
        select
            studentid,
            yearid,
            calendardate,
            att_code,
            attendancevalue,
            membership_day_number,
            rn_student_year_code,
            concat(
                studentid,
                '_',
                yearid,
                '_',
                att_code,
                '_',
                (membership_day_number - rn_student_year_code)
            ) as code_streak_id,
            concat(
                studentid,
                '_',
                yearid,
                '_',
                attendancevalue,
                '_',
                (membership_day_number - rn_student_year_attendancevalue)
            ) as att_streak_id,
        from att_mem
    ),

    streaks_agg as (
        select
            studentid,
            yearid,
            att_code,
            code_streak_id as streak_id,
            min(calendardate) as streak_start_date,
            max(calendardate) as streak_end_date,
            count(calendardate) as streak_length_membership,
        from streaks_long
        group by studentid, yearid, att_code, code_streak_id

        union all

        select
            studentid,
            yearid,
            safe_cast(attendancevalue as string) as att_code,
            att_streak_id as streak_id,
            min(calendardate) as streak_start_date,
            max(calendardate) as streak_end_date,
            count(calendardate) as streak_length_membership,
        from streaks_long
        group by studentid, yearid, attendancevalue, att_streak_id
    )

select
    *, date_diff(streak_end_date, streak_start_date, day) + 1 as streak_length_calendar,
from streaks_agg
