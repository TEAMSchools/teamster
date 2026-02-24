with
    enroll_calc as (
        select
            r.aligned_enrollment_academic_year,
            r.aligned_enrollment_academic_year_display,
            r.enrollment_academic_year,
            r.enrollment_academic_year_display,
            r.org,
            r.region,
            r.latest_schoolid,
            r.latest_school,
            r.finalsite_student_id,
            r.powerschool_student_number,
            r.first_name,
            r.last_name,
            r.grade_level,
            r.detailed_status,

            coalesce(
                e.next_year_enrollment_type, 'New'
            ) as aligned_enrollment_academic_year_enrollment_type,

            if(
                r.enrollment_academic_year = 2025, r.grade_level + 1, r.grade_level
            ) as aligned_enrollment_year_grade_level,

        from {{ ref("int_finalsite__status_report") }} as r
        left join
            {{ ref("int_extracts__student_enrollments") }} as e
            on r.finalsite_student_id = e.finalsite_student_id
            and e.academic_year = 2025
            and e.grade_level != 99
            and e.rn_year = 1
    ),

    base_data as (
        select
            r.*,

            x.applicant_ops as student_applicant_ops,
            x.applicant_ops_alt as student_applicant_ops_alt,
            x.offered_ops as student_offered_ops,
            x.pending_offer_ops as student_pending_offer_ops,
            x.overall_conversion_ops as student_overall_conversion_ops,
            x.offers_to_accepted_den as student_offers_to_accepted_den,
            x.offers_to_accepted_num as student_offers_to_accepted_num,
            x.accepted_to_enrolled_den as student_accepted_to_enrolled_den,
            x.accepted_to_enrolled_num as student_accepted_to_enrolled_num,
            x.offers_to_enrolled_den as student_offers_to_enrolled_den,
            x.offers_to_enrolled_num as student_offers_to_enrolled_num,
            x.waitlisted as student_waitlisted,

        from enroll_calc as r
        inner join
            {{ ref("stg_google_sheets__finalsite__status_crosswalk") }} as x
            on r.enrollment_academic_year = x.enrollment_academic_year
            and r.aligned_enrollment_academic_year_enrollment_type = x.enrollment_type
            and r.detailed_status = x.detailed_status
    ),

    calcs as (
        select
            aligned_enrollment_academic_year,
            aligned_enrollment_academic_year_display,
            enrollment_academic_year,
            enrollment_academic_year_display,
            org,
            region,
            latest_schoolid,
            latest_school,
            finalsite_student_id,
            powerschool_student_number,
            first_name,
            last_name,
            grade_level,
            aligned_enrollment_year_grade_level,
            aligned_enrollment_academic_year_enrollment_type,

            'Offers to Accepted' as metric,

            if(
                (
                    max(student_offers_to_accepted_num) over (
                        partition by finalsite_student_id
                    ) / max(student_offers_to_accepted_den) over (
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
            region,
            latest_schoolid,
            latest_school,
            finalsite_student_id,
            powerschool_student_number,
            first_name,
            last_name,
            grade_level,
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
            region,
            latest_schoolid,
            latest_school,
            finalsite_student_id,
            powerschool_student_number,
            first_name,
            last_name,
            grade_level,
            aligned_enrollment_year_grade_level,
            aligned_enrollment_academic_year_enrollment_type,

            'Offers to Enrolled' as metric,

            if(
                (
                    max(student_offers_to_enrolled_num) over (
                        partition by finalsite_student_id
                    ) / max(student_offers_to_enrolled_den) over (
                        partition by finalsite_student_id
                    )
                )
                = 1,
                finalsite_student_id,
                null
            ) as met_metric,

        from base_data
        where enrollment_academic_year = 2026 and student_offers_to_enrolled_den != 0
    ),

    scaffold as (
        select
            s.academic_year,
            s.org,
            s.region,
            s.schoolid,
            s.school,
            s.grade_level,

            metric,

        from {{ ref("stg_google_sheets__finalsite__school_scaffold") }} as s
        cross join
            unnest(
                ['Offers to Accepted', 'Offers to Enrolled', 'Accepted to Enrolled']
            ) as metric
    )

select
    s.academic_year,
    s.org,
    s.region,
    s.schoolid,
    s.school,
    s.grade_level,
    s.metric,

    c.aligned_enrollment_academic_year,
    c.aligned_enrollment_academic_year_display,
    c.enrollment_academic_year,
    c.enrollment_academic_year_display,
    c.finalsite_student_id,
    c.powerschool_student_number,
    c.first_name,
    c.last_name,
    c.met_metric,

    g.goal_type,
    g.goal_name,
    g.goal_value,

from scaffold as s
left join
    calcs as c
    on s.academic_year = c.aligned_enrollment_academic_year
    and s.schoolid = c.latest_schoolid
    and s.grade_level = c.aligned_enrollment_year_grade_level
    and s.metric = c.metric
left join
    {{ ref("stg_google_sheets__finalsite__goals") }} as g
    on c.enrollment_academic_year = g.enrollment_academic_year
    and c.metric = g.goal_name
    and c.latest_schoolid = g.schoolid
    and c.aligned_enrollment_year_grade_level = g.grade_level
