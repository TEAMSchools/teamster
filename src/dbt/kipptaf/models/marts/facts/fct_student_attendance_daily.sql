with
    locations as (
        select powerschool_school_id, dagster_code_location, location_name,
        from {{ ref("stg_people__locations") }}
    ),

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
                "ada.student_number",
                "ada._dbt_source_relation",
                "ada.academic_year",
                "enr.entrydate",
            ]
        )
    }} as student_enrollment_key,

    ada.calendardate as date_key,

    {{ dbt_utils.generate_surrogate_key(["loc.location_name"]) }} as location_key,

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
from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }} as ada
inner join
    {{ ref("base_powerschool__student_enrollments") }} as enr
    on ada.studentid = enr.studentid
    and ada.schoolid = enr.schoolid
    and ada.calendardate >= enr.entrydate
    and ada.calendardate < enr.exitdate
    and {{ union_dataset_join_clause(left_alias="ada", right_alias="enr") }}
left join
    locations as loc
    on ada.schoolid = loc.powerschool_school_id
    and {{ extract_code_location("ada") }} = loc.dagster_code_location
left join
    terms as t
    on ada.schoolid = t.school_id
    and ada.term = t.code
    and ada.academic_year = t.academic_year

-- TODO: overlapping enrollment records at same school cause join
-- fan-out; qualify picks latest entrydate (#3633)
qualify
    row_number() over (
        partition by ada.student_number, ada._dbt_source_relation, ada.calendardate
        order by enr.entrydate desc
    )
    = 1
