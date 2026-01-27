with
    weekly_spine as (
        -- need only one row per expected sre academic year
        select distinct
            enrollment_academic_year_display,
            sre_academic_year as academic_year,
            sre_year_start,
            sre_year_end,

            week_start as week_start_monday,

            'KTAF' as org,

            date_add(week_start, interval 6 day) as week_end_sunday,

        from {{ ref("int_finalsite__status_report") }}
        cross join
            unnest(
                generate_date_array(
                    -- trunk-ignore(sqlfluff/LT01)
                    date_trunc(sre_year_start, week(monday)),
                    -- trunk-ignore(sqlfluff/LT01)
                    date_trunc(sre_year_end, week(monday)),
                    interval 7 day
                )
            ) as week_start
        where rn = 1
    ),

    enrollment_type_calc as (
        select
            _dbt_source_relation,
            academic_year,
            student_number,
            first_name,
            last_name,

            case
                when
                    coalesce(
                        lag(
                            sum(if(date_diff(exitdate, entrydate, day) >= 7, 1, 0))
                        ) over (partition by student_number order by academic_year),
                        0
                    )
                    = 0
                then 'New'
                when
                    coalesce(
                        lag(
                            sum(if(date_diff(exitdate, entrydate, day) >= 7, 1, 0))
                        ) over (partition by student_number order by academic_year),
                        0
                    )
                    = 1
                    and academic_year - coalesce(
                        lag(academic_year) over (
                            partition by student_number order by academic_year
                        ),
                        0
                    )
                    > 1
                then 'New'
                else 'Returner'
            end as enrollment_type,

        from {{ ref("base_powerschool__student_enrollments") }}
        where grade_level != 99
        group by
            _dbt_source_relation, academic_year, student_number, first_name, last_name
    ),

    mod_enrollment_type as (
        select
            f._dbt_source_relation,
            f.sre_academic_year as academic_year,
            f.enrollment_academic_year_display,
            f.enrollment_year,
            f.region,
            f.schoolid,
            f.school,
            f.finalsite_student_id,
            f.powerschool_student_number,
            f.last_name,
            f.first_name,
            f.grade_level,
            f.detailed_status,
            f.status_start_date,
            f.status_end_date,
            f.days_in_status,
            f.sre_year_start,
            f.sre_year_end,
            f.rn,

            coalesce(e.enrollment_type, 'New') as enrollment_type,

        from {{ ref("int_finalsite__status_report") }} as f
        left join
            enrollment_type_calc as e
            on f.powerschool_student_number = e.student_number
            and {{ union_dataset_join_clause(left_alias="f", right_alias="e") }}
    ),

    finalsite_data as (
        select
            f._dbt_source_relation,
            f.academic_year,
            f.enrollment_academic_year_display,
            f.enrollment_year,
            f.region,
            f.schoolid,
            f.school,
            f.finalsite_student_id,
            f.powerschool_student_number,
            f.last_name,
            f.first_name,
            f.grade_level,
            f.detailed_status,
            f.status_start_date,
            f.status_end_date,
            f.days_in_status,
            f.sre_year_start,
            f.sre_year_end,
            f.rn,
            f.enrollment_type,

            x.applicant_ops as student_applicant_ops,
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

        from mod_enrollment_type as f
        inner join
            {{ ref("stg_google_sheets__finalsite__status_crosswalk") }} as x
            on f.academic_year = x.academic_year
            and f.enrollment_type = x.enrollment_type
            and f.detailed_status = x.detailed_status
    ),

    student_scaffold as (
        select
            m._dbt_source_relation,
            m.academic_year,
            m.schoolid,
            m.school,
            m.finalsite_student_id,
            m.grade_level,
            m.enrollment_type,

            w.week_start_monday,
            w.week_end_sunday,

            c.detailed_status,

        from mod_enrollment_type as m
        inner join weekly_spine as w on m.academic_year = w.academic_year
        cross join {{ ref("stg_google_sheets__finalsite__status_crosswalk") }} as c
        where
            m.academic_year = c.academic_year
            and m.enrollment_type = c.enrollment_type
            and m.rn = 1
    ),

    scaffold as (
        -- distinct: get a list of schools open tied to an academic year
        select distinct
            e._dbt_source_relation,
            e.academic_year,
            'KTAF' as org,
            e.region,
            e.schoolid,
            e.school,
            e.grade_level,

            w.enrollment_academic_year_display,
            w.sre_year_start,
            w.sre_year_end,
            w.week_start_monday,
            w.week_end_sunday,

            c.enrollment_type,
            c.overall_status,
            c.funnel_status,
            c.status_category,
            c.offered_status,
            c.offered_status_detailed,
            c.detailed_status,
            c.detailed_status_ranking,
            c.detailed_status_branched_ranking,
            c.powerschool_enroll_status,
            c.valid_detailed_status,

            c.applicant_ops,
            c.offered_ops,
            c.pending_offer_ops,
            c.overall_conversion_ops,
            c.offers_to_accepted_den,
            c.offers_to_accepted_num,
            c.accepted_to_enrolled_den,
            c.accepted_to_enrolled_num,
            c.offers_to_enrolled_den,
            c.offers_to_enrolled_num,
            c.waitlisted,

        from {{ ref("int_extracts__student_enrollments") }} as e
        inner join weekly_spine as w on e.academic_year = w.academic_year
        cross join {{ ref("stg_google_sheets__finalsite__status_crosswalk") }} as c
        where
            e.grade_level != 99 and e.academic_year = c.academic_year and e.rn_year = 1

        union all

        /* distinct: get a list of grade levels but schoolid by region tied to an
           academic year */
        select distinct
            e._dbt_source_relation,
            e.academic_year,
            'KTAF' as org,
            e.region,
            0 as schoolid,
            'No School Assigned' as school,
            e.grade_level,

            w.enrollment_academic_year_display,
            w.sre_year_start,
            w.sre_year_end,
            w.week_start_monday,
            w.week_end_sunday,

            c.enrollment_type,
            c.overall_status,
            c.funnel_status,
            c.status_category,
            c.offered_status,
            c.offered_status_detailed,
            c.detailed_status,
            c.detailed_status_ranking,
            c.detailed_status_branched_ranking,
            c.powerschool_enroll_status,
            c.valid_detailed_status,

            c.applicant_ops,
            c.offered_ops,
            c.pending_offer_ops,
            c.overall_conversion_ops,
            c.offers_to_accepted_den,
            c.offers_to_accepted_num,
            c.accepted_to_enrolled_den,
            c.accepted_to_enrolled_num,
            c.offers_to_enrolled_den,
            c.offers_to_enrolled_num,
            c.waitlisted,

        from {{ ref("int_extracts__student_enrollments") }} as e
        inner join weekly_spine as w on e.academic_year = w.academic_year
        cross join {{ ref("stg_google_sheets__finalsite__status_crosswalk") }} as c
        where
            e.grade_level != 99 and e.academic_year = c.academic_year and e.rn_year = 1
    )

select
    s._dbt_source_relation,
    s.academic_year,
    s.enrollment_academic_year_display,
    s.org,
    s.region,
    s.schoolid,
    s.school,
    s.grade_level,
    s.sre_year_start,
    s.sre_year_end,
    s.week_start_monday,
    s.week_end_sunday,
    s.enrollment_type,
    s.overall_status,
    s.funnel_status,
    s.status_category,
    s.offered_status,
    s.offered_status_detailed,
    s.detailed_status,
    s.detailed_status_ranking,
    s.detailed_status_branched_ranking,
    s.powerschool_enroll_status,
    s.valid_detailed_status,
    s.applicant_ops,
    s.offered_ops,
    s.pending_offer_ops,
    s.overall_conversion_ops,
    s.offers_to_accepted_den,
    s.offers_to_accepted_num,
    s.accepted_to_enrolled_den,
    s.accepted_to_enrolled_num,
    s.offers_to_enrolled_den,
    s.offers_to_enrolled_num,
    s.waitlisted,

    stu.finalsite_student_id,

    f.finalsite_student_id as student_finalsite_student_id,
    f.enrollment_year as student_enrollment_year,
    f.region as student_region,
    f.schoolid as student_schoolid,
    f.school as student_school,
    f.powerschool_student_number as student_number,
    f.last_name as student_last_name,
    f.first_name as student_first_name,
    f.grade_level as student_grade_level,
    f.detailed_status as student_detailed_status,
    f.status_start_date,
    f.status_end_date,
    f.days_in_status,
    f.enrollment_type as student_enrollment_type,
    f.student_applicant_ops,
    f.student_offered_ops,
    f.student_pending_offer_ops,
    f.student_overall_conversion_ops,
    f.student_offers_to_accepted_den,
    f.student_offers_to_accepted_num,
    f.student_accepted_to_enrolled_den,
    f.student_accepted_to_enrolled_num,
    f.student_offers_to_enrolled_den,
    f.student_offers_to_enrolled_num,
    f.student_waitlisted,

from scaffold as s
inner join
    student_scaffold as stu
    on s.academic_year = stu.academic_year
    and s.schoolid = stu.schoolid
    and s.grade_level = stu.grade_level
    and s.enrollment_type = stu.enrollment_type
    and s.detailed_status = stu.detailed_status
    and s.week_start_monday = stu.week_start_monday
    and {{ union_dataset_join_clause(left_alias="s", right_alias="stu") }}
left join
    finalsite_data as f
    on stu.academic_year = f.academic_year
    and stu.schoolid = f.schoolid
    and stu.grade_level = f.grade_level
    and stu.detailed_status = f.detailed_status
    and stu.enrollment_type = f.enrollment_type
    and {{ union_dataset_join_clause(left_alias="stu", right_alias="f") }}
    and stu.finalsite_student_id = f.finalsite_student_id
    and f.status_start_date between stu.week_start_monday and stu.week_end_sunday
