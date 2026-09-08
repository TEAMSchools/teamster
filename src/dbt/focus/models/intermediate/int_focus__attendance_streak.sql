with
    att_mem as (
        select
            student_number,
            academic_year,
            school_date,
            state_value,
            daily_code,

            '{{ project_name }}' as project_name,

            row_number() over (
                partition by student_number, academic_year order by school_date asc
            ) as membership_day_number,

            row_number() over (
                partition by student_number, academic_year, cast(state_value as string)
                order by school_date asc
            ) as rn_student_year_state_value,

            row_number() over (
                partition by student_number, academic_year, daily_code
                order by school_date asc
            ) as rn_student_year_code,
        from {{ ref("int_focus__attendance_daily") }}
    ),

    streaks_long as (
        select
            student_number,
            academic_year,
            school_date,
            daily_code,
            state_value,
            membership_day_number,
            rn_student_year_code,

            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "'code'",
                        "project_name",
                        "student_number",
                        "academic_year",
                        "daily_code",
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
                        "academic_year",
                        "state_value",
                        "(membership_day_number - rn_student_year_state_value)",
                    ]
                )
            }} as att_streak_id,
        from att_mem
    ),

    -- streak_type distinguishes the two families that used to share one
    -- overloaded column: 'daily_code' rows group on the raw Focus code (null
    -- is its own group, so a present streak's streak_value is null), 'state_value'
    -- rows group on the stringified present/absent value.
    streaks_agg as (
        select
            student_number,
            academic_year,

            'daily_code' as streak_type,
            daily_code as streak_value,

            code_streak_id as streak_id,

            min(school_date) as streak_start_date,
            max(school_date) as streak_end_date,
            count(school_date) as streak_length_days,
        from streaks_long
        group by student_number, academic_year, daily_code, code_streak_id

        union all

        select
            student_number,
            academic_year,

            'state_value' as streak_type,
            cast(state_value as string) as streak_value,

            att_streak_id as streak_id,

            min(school_date) as streak_start_date,
            max(school_date) as streak_end_date,
            count(school_date) as streak_length_days,
        from streaks_long
        group by student_number, academic_year, state_value, att_streak_id
    )

select
    *,

    date_diff(streak_end_date, streak_start_date, day)
    + 1 as streak_length_calendar_days,
from streaks_agg
