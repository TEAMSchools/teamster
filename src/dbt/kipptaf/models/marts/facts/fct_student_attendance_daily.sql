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
    )

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
                "enr._dbt_source_project",
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
    ada.attendancevalue as attendance_value,
    ada.membershipvalue as membership_value,

    ada.is_present_weighted as present_weight,

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
from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }} as ada
inner join
    {{ ref("int_powerschool__student_enrollment_union") }} as enr
    on ada.studentid = enr.studentid
    and ada.schoolid = enr.schoolid
    and ada.calendardate >= enr.entrydate
    and ada.calendardate < enr.exitdate
    and ada._dbt_source_project = enr._dbt_source_project
left join
    {{ ref("stg_powerschool__schools") }} as sch
    on ada.schoolid = sch.school_number
    and ada._dbt_source_project = sch._dbt_source_project
left join
    terms as t
    on ada.schoolid = t.school_id
    and ada.term = t.code
    and ada.academic_year = t.academic_year
