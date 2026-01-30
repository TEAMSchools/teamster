with
    daily_spine as (
        -- need only one row per expected sre academic year
        select distinct sre_academic_year, calendar_day,

        from {{ ref("int_finalsite__status_report") }}
        cross join
            unnest(
                generate_date_array(
                    -- trunk-ignore(sqlfluff/LT01)
                    date_trunc(sre_academic_year_start, week(monday)),
                    -- trunk-ignore(sqlfluff/LT01)
                    date_trunc(sre_academic_year_end, week(monday)),
                    interval 1 day
                )
            ) as calendar_day
        where rn = 1
    ),

    scaffold as (
        -- distinct: get a list of schools open tied to an academic year
        select distinct
            e._dbt_source_relation,
            e.academic_year,
            e.academic_year_display,
            e.district as org,
            e.region,
            e.schoolid,
            e.school,
            e.grade_level,

            d.calendar_day,

            metric,

        from {{ ref("int_extracts__student_enrollments") }} as e
        inner join daily_spine as d on e.academic_year = d.sre_academic_year
        cross join
            unnest(
                [
                    'Applications',
                    'Offers',
                    'Pending Offers',
                    'Pending Offer <= 4',
                    'Pending Offer >= 5 & <=10',
                    'Pending Offer > 10',
                    'Conversion'
                ]
            ) as metric
        where e.grade_level != 99 and e.rn_year = 1

        union all

        /* distinct: get a list of grade levels but schoolid by region tied to an
           academic year */
        select distinct
            e._dbt_source_relation,
            e.academic_year,
            e.academic_year_display,
            e.district as org,
            e.region,
            0 as schoolid,
            'No School Assigned' as school,
            e.grade_level,

            d.calendar_day,

            metric,

        from {{ ref("int_extracts__student_enrollments") }} as e
        inner join daily_spine as d on e.academic_year = d.sre_academic_year
        cross join
            unnest(
                [
                    'Applications',
                    'Offers',
                    'Pending Offers',
                    'Pending Offer <= 4',
                    'Pending Offer >= 5 & <=10',
                    'Pending Offer > 10',
                    'Conversion'
                ]
            ) as metric
        where e.grade_level != 99 and e.rn_year = 1
    ),

    summary as (
        select
            r._dbt_source_relation,
            r.academic_year,
            r.sre_academic_year,
            r.enrollment_academic_year,
            r.enrollment_academic_year_display,
            r.org,
            r.region,
            r.school,
            r.grade_level,

            r.student_finalsite_student_id,
            r.student_grade_level,
            r.student_detailed_status,
            r.status_start_date,
            r.student_applicant_ops,
            r.student_offered_ops,
            r.student_pending_offer_ops,
            r.student_overall_conversion_ops,
            r.student_offers_to_accepted_num,
            r.student_offers_to_accepted_den,
            r.student_accepted_to_enrolled_num,
            r.student_accepted_to_enrolled_den,
            r.student_offers_to_enrolled_num,
            r.student_offers_to_enrolled_den,

            d.calendar_day,

        from {{ ref("int_students__finalsite_student_roster") }} as r
        inner join
            daily_spine as d
            on d.calendar_day between r.status_start_date and r.status_end_date
    ),

    max_custom_status as (
        select
            _dbt_source_relation,
            academic_year,
            sre_academic_year,
            enrollment_academic_year,
            enrollment_academic_year_display,
            org,
            region,
            school,
            grade_level,
            student_finalsite_student_id,
            student_grade_level,
            calendar_day,

            max(student_applicant_ops) over (
                partition by sre_academic_year, student_finalsite_student_id
            ) as application_cumulative,

            max(student_offered_ops) over (
                partition by sre_academic_year, student_finalsite_student_id
            ) as offers_cumulative,

            max(student_overall_conversion_ops) over (
                partition by sre_academic_year, student_finalsite_student_id
            ) as conversion_cumulative,

            max(student_pending_offer_ops) over (
                partition by
                    sre_academic_year, student_finalsite_student_id, calendar_day
            ) as pending_offer_daily,

        from summary
    ),

    pending_offer_calcs as (
        select
            _dbt_source_relation,
            academic_year,
            sre_academic_year,
            enrollment_academic_year,
            enrollment_academic_year_display,
            org,
            region,
            school,
            grade_level,
            student_finalsite_student_id,
            student_grade_level,
            calendar_day,
            application_cumulative,
            offers_cumulative,
            conversion_cumulative,
            pending_offer_daily,

            case
                when
                    pending_offer_daily = 1
                    and sum(pending_offer_daily) over (
                        partition by sre_academic_year, student_finalsite_student_id
                        order by calendar_day asc
                    )
                    <= 4
                then 'Pending Offer <= 4'
                when
                    pending_offer_daily = 1
                    and sum(pending_offer_daily) over (
                        partition by sre_academic_year, student_finalsite_student_id
                        order by calendar_day asc
                    )
                    between 5 and 10
                then 'Pending Offer >= 5 & <=10'
                when
                    pending_offer_daily = 1
                    and sum(pending_offer_daily) over (
                        partition by sre_academic_year, student_finalsite_student_id
                        order by calendar_day asc
                    )
                    > 10
                then 'Pending Offer > 10'
            end as pending_offer_timing_status,

        from max_custom_status
    ),

    final as (
        select
            s._dbt_source_relation,
            s.academic_year,
            s.academic_year_display,
            s.enrollment_academic_year,
            s.enrollment_academic_year_display,
            s.org,
            s.region,
            s.school,
            s.grade_level,
            s.calendar_day,
            s.metric,

            if(
                p.application_cumulative = 1, p.student_finalsite_student_id, null
            ) as student_finalsite_student_id,

        from scaffold as s
        left join
            pending_offer_calcs as p
            on s.academic_year = p.academic_year
            and s.region = p.region
            and s.school = p.school
            and s.grade_level = p.grade_level
            and s.calendar_day = p.calendar_day
        where s.metric = 'Applications'

        union all

        select
            s._dbt_source_relation,
            s.academic_year_display,
            s.enrollment_academic_year,
            s.enrollment_academic_year_display,
            s.org,
            s.region,
            s.school,
            s.grade_level,
            s.calendar_day,
            s.metric,

            if(
                p.offers_cumulative = 1, p.student_finalsite_student_id, null
            ) as student_finalsite_student_id,

        from scaffold as s
        left join
            pending_offer_calcs as p
            on s.academic_year = p.academic_year
            and s.region = p.region
            and s.school = p.school
            and s.grade_level = p.grade_level
            and s.calendar_day = p.calendar_day
        where s.metric = 'Offers'

        union all

        select
            s._dbt_source_relation,
            s.academic_year_display,
            s.enrollment_academic_year,
            s.enrollment_academic_year_display,
            s.org,
            s.region,
            s.school,
            s.grade_level,
            s.calendar_day,
            s.metric,

            if(
                p.conversion_cumulative = 1, p.student_finalsite_student_id, null
            ) as student_finalsite_student_id,

        from scaffold as s
        left join
            pending_offer_calcs as p
            on s.academic_year = p.academic_year
            and s.region = p.region
            and s.school = p.school
            and s.grade_level = p.grade_level
            and s.calendar_day = p.calendar_day
        where s.metric = 'Conversion'

        union all

        select
            s._dbt_source_relation,
            s.academic_year_display,
            s.enrollment_academic_year,
            s.enrollment_academic_year_display,
            s.org,
            s.region,
            s.school,
            s.grade_level,
            s.calendar_day,
            s.metric,

            if(
                p.pending_offer_daily = 1, p.student_finalsite_student_id, null
            ) as student_finalsite_student_id,

        from scaffold as s
        left join
            pending_offer_calcs as p
            on s.academic_year = p.academic_year
            and s.region = p.region
            and s.school = p.school
            and s.grade_level = p.grade_level
            and s.calendar_day = p.calendar_day
        where s.metric = 'Pending Offers'

        union all

        select
            s._dbt_source_relation,
            s.academic_year_display,
            s.enrollment_academic_year,
            s.enrollment_academic_year_display,
            s.org,
            s.region,
            s.school,
            s.grade_level,
            s.calendar_day,
            s.metric,

            p.student_finalsite_student_id,

        from scaffold as s
        left join
            pending_offer_calcs as p
            on s.academic_year = p.academic_year
            and s.region = p.region
            and s.school = p.school
            and s.grade_level = p.grade_level
            and s.calendar_day = p.calendar_day
            and s.metric = p.pending_offer_timing_status
    )

select
    f.*,

    r.region as enrollment_region,
    r.schoolid as enrollment_schoolid,
    r.school as enrollment_school,
    r.student_number as enrollment_student_number,
    r.grade_level as enrollment_grade_level,
    r.enroll_status as enrollment_latest_enroll_status,
    r.is_enrolled_y1 as enrollment_is_enrolled_y1,
    r.is_enrolled_oct01 as enrollment_is_enrolled_oct01,
    r.is_enrolled_oct15 as enrollment_is_enrolled_oct15,
    r.is_self_contained as enrollment_is_self_contained,

from final as f
left join
    {{ ref("int_extracts__student_enrollments") }} as r
    on f.enrollment_academic_year = r.academic_year
    and f.student_number = r.student_number
    and {{ union_dataset_join_clause(left_alias="f", right_alias="r") }}
    and r.grade_level != 99
    and r.rn_year = 1
where f.calendar_day = current_date('{{ var("local_timezone") }}')
