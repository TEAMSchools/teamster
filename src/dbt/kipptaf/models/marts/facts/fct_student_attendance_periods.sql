with
    daily as (
        select
            ada.student_number,
            ada._dbt_source_project,
            ada.academic_year,
            ada.calendardate,
            ada.membershipvalue,
            ada.attendancevalue,
            ada.is_truant,

            sch.location_key,

            date(ada.academic_year, 7, 1) as year_start_date,
        from {{ ref("int_students__attendance_daily") }} as ada
        inner join
            {{ ref("int_students__schools") }} as sch
            on ada.schoolid = sch.school_number
            and ada._dbt_source_project = sch._dbt_source_project
        where ada.calendardate <= current_date('{{ var("local_timezone") }}')
    ),

    aggregated as (
        select
            location_key,
            student_number,
            _dbt_source_project,
            academic_year,

            'year' as period_type,
            year_start_date as period_start_date,

            max(if(membershipvalue = 1, calendardate, null)) as period_end_date,

            sum(
                if(
                    membershipvalue = 1 and attendancevalue is not null,
                    membershipvalue,
                    0
                )
            ) as n_membership_days_ytd,

            sum(
                if(
                    membershipvalue = 1 and attendancevalue is not null,
                    attendancevalue,
                    0
                )
            ) as n_present_days_ytd,
        from daily
        group by
            location_key,
            student_number,
            _dbt_source_project,
            academic_year,
            period_type,
            period_start_date
        having max(if(membershipvalue = 1, calendardate, null)) is not null
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "student_number",
                "_dbt_source_project",
                "location_key",
                "period_type",
                "period_start_date",
            ]
        )
    }} as student_attendance_period_key,

    {{ dbt_utils.generate_surrogate_key(["student_number"]) }} as student_key,

    location_key,
    academic_year,
    period_type,
    period_start_date,
    period_end_date,
    n_membership_days_ytd,
    n_present_days_ytd,
from aggregated
