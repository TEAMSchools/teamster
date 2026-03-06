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
        where not qa_flag
    ),

    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="cleaned_data",
                partition_by="enrollment_academic_year, finalsite_id, grouped_status",
                order_by="grouped_status_start_date desc",
            )
        }}
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
    is_enrolled_fdos,
    is_enrolled_oct01,
    is_enrolled_oct15,
    latest_status,
    aligned_enrollment_type,
    grouped_status_order,
    grouped_status_timeframe,
    grouped_status_start_date,

from cleaned_data
where grouped_status_timeframe = 'Ever'

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
    is_enrolled_fdos,
    is_enrolled_oct01,
    is_enrolled_oct15,
    latest_status,
    aligned_enrollment_type,
    grouped_status_order,
    grouped_status_timeframe,
    grouped_status_start_date,

from cleaned_data
where grouped_status_timeframe = 'Current' and latest_detailed_match
