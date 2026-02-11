with
    active_finalsite_by_extract_year as (
        select *,
        from {{ ref("int_finalsite__status_report") }}
        where extract_date_time = latest_extract_datetime
    )

    final_enrollment_calc as (
        select
            f._dbt_source_relation,
            f.enrollment_year,
            f.enrollment_academic_year,
            f.enrollment_academic_year_display,
            f.sre_academic_year_start,
            f.sre_academic_year_end,
            f.extract_year,
            f.extract_datetime,
            f.latest_extract_datetime,
            f.org,
            f.region,
            f.latest_region,
            f.schoolid,
            f.latest_schoolid,
            f.school,
            f.latest_school,
            f.finalsite_student_id,
            f.first_name,
            f.last_name,
            f.grade_level_name,
            f.grade_level,
            f.status,
            f.detailed_status,
            f.status_order,
            f.status_start_date,
            f.status_end_date,
            f.days_in_status,
            f.rn,
            f.enrollment_type_raw,

            e.enroll_status as enroll_yr_min_1_enroll_status,
            e.finalsite_enrollment_type as enroll_yr_min_1_enrollment_type,

            case
                e.finalsite_enrollment_type
                when 'New'
                then 'Returner'
                when 'Returner'
                then 'Returner'
                else 'New'
            end as enrollment_year_enrollment_type,

        from {{ ref("int_finalsite__status_report") }} as f
        left join
            {{ ref("int_extracts__student_enrollments") }} as e
            on f.enrollment_academic_year - 1 = e.academic_year
            and f.powerschool_student_number = e.student_number
            and e.rn_year = 1
    )

select
    f.*,

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

from final_enrollment_calc as f
inner join
    {{ ref("stg_google_sheets__finalsite__status_crosswalk") }} as x
    on f.enrollment_academic_year = x.enrollment_academic_year
    and f.enrollment_year_enrollment_type = x.enrollment_type
    and f.detailed_status = x.detailed_status
