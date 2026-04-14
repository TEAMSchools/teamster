with
    locations as (
        -- TODO: int_people__location_crosswalk has duplicate rows (#3633)
        select distinct
            location_powerschool_school_id,
            location_dagster_code_location,
            location_clean_name,
        from {{ ref("int_people__location_crosswalk") }}
        where
            not location_is_pathways
            and location_clean_name <> 'KIPP Whittier Elementary'
    )

select
    {{ dbt_utils.generate_surrogate_key(["ada.student_number", "ada.calendardate"]) }}
    as student_attendance_daily_key,

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

    {{ dbt_utils.generate_surrogate_key(["loc.location_clean_name"]) }} as location_key,

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
    and ada.calendardate between enr.entrydate and enr.exitdate
    and {{ union_dataset_join_clause(left_alias="ada", right_alias="enr") }}
left join
    locations as loc
    on ada.schoolid = loc.location_powerschool_school_id
    and {{ extract_code_location("ada") }} = loc.location_dagster_code_location
