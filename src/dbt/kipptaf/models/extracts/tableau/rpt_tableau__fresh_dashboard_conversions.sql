with
    base_data as (
        select
            aligned_enrollment_academic_year,
            aligned_enrollment_academic_year_display,
            enrollment_academic_year,
            enrollment_academic_year_display,
            org,
            latest_region,
            latest_schoolid,
            latest_school,
            finalsite_student_id,
            powerschool_student_number,
            first_name,
            last_name,
            latest_grade_level,
            next_year_enrollment_type
            as aligned_enrollment_academic_year_enrollment_type,
            detailed_status,
            days_in_status,

            student_applicant_ops_alt,
            student_offered_ops,
            student_pending_offer_ops,
            student_overall_conversion_ops,
            student_offers_to_accepted_num,
            student_offers_to_accepted_den,
            student_accepted_to_enrolled_num,
            student_accepted_to_enrolled_den,
            student_offers_to_enrolled_num,
            student_offers_to_enrolled_den,
            student_waitlisted,

            if(
                enrollment_academic_year = 2025,
                latest_grade_level + 1,
                latest_grade_level
            ) as aligned_enrollment_year_grade_level,

        from `kipptaf_students.int_students__finalsite_student_roster`
    )

select
    aligned_enrollment_academic_year,
    aligned_enrollment_academic_year_display,
    enrollment_academic_year,
    enrollment_academic_year_display,
    org,
    latest_region,
    latest_schoolid,
    latest_school,
    finalsite_student_id,
    powerschool_student_number,
    first_name,
    last_name,
    latest_grade_level,
    aligned_enrollment_year_grade_level,
    aligned_enrollment_academic_year_enrollment_type,

    'Offers to Accepted' as metric,

    if(
        (
            max(student_offers_to_accepted_num) over (partition by finalsite_student_id)
            / max(student_offers_to_accepted_den) over (
                partition by finalsite_student_id
            )
        )
        = 1,
        finalsite_student_id,
        null
    ) as met_metric,

from base_data
where enrollment_academic_year = 2026 and student_offers_to_accepted_den != 0

union all

select
    aligned_enrollment_academic_year,
    aligned_enrollment_academic_year_display,
    enrollment_academic_year,
    enrollment_academic_year_display,
    org,
    latest_region,
    latest_schoolid,
    latest_school,
    finalsite_student_id,
    powerschool_student_number,
    first_name,
    last_name,
    latest_grade_level,
    aligned_enrollment_year_grade_level,
    aligned_enrollment_academic_year_enrollment_type,

    'Accepted to Enrolled' as metric,

    if(
        (
            max(student_accepted_to_enrolled_num) over (
                partition by finalsite_student_id
            ) / max(student_accepted_to_enrolled_den) over (
                partition by finalsite_student_id
            )
        )
        = 1,
        finalsite_student_id,
        null
    ) as met_metric,

from base_data
where enrollment_academic_year = 2026 and student_accepted_to_enrolled_den != 0

union all

select
    aligned_enrollment_academic_year,
    aligned_enrollment_academic_year_display,
    enrollment_academic_year,
    enrollment_academic_year_display,
    org,
    latest_region,
    latest_schoolid,
    latest_school,
    finalsite_student_id,
    powerschool_student_number,
    first_name,
    last_name,
    latest_grade_level,
    aligned_enrollment_year_grade_level,
    aligned_enrollment_academic_year_enrollment_type,

    'Offers to Enrolled' as metric,

    if(
        (
            max(student_offers_to_enrolled_num) over (partition by finalsite_student_id)
            / max(student_offers_to_enrolled_den) over (
                partition by finalsite_student_id
            )
        )
        = 1,
        finalsite_student_id,
        null
    ) as met_metric,

from base_data
where enrollment_academic_year = 2026 and student_offers_to_enrolled_den != 0
