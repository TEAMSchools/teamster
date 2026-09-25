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
    ),

    -- grain projection onto finalsite_enrollment_id, which the source repeats
    -- across Dagster partitions. Deliberately unscoped by year: a record filed
    -- under any cycle still means Finalsite knows the student.
    finalsite_records as (
        select distinct finalsite_enrollment_id,
        from {{ ref("stg_finalsite__status_report") }}
    ),

    finalsite_contact_ids as (
        select
            _dbt_source_project,
            finalsite_enrollment_id,

            cast(focus_student_id_prefixed as int) as focus_student_id,
        from {{ ref("int_finalsite__contact_id_attributes") }}
    ),

    sis_enrollments as (
        select
            e.academic_year,
            e.academic_year_display,
            e.region,
            e.schoolid,
            e.school,
            e.student_number,
            e.student_first_name,
            e.student_last_name,
            e.grade_level,
            e.enroll_status,

            -- Miami rows carry no infosnap_id, so their Finalsite identity
            -- comes from the contact-id crosswalk instead.
            coalesce(e.infosnap_id, c.finalsite_enrollment_id) as sis_finalsite_id,

        from {{ ref("int_extracts__student_enrollments") }} as e
        left join
            finalsite_contact_ids as c
            on e.student_number = c.focus_student_id
            and e._dbt_source_project = c._dbt_source_project
        where
            e.rn_year = 1
            and e.enroll_status = 0
            and e.academic_year = {{ var("finalsite_recruitment_year") }}
    ),

    sis_only as (
        select
            e.academic_year as enrollment_academic_year,
            e.academic_year_display as enrollment_academic_year_display,
            e.region,
            e.schoolid,
            e.school,
            e.student_number as powerschool_student_number,
            e.student_first_name as first_name,
            e.student_last_name as last_name,
            e.grade_level,
            e.enroll_status as sis_enroll_status,
            e.grade_level as sis_grade_level,
            e.schoolid as sis_schoolid,
            e.school as sis_school,

            'KTAF' as org,
            'is_missing_finalsite_record' as flag_name,
            true as flag_value,

            cast(null as string) as finalsite_id,
            cast(null as string) as self_contained,
            cast(null as string) as enrollment_type,
            cast(null as string) as latest_status,
            cast(null as int64) as finalsite_expected_enroll_status,

        from sis_enrollments as e
        left join
            finalsite_records as f on e.sis_finalsite_id = f.finalsite_enrollment_id
        where f.finalsite_enrollment_id is null
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
            is_enroll_status_mismatch,
            is_grade_level_mismatch,
            is_school_mismatch,
            is_missing_sis_record
        )
    )
where flag_value

union all

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

from sis_only
