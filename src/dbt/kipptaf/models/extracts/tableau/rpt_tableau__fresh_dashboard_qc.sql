with
    -- grain projection: every column here is functionally determined by
    -- (enrollment_academic_year, finalsite_id); the source carries one row per
    -- (goal_type, goal_name) grouping, neither of which is projected, so those
    -- collapse to one byte-identical tuple. Not a mask for upstream duplicates.
    roster as (
        select distinct
            enrollment_academic_year,
            enrollment_academic_year_display,
            org,
            region,
            schoolid,
            school,
            finalsite_id,
            powerschool_student_number,
            first_name,
            last_name,
            grade_level,
            self_contained,
            enrollment_type,
            latest_status,
            enroll_status as sis_enroll_status,
            sis_grade_level,
            sis_schoolid,
            sis_school,
            finalsite_expected_enroll_status,
            is_same_day_status_tie,
            is_enroll_status_mismatch,
            is_grade_level_mismatch,
            is_school_mismatch,

            if(
                finalsite_expected_enroll_status = 0 and enroll_status is null,
                true,
                false
            ) as is_missing_sis_record,

        from {{ ref("int_tableau__finalsite_student_scaffold") }}
        where grouped_status_timeframe = 'Current'
    )

select
    enrollment_academic_year,
    enrollment_academic_year_display,
    org,
    region,
    schoolid,
    school,
    finalsite_id,
    powerschool_student_number,
    first_name,
    last_name,
    grade_level,
    self_contained,
    enrollment_type,
    latest_status,
    sis_enroll_status,
    sis_grade_level,
    sis_schoolid,
    sis_school,
    finalsite_expected_enroll_status,

    flag_name,
    flag_value,

from
    roster unpivot (
        flag_value for flag_name in (
            is_same_day_status_tie,
            is_enroll_status_mismatch,
            is_grade_level_mismatch,
            is_school_mismatch,
            is_missing_sis_record
        )
    )
where flag_value
