with
    finalsite_report as (
        select
            f.* except (school),

            x.powerschool_school_id as schoolid,
            x.abbreviation as school,

            row_number() over (
                partition by f.academic_year, f.sre_year_start, f.sre_year_end
                order by f.academic_year
            ) as rn_sre_year,

        from {{ ref("stg_google_sheets__finalsite__sample_data") }} as f
        left join
            {{ ref("stg_google_sheets__people__location_crosswalk") }} as x
            on f.school = x.name
    ),

    latest_school_id_gl as (
        select
            _dbt_source_relation,
            academic_year,
            finalsite_student_id,
            schoolid,
            school,
            grade_level,
            grade_level_string,

            row_number() over (
                partition by academic_year, finalsite_student_id
                order by status_start_date desc
            ) as rn,

        from finalsite_report
        qualify rn = 1
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
            f.finalsite_student_id,
            f.academic_year,
            f.academic_year_display,
            f.enrollment_year,
            f.region,
            f.powerschool_student_number,
            f.last_name,
            f.first_name,
            f.detailed_status,
            f.status_start_date,
            f.status_end_date,
            f.days_in_status,

            coalesce(e.enrollment_type, 'New') as enrollment_type,

            coalesce(f.schoolid, r.schoolid) as schoolid,
            coalesce(f.school, r.school) as school,
            coalesce(f.grade_level, r.grade_level) as grade_level,
            coalesce(f.grade_level_string, r.grade_level_string) as grade_level_string,

        from finalsite_report as f
        left join
            enrollment_type_calc as e
            on f.powerschool_student_number = e.student_number
            and {{ union_dataset_join_clause(left_alias="f", right_alias="e") }}
        left join
            latest_school_id_gl as r
            on f.academic_year = r.academic_year
            and f.finalsite_student_id = r.finalsite_student_id
            and {{ union_dataset_join_clause(left_alias="f", right_alias="r") }}
    ),

    scaffold as (
        -- distinct: get a list of schools open tied to an academic year
        select distinct
            e._dbt_source_relation,
            e.academic_year,
            e.region,
            e.schoolid,
            e.school,
            e.grade_level,

            f.sre_year_start,
            f.sre_year_end,

            c.overall_status,
            c.funnel_status,
            c.status_category,
            c.offered_status,
            c.offered_status_detailed,
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

            week_start as week_start_monday,
            date_add(week_start, interval 6 day) as week_end_sunday,

            cast(e.academic_year as string)
            || '-'
            || right(cast(e.academic_year + 1 as string), 2) as academic_year_display,

        from {{ ref("int_extracts__student_enrollments") }} as e
        inner join
            finalsite_report as f
            on e.academic_year = f.academic_year
            and f.rn_sre_year = 1
        cross join
            unnest(
                generate_date_array(
                    -- trunk-ignore(sqlfluff/LT01)
                    date_trunc(f.sre_year_start, week(monday)),
                    -- trunk-ignore(sqlfluff/LT01)
                    date_trunc(f.sre_year_end, week(monday)),
                    interval 7 day
                )
            ) as week_start
        cross join {{ ref("stg_google_sheets__finalsite__status_crosswalk") }} as c
        where e.grade_level != 99 and c.academic_year = c.academic_year
    )

select
    s._dbt_source_relation,
    s.academic_year,
    s.academic_year_display,
    s.region,
    s.schoolid,
    s.school,
    s.grade_level,
    s.grade_level_string,
    s.sre_year_start,
    s.sre_year_end,
    s.week_start_monday,
    s.week_end_sunday,
    s.overall_status,
    s.funnel_status,
    s.status_category,
    s.offered_status,
    s.offered_status_detailed,
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

    coalesce(m1.finalsite_student_id, m2.finalsite_student_id) as finalsite_student_id,
    coalesce(m1.enrollment_year, m2.enrollment_year) as student_enrollment_year,
    coalesce(m1.region, m2.region) as student_region,
    coalesce(m1.schoolid, m2.schoolid) as student_schoolid,
    coalesce(m1.school, m2.school) as student_school,
    coalesce(
        m1.powerschool_student_number, m2.powerschool_student_number
    ) as powerschool_student_number,
    coalesce(m1.last_name, m2.last_name) as student_last_name,
    coalesce(m1.first_name, m2.first_name) as student_first_name,
    coalesce(m1.grade_level, m2.grade_level) as student_grade_level,
    coalesce(
        m1.grade_level_string, m2.grade_level_string
    ) as student_grade_level_string,
    coalesce(m1.detailed_status, m2.detailed_status) as student_detailed_status,
    coalesce(m1.status_start_date, m2.status_start_date) as status_start_date,
    coalesce(m1.status_end_date, m2.status_end_date) as status_end_date,
    coalesce(m1.days_in_status, m2.days_in_status) as days_in_status,
    coalesce(m1.enrollment_type, m2.enrollment_type) as student_enrollment_type,

from scaffold as s
left join
    mod_enrollment_type as m1
    on s.academic_year = m1.academic_year
    and s.schoolid = m1.schoolid
    and s.grade_level = m1.grade_level
    and s.detailed_status = m1.detailed_status
    and s.enrollment_type = m1.enrollment_type
    and {{ union_dataset_join_clause(left_alias="s", right_alias="m1") }}
    and m1.status_start_date between s.week_start_monday and s.week_end_sunday
    and m1.schoolid is not null
left join
    mod_enrollment_type as m2
    on s.academic_year = m2.academic_year
    and s.schoolid = m2.schoolid
    and s.grade_level = m2.grade_level
    and s.detailed_status = m2.detailed_status
    and s.enrollment_type = m2.enrollment_type
    and {{ union_dataset_join_clause(left_alias="s", right_alias="m2") }}
    and m2.status_start_date between s.week_start_monday and s.week_end_sunday
    and m2.schoolid is null
