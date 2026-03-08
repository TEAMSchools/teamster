with
    -- trunk-ignore(sqlfluff/ST03)
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
            enroll_status,
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
    enroll_status,
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

    case
        grouped_status
        when 'Applications'
        then 'App Target'
        when 'Inquiries'
        then 'Inquiries'
        when 'Offers'
        then 'Offers Target'
        else grouped_status
    end as goal_name,

from deduplicate as d
where d.grouped_status_timeframe = 'Ever'

union all

select
    d.enrollment_academic_year,
    d.enrollment_academic_year_display,
    d.org,
    d.region,
    d.schoolid,
    d.school,
    d.finalsite_id,
    d.powerschool_student_number,
    d.first_name,
    d.last_name,
    d.grade_level,
    d.enroll_status,
    d.gender,
    d.birthdate,
    d.self_contained,
    d.enrollment_type,
    d.grouped_status,
    d.is_enrolled_fdos,
    d.is_enrolled_oct01,
    d.is_enrolled_oct15,
    d.latest_status,
    d.aligned_enrollment_type,
    d.grouped_status_order,
    d.grouped_status_timeframe,
    d.grouped_status_start_date,

    d.latest_status as goal_name,

from deduplicate as d
where d.grouped_status_timeframe = 'Current' and d.latest_detailed_match

union all

select
    d.enrollment_academic_year,
    d.enrollment_academic_year_display,
    d.org,
    d.region,
    d.schoolid,
    d.school,
    d.finalsite_id,
    d.powerschool_student_number,
    d.first_name,
    d.last_name,
    d.grade_level,
    d.enroll_status,
    d.gender,
    d.birthdate,
    d.self_contained,
    d.enrollment_type,
    d.grouped_status,
    d.is_enrolled_fdos,
    d.is_enrolled_oct01,
    d.is_enrolled_oct15,
    d.latest_status,
    d.aligned_enrollment_type,
    d.grouped_status_order,
    d.grouped_status_timeframe,
    d.grouped_status_start_date,

    pending_offers_cat as goal_name,

from deduplicate as d
cross join unnest(['>= 4 Days', '>= 5 & <= 10 Days', '> 10 Days']) as pending_offers_cat
where
    d.grouped_status_timeframe = 'Current'
    and d.latest_detailed_match
    and d.grouped_status = 'Pending Offers'
