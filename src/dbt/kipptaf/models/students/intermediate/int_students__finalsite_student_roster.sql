with
    most_recent_students as (
        -- need distinct because of students with multiple apps
        select distinct
            coalesce(
                latest_finalsite_student_id, finalsite_student_id
            ) as finalsite_student_id,

        from {{ ref("int_finalsite__status_report") }}
        where
            extract_datetime = latest_extract_datetime
            and detailed_status not in ('Inactive Inquiry', 'Deferred')
    ),

    active_finalsite_for_current_year as (
        select
            {{ var("current_academic_year") }} as enrollment_academic_year,
            c.latest_finalsite_student_id,

            coalesce(e.next_year_enrollment_type, 'New') as next_year_enrollment_type,

        from {{ ref("int_finalsite__status_report") }} as c
        inner join
            most_recent_students as m
            on c.latest_finalsite_student_id = m.finalsite_student_id
        left join
            {{ ref("int_extracts__student_enrollments") }} as e
            on c.latest_finalsite_student_id = e.finalsite_student_id
            and e.academic_year = {{ var("current_academic_year") }}
            and e.grade_level != 99
            and e.rn_year = 1
        where
            c.extract_year = 'Current_Year'
            and c.detailed_status = 'Enrolled'
            and c.powerschool_student_number is not null
            and c.latest_finalsite_student_id_rn = 1
    ),

    active_finalsite_for_next_year as (
        /* cannot use latest_finalsite_student_id to get unique row counts because new
           students typically do not have a powerschool_student_number */
        select distinct
            {{ var("current_academic_year") + 1 }} + 1 as enrollment_academic_year,
            n.finalsite_student_id as latest_finalsite_student_id,

            coalesce(e.next_year_enrollment_type, 'New') as next_year_enrollment_type,

        from {{ ref("int_finalsite__status_report") }} as n
        inner join
            most_recent_students as m on n.finalsite_student_id = m.finalsite_student_id
        left join
            active_finalsite_for_current_year as c
            on n.finalsite_student_id = c.latest_finalsite_student_id
        left join
            {{ ref("int_extracts__student_enrollments") }} as e
            on n.latest_finalsite_student_id = e.finalsite_student_id
            and e.academic_year = {{ var("current_academic_year") }}
            and e.grade_level != 99
            and e.rn_year = 1
        where n.extract_year = 'Next_Year' and c.latest_finalsite_student_id is null
    ),

    active_fs_roster as (
        select
            enrollment_academic_year,
            latest_finalsite_student_id,
            next_year_enrollment_type,

        from active_finalsite_for_current_year

        union all

        select
            enrollment_academic_year,
            latest_finalsite_student_id,
            next_year_enrollment_type,

        from active_finalsite_for_next_year
    ),

    aligned_year_calcs as (
        select
            a.enrollment_academic_year,
            a.latest_finalsite_student_id as finalsite_student_id,
            a.next_year_enrollment_type,

            f._dbt_source_relation,
            f.enrollment_year,
            f.enrollment_academic_year_display,
            f.sre_academic_year_start,
            f.sre_academic_year_end,
            f.org,
            f.region,
            f.latest_region,
            f.schoolid,
            f.latest_schoolid,
            f.school,
            f.latest_school,
            f.powerschool_student_number,
            f.first_name,
            f.last_name,
            f.grade_level,
            f.latest_grade_level,
            f.detailed_status,
            f.status_order,
            f.status_start_date,
            f.status_end_date,
            f.days_in_status,
            f.rn,
            f.enrollment_type_raw,
            f.latest_status,

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

            {{ var("current_academic_year") + 1 }} as aligned_enrollment_academic_year,

        from active_fs_roster as a
        inner join
            {{ ref("int_finalsite__status_report") }} as f
            on a.enrollment_academic_year = f.enrollment_academic_year
            and a.latest_finalsite_student_id = f.finalsite_student_id
        inner join
            {{ ref("stg_google_sheets__finalsite__status_crosswalk") }} as x
            on a.enrollment_academic_year = x.enrollment_academic_year
            and a.next_year_enrollment_type = x.enrollment_type
            and f.detailed_status = x.detailed_status
        where a.enrollment_academic_year <= {{ var("current_academic_year") + 1 }}
    )

select
    *,

    cast(aligned_enrollment_academic_year as string)
    || '-'
    || right(
        cast(aligned_enrollment_academic_year + 1 as string), 2
    ) as aligned_enrollment_academic_year_display,

    date(
        aligned_enrollment_academic_year - 1, 10, 16
    ) as sre_aligned_academic_year_start,

    date(aligned_enrollment_academic_year, 6, 30) as sre_aligned_academic_year_end,

from aligned_year_calcs
