with
    cleaned_data as (
        select
            enrollment_academic_year,
            enrollment_academic_year_display,
            org,
            region,
            schoolid,
            finalsite_enrollment_id as finalsite_id,
            powerschool_student_number,
            first_name,
            last_name,
            grade_level,
            gender,
            birthdate,
            self_contained,
            enrollment_type,
            status_group_value as grouped_status,
            grouped_status_order,
            grouped_status_timeframe,
            qa_flag,
            ps_grade_level,
            ps_school,
            ps_region,
            is_enrolled_fdos,
            is_enrolled_oct01,
            is_enrolled_oct15,
            latest_status,

            'All' as aligned_enrollment_type,

            if(latest_status = detailed_status, true, false) as latest_detailed_match,

            if(
                status_group_value in ('Inquiries', 'Applications'), region, school
            ) as school,

            max(status_start_date) over (
                partition by
                    enrollment_academic_year,
                    finalsite_enrollment_id,
                    status_group_value
            ) as grouped_status_start_date,

        from {{ ref("int_students__finalsite_student_roster") }}
        qualify
            row_number() over (
                partition by
                    enrollment_academic_year,
                    finalsite_enrollment_id,
                    status_group_value
                order by grouped_status_order asc
            )
            = 1
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
    gender,
    birthdate,
    self_contained,
    enrollment_type,
    grouped_status,
    ps_grade_level,
    ps_school,
    ps_region,
    is_enrolled_fdos,
    is_enrolled_oct01,
    is_enrolled_oct15,
    latest_status,
    aligned_enrollment_type,
    grouped_status_order,
    grouped_status_timeframe,
    grouped_status_start_date,

from cleaned_data
where grouped_status_timeframe = 'Ever' and not qa_flag

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
    gender,
    birthdate,
    self_contained,
    enrollment_type,
    grouped_status,
    ps_grade_level,
    ps_school,
    ps_region,
    is_enrolled_fdos,
    is_enrolled_oct01,
    is_enrolled_oct15,
    latest_status,
    aligned_enrollment_type,
    grouped_status_order,
    grouped_status_timeframe,
    grouped_status_start_date,

from cleaned_data
where grouped_status_timeframe = 'Current' and latest_detailed_match and not qa_flag
