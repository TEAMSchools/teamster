with
    most_recent_students as (
        -- need distinct because of students with multiple apps
        select distinct finalsite_student_id,
        from {{ ref("int_finalsite__status_report") }}
        where extract_datetime = latest_extract_datetime
    ),

    active_finalsite_for_current_year as (
        select
            {{ var("current_academic_year") }} as enrollment_academic_year,
            c.finalsite_student_id,

        from {{ ref("int_finalsite__status_report") }} as c
        inner join
            most_recent_students as m on c.finalsite_student_id = m.finalsite_student_id
        where
            c.extract_year = 'Current_Year'
            and c.detailed_status = 'Enrolled'
            and c.powerschool_student_number is not null
            and c.latest_finalsite_student_id = 1
    ),

    active_finalsite_for_next_year as (
        /* cannot use latest_finalsite_student_id to get unique row counts because new
           students typically do not have a powerschool_student_number */
        select distinct
            {{ var("current_academic_year") }} + 1 as enrollment_academic_year,
            n.finalsite_student_id,

        from {{ ref("int_finalsite__status_report") }} as n
        inner join
            most_recent_students as m on n.finalsite_student_id = m.finalsite_student_id
        left join
            active_finalsite_for_current_year as c
            on n.finalsite_student_id = c.finalsite_student_id
        where
            n.extract_year = 'Next_Year'
            and n.detailed_status != 'Inactive Inquiry'
            and c.finalsite_student_id is null
    ),

    active_fs_roster as (
        select *,
        from active_finalsite_for_current_year

        union all

        select *,
        from active_finalsite_for_next_year
    ),

    enrollment_calc as (
        select
            f.enrollment_academic_year,
            f.finalsite_student_id,
            f.powerschool_student_number,
            f.enrollment_type_raw,

            e.enroll_status as enroll_yr_min_1_enroll_status,
            e.finalsite_enrollment_type as enroll_yr_min_1_enrollment_type,

            if(
                e.finalsite_enrollment_type in ('New', 'Returner'), 'Returner', 'New'
            ) as enrollment_year_enrollment_type,

        from {{ ref("int_finalsite__status_report") }} as f
        left join
            {{ ref("int_extracts__student_enrollments") }} as e
            on f.enrollment_academic_year - 1 = e.academic_year
            and f.powerschool_student_number = e.student_number
            and e.grade_level != 99
            and e.rn_year = 1
    )

select
    a.enrollment_academic_year,
    a.finalsite_student_id,

    e.powerschool_student_number,
    e.enrollment_type_raw,
    e.enroll_yr_min_1_enroll_status,
    e.enroll_yr_min_1_enrollment_type,
    e.enrollment_year_enrollment_type,

from active_fs_roster as a
inner join
    enrollment_calc as e
    on a.enrollment_academic_year = e.enrollment_academic_year
    and a.finalsite_student_id = e.finalsite_student_id
    --
    -- select
    -- r.enrollment_academic_year,
    -- r.finalsite_student_id,
    --
    -- e.powerschool_student_number,
    -- e.enrollment_type_raw,
    -- e.enroll_yr_min_1_enroll_status,
    -- e.enroll_yr_min_1_enrollment_type,
    -- e.enrollment_year_enrollment_type,
    --
    -- f._dbt_source_relation,
    -- f.enrollment_academic_year_display,
    -- f.sre_academic_year_start,
    -- f.sre_academic_year_end,
    -- f.extract_year,
    -- f.extract_datetime,
    -- f.latest_extract_datetime,
    -- f.org,
    -- f.region,
    -- f.latest_region,
    -- f.schoolid,
    -- f.latest_schoolid,
    -- f.school,
    -- f.latest_school,
    -- f.first_name,
    -- f.last_name,
    -- f.grade_level_name,
    -- f.grade_level,
    -- f.status,
    -- f.detailed_status,
    -- f.status_order,
    -- f.status_start_date,
    -- f.status_end_date,
    -- f.days_in_status,
    -- f.rn,
    --
    -- x.applicant_ops as student_applicant_ops,
    -- x.applicant_ops_alt as student_applicant_ops_alt,
    -- x.offered_ops as student_offered_ops,
    -- x.pending_offer_ops as student_pending_offer_ops,
    -- x.overall_conversion_ops as student_overall_conversion_ops,
    -- x.offers_to_accepted_den as student_offers_to_accepted_den,
    -- x.offers_to_accepted_num as student_offers_to_accepted_num,
    -- x.accepted_to_enrolled_den as student_accepted_to_enrolled_den,
    -- x.accepted_to_enrolled_num as student_accepted_to_enrolled_num,
    -- x.offers_to_enrolled_den as student_offers_to_enrolled_den,
    -- x.offers_to_enrolled_num as student_offers_to_enrolled_num,
    -- x.waitlisted as student_waitlisted,
    --
    -- from active_fs_roster as r
    -- left join
    -- final_enrollment_calc as e
    -- on r.enrollment_academic_year = e.enrollment_academic_year
    -- and r.finalsite_student_id = e.finalsite_student_id
    -- left join
    -- {{ ref("int_finalsite__status_report") }} as f
    -- on r.enrollment_academic_year = f.enrollment_academic_year
    -- and r.finalsite_student_id = f.finalsite_student_id
    -- inner join
    -- {{ ref("stg_google_sheets__finalsite__status_crosswalk") }} as x
    -- on f.enrollment_academic_year = x.enrollment_academic_year
    -- and f.enrollment_year_enrollment_type = x.enrollment_type
    -- and f.detailed_status = x.detailed_status
