with
    terms as (
        select
            t.school_id,
            t.code,
            t.academic_year,

            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "t.`type`",
                        "t.code",
                        "t.`name`",
                        "t.`start_date`",
                        "t.region",
                        "t.school_id",
                    ]
                )
            }} as term_key,
        from {{ ref("stg_google_sheets__reporting__terms") }} as t
    ),

    daily as (
        select
            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "ada.student_number",
                        "ada._dbt_source_relation",
                        "ada.calendardate",
                    ]
                )
            }} as student_attendance_daily_key,

            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "enr.student_number",
                        "enr._dbt_source_relation",
                        "enr.academic_year",
                        "enr.entrydate",
                    ]
                )
            }} as student_enrollment_key,

            ada.calendardate as date_key,

            sch.location_key,

            t.term_key,

            ada.academic_year,

            ada.att_code as attendance_code,

            if(
                ada._dbt_source_project = 'kipppaterson' and ada.academic_year < 2026,
                null,
                ada.attendancevalue
            ) as attendance_value,
            if(
                ada._dbt_source_project = 'kipppaterson' and ada.academic_year < 2026,
                null,
                ada.membershipvalue
            ) as membership_value,

            if(
                ada._dbt_source_project = 'kipppaterson' and ada.academic_year < 2026,
                null,
                ada.is_present_weighted
            ) as present_weight,

            ada.is_truant,

            ada.semester,

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

            ada.student_number,
            ada.schoolid,

            enr.enroll_status,
        from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }} as ada
        inner join
            {{ ref("base_powerschool__student_enrollments") }} as enr
            on ada.studentid = enr.studentid
            and ada.schoolid = enr.schoolid
            and ada.calendardate >= enr.entrydate
            and ada.calendardate < enr.exitdate
            and {{ union_dataset_join_clause(left_alias="ada", right_alias="enr") }}
        left join
            {{ ref("stg_powerschool__schools") }} as sch
            on ada.schoolid = sch.school_number
            and {{ union_dataset_join_clause(left_alias="ada", right_alias="sch") }}
        left join
            terms as t
            on ada.schoolid = t.school_id
            and ada.term = t.code
            and ada.academic_year = t.academic_year
        where ada.calendardate <= current_date('{{ var("local_timezone") }}')
    ),

    running as (
        select
            *,

            avg(if(membership_value = 1, attendance_value, null)) over (
                partition by student_number, academic_year
                order by date_key asc
                rows between unbounded preceding and current row
            ) as _running_ada,
        from daily
    )

select
    student_attendance_daily_key,
    student_enrollment_key,
    student_number,

    date_key,
    location_key,
    term_key,

    academic_year,
    semester,
    enroll_status,

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

    if(_running_ada is null, null, _running_ada <= 0.90) as is_chronically_absent,

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

    not (
        academic_year = {{ var("current_academic_year") }} and enroll_status = 2
    ) as is_ca_eligible,

    row_number() over (partition by student_enrollment_key order by date_key desc)
    = 1 as is_latest_record,
from running
