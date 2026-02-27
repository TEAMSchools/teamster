with
    stacked_data as (

        /* denominator groupings for inquiries, applications, waitlisted, offers,
           assigned school and accepted. need distinct to bring only one row per
           student when they have multiple statuses per group */
        select distinct
            aligned_enrollment_academic_year,
            aligned_enrollment_academic_year_display,
            enrollment_academic_year,
            enrollment_academic_year_display,
            current_academic_year,
            next_academic_year,
            org,
            region,
            schoolid,
            school,
            finalsite_enrollment_id as finalsite_id,
            powerschool_student_number,
            first_name,
            last_name,
            grade_level,
            aligned_enrollment_academic_year_grade_level,
            self_contained,
            enrollment_academic_year_enrollment_type,
            status_group_denominator as grouped_status,
            sre_academic_year_start,
            sre_academic_year_end,
            is_enrolled_fdos,
            is_enrolled_oct01,
            is_enrolled_oct15,
            latest_status,

            'All' as aligned_enrollment_type,

            case
                status_group_denominator
                when 'Inquiries'
                then 1
                when 'Applications'
                then 2
                when 'Offers'
                then 3
                when 'Accepted'
                then 5
                else 0
            end as grouped_status_order,

            max(status_start_date) over (
                partition by
                    enrollment_academic_year,
                    finalsite_enrollment_id,
                    status_group_denominator
            ) as grouped_status_start_date,

        from {{ ref("int_students__finalsite_student_roster") }}
        where
            status_group_denominator is not null
            and status_start_date is not null
            and not qa_flag

        union all

        /* denominator for conversion metrics groupings need distinct to bring only
           one row per student when they have multiple statuses per group */
        select distinct
            aligned_enrollment_academic_year,
            aligned_enrollment_academic_year_display,
            enrollment_academic_year,
            enrollment_academic_year_display,
            current_academic_year,
            next_academic_year,
            org,
            region,
            schoolid,
            school,
            finalsite_enrollment_id as finalsite_id,
            powerschool_student_number,
            first_name,
            last_name,
            grade_level,
            aligned_enrollment_academic_year_grade_level,
            self_contained,
            enrollment_academic_year_enrollment_type,
            conversion_metric_denominator as grouped_status,
            sre_academic_year_start,
            sre_academic_year_end,
            is_enrolled_fdos,
            is_enrolled_oct01,
            is_enrolled_oct15,
            latest_status,

            'All' as aligned_enrollment_type,

            0 as grouped_status_order,

            max(status_start_date) over (
                partition by
                    enrollment_academic_year,
                    finalsite_enrollment_id,
                    conversion_metric_denominator
            ) as grouped_status_start_date,

        from {{ ref("int_students__finalsite_student_roster") }}
        where
            conversion_metric_denominator is not null
            and status_start_date is not null
            and not qa_flag

        union all

        -- currently enrolled numerator
        select
            aligned_enrollment_academic_year,
            aligned_enrollment_academic_year_display,
            enrollment_academic_year,
            enrollment_academic_year_display,
            current_academic_year,
            next_academic_year,
            org,
            region,
            schoolid,
            school,
            finalsite_enrollment_id as finalsite_id,
            powerschool_student_number,
            first_name,
            last_name,
            grade_level,
            aligned_enrollment_academic_year_grade_level,
            self_contained,
            enrollment_academic_year_enrollment_type,
            detailed_status as grouped_status,
            sre_academic_year_start,
            sre_academic_year_end,
            is_enrolled_fdos,
            is_enrolled_oct01,
            is_enrolled_oct15,
            latest_status,

            'All' as aligned_enrollment_type,

            7 as grouped_status_order,

            status_start_date as grouped_status_start_date,

        from {{ ref("int_students__finalsite_student_roster") }}
        where
            detailed_status = 'Enrolled'
            and status_start_date is not null
            and not qa_flag

        union all

        /* numerator groupings for pending offer and currently accepted need distinct
           to bring only one row per student when they have multiple statuses per
           group */
        select distinct
            aligned_enrollment_academic_year,
            aligned_enrollment_academic_year_display,
            enrollment_academic_year,
            enrollment_academic_year_display,
            current_academic_year,
            next_academic_year,
            org,
            region,
            schoolid,
            school,
            finalsite_enrollment_id,
            powerschool_student_number,
            first_name,
            last_name,
            grade_level,
            aligned_enrollment_academic_year_grade_level,
            self_contained,
            enrollment_academic_year_enrollment_type,
            status_group_numerator as grouped_status,
            sre_academic_year_start,
            sre_academic_year_end,
            is_enrolled_fdos,
            is_enrolled_oct01,
            is_enrolled_oct15,
            latest_status,

            'All' as aligned_enrollment_type,

            if(status_group_numerator = 'Pending Offers', 4, 6) as grouped_status_order,

            max(status_start_date) over (
                partition by
                    enrollment_academic_year,
                    finalsite_enrollment_id,
                    status_group_numerator
            ) as grouped_status_start_date,

        from {{ ref("int_students__finalsite_student_roster") }}
        where
            status_group_numerator is not null
            and status_start_date is not null
            and not qa_flag

        union all

        /* numerator for conversion metrics groupings need distinct to bring only one
           row per student when they have multiple statuses per group */
        select distinct
            aligned_enrollment_academic_year,
            aligned_enrollment_academic_year_display,
            enrollment_academic_year,
            enrollment_academic_year_display,
            current_academic_year,
            next_academic_year,
            org,
            region,
            schoolid,
            school,
            finalsite_enrollment_id as finalsite_id,
            powerschool_student_number,
            first_name,
            last_name,
            grade_level,
            aligned_enrollment_academic_year_grade_level,
            self_contained,
            enrollment_academic_year_enrollment_type,
            conversion_metric_numerator as grouped_status,
            sre_academic_year_start,
            sre_academic_year_end,
            is_enrolled_fdos,
            is_enrolled_oct01,
            is_enrolled_oct15,
            latest_status,

            'All' as aligned_enrollment_type,

            0 as grouped_status_order,

            max(status_start_date) over (
                partition by
                    enrollment_academic_year,
                    finalsite_enrollment_id,
                    conversion_metric_numerator
            ) as grouped_status_start_date,

        from {{ ref("int_students__finalsite_student_roster") }}
        where
            conversion_metric_numerator is not null
            and status_start_date is not null
            and not qa_flag
    )

select
    aligned_enrollment_academic_year,
    aligned_enrollment_academic_year_display,
    enrollment_academic_year,
    enrollment_academic_year_display,
    current_academic_year,
    next_academic_year,
    org,
    region,
    schoolid,
    finalsite_id,
    powerschool_student_number,
    first_name,
    last_name,
    grade_level,
    aligned_enrollment_academic_year_grade_level,
    self_contained,
    enrollment_academic_year_enrollment_type,
    grouped_status,
    sre_academic_year_start,
    sre_academic_year_end,
    is_enrolled_fdos,
    is_enrolled_oct01,
    is_enrolled_oct15,
    latest_status,
    aligned_enrollment_type,
    grouped_status_order,
    grouped_status_start_date,

    if(grouped_status in ('Inquiries', 'Applications'), region, school) as school,

from stacked_data
