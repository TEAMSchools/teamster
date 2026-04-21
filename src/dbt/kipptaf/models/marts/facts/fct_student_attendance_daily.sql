with
    locations as (
        select powerschool_school_id, dagster_code_location, location_name,
        from {{ ref("stg_people__locations") }}
        where not is_pathways and location_name <> 'KIPP Whittier Elementary'
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

    ada.student_number,
    ada.academic_year,

    ada.att_code as attendance_code,
    ada.attendancevalue as attendance_value,
    ada.membershipvalue as membership_value,

    ada.is_absent,
    ada.is_present_weighted,
    ada.is_tardy,
    ada.is_ontime,
    ada.is_oss,
    ada.is_iss,
    ada.is_suspended,
    ada.is_truant,

    ada.semester,
    ada.term,
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

-- TODO: overlapping enrollment records at same school cause join
-- fan-out; qualify picks latest entrydate (#3633)
qualify
    row_number() over (
        partition by ada.student_number, ada._dbt_source_relation, ada.calendardate
        order by enr.entrydate desc
    )
    = 1
