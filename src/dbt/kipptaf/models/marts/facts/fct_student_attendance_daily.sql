with
    daily as (
        select
            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "ada.student_number",
                        "ada._dbt_source_project",
                        "ada.calendardate",
                    ]
                )
            }} as student_attendance_daily_key,

            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "ada.student_number",
                        "ada._dbt_source_project",
                        "ada.academic_year",
                        "ada.entrydate",
                    ]
                )
            }} as student_enrollment_key,

            ada.week_start_monday,

            ada.is_current_record,
            ada.is_enrollment_month_end_record,
            ada.is_enrollment_week_end_record,

            ada.calendardate as date_key,

            t.term_key,

            ada.att_code as attendance_code,

            ada.attendancevalue as attendance_value,
            ada.membershipvalue as membership_value,

            ada.is_present_weighted as present_weight,

            ada.is_truant,

            cast(ada.is_absent as int64) as is_absent,
            cast(ada.is_tardy as int64) as is_tardy,
            cast(ada.is_ontime as int64) as is_ontime,
            cast(ada.is_oss as int64) as is_oss,
            cast(ada.is_iss as int64) as is_iss,
            cast(ada.is_suspended as int64) as is_suspended,

            case
                when ada.is_oss = 1
                then 'Out-of-School Suspension'
                when ada.is_iss = 1
                then 'In-School Suspension'
                when ada.is_absent = 1
                then 'Absent'
                when ada.is_tardy = 1
                then 'Tardy'
                else 'Present'
            end as attendance_category,
        from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }} as ada
        left join
            {{ ref("dim_terms") }} as t
            on ada.schoolid = t.school_id
            and ada.term = t.term_name
            and ada.academic_year = t.academic_year
            and t.`type` = 'RT'
        where ada.calendardate <= current_date('{{ var("local_timezone") }}')
    ),

    running as (
        select
            *,

            avg(if(membership_value = 1, attendance_value, null)) over (
                partition by student_enrollment_key
                order by date_key asc
                rows between unbounded preceding and current row
            ) as _running_ada,
        from daily
    )

select
    student_attendance_daily_key,
    student_enrollment_key,

    date_key,
    term_key,

    is_current_record,
    is_enrollment_month_end_record,
    is_enrollment_week_end_record,

    attendance_code,
    attendance_value,
    membership_value,
    present_weight,

    is_truant,

    is_absent,
    is_tardy,
    is_ontime,
    is_oss,
    is_iss,
    is_suspended,

    attendance_category,

    if(_running_ada is null, null, _running_ada < 0.90) as is_chronically_absent,

    case
        when _running_ada is null
        then null
        when _running_ada >= 0.95
        then 'Tier 1'
        when _running_ada >= 0.90
        then 'Tier 2'
        when _running_ada >= 0.80
        then 'Tier 3'
        else 'Tier 4'
    end as ada_tier,

    row_number() over (partition by student_enrollment_key order by date_key desc)
    = 1 as is_latest_record,

    row_number() over (
        partition by student_enrollment_key, date_trunc(date_key, month)
        order by if(membership_value = 1, date_key, null) desc nulls last
    )
    = 1
    and membership_value = 1 as is_month_end_record,

    row_number() over (
        partition by student_enrollment_key, week_start_monday
        order by if(membership_value = 1, date_key, null) desc nulls last
    )
    = 1
    and membership_value = 1 as is_week_end_record,
from running
