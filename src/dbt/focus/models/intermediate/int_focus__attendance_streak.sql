with
    -- studentid is null on the Focus side, and generate_surrogate_key maps null
    -- to a single constant -- hashing it would collapse every Focus student into
    -- one streak per year and code. student_number is the key throughout.
    att_mem as (
        select
            student_number,
            yearid,
            calendardate,
            attendancevalue,

            '{{ project_name }}' as project_name,

            coalesce(att_code, 'P') as att_code,

            row_number() over (
                partition by student_number, yearid order by calendardate asc
            ) as membership_day_number,

            row_number() over (
                partition by student_number, yearid, cast(attendancevalue as string)
                order by calendardate asc
            ) as rn_student_year_attendancevalue,

            row_number() over (
                partition by student_number, yearid, att_code order by calendardate asc
            ) as rn_student_year_code,
        from {{ ref("int_focus__attendance_daily") }}
        where membershipvalue = 1
    ),

    streaks_long as (
        select
            student_number,
            yearid,
            calendardate,
            att_code,
            attendancevalue,
            membership_day_number,
            rn_student_year_code,

            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "'code'",
                        "project_name",
                        "student_number",
                        "yearid",
                        "att_code",
                        "(membership_day_number - rn_student_year_code)",
                    ]
                )
            }} as code_streak_id,

            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "'att'",
                        "project_name",
                        "student_number",
                        "yearid",
                        "attendancevalue",
                        "(membership_day_number - rn_student_year_attendancevalue)",
                    ]
                )
            }} as att_streak_id,
        from att_mem
    ),

    streaks_agg as (
        select
            student_number,
            yearid,
            att_code,
            code_streak_id as streak_id,

            min(calendardate) as streak_start_date,
            max(calendardate) as streak_end_date,
            count(calendardate) as streak_length_membership,
        from streaks_long
        group by student_number, yearid, att_code, code_streak_id

        union all

        select
            student_number,
            yearid,

            cast(attendancevalue as string) as att_code,

            att_streak_id as streak_id,

            min(calendardate) as streak_start_date,
            max(calendardate) as streak_end_date,
            count(calendardate) as streak_length_membership,
        from streaks_long
        group by student_number, yearid, attendancevalue, att_streak_id
    )

select
    *,

    -- Projected null so the kipptaf union matches the PowerSchool branch column
    -- for column.
    cast(null as int64) as studentid,

    date_diff(streak_end_date, streak_start_date, day) + 1 as streak_length_calendar,
from streaks_agg
