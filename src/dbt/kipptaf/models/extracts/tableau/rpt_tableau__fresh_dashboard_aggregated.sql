with
    scaffold as (
        select
            b.academic_year as powerschool_academic_year,
            b.org,
            b.region,
            b.schoolid,
            b.school,
            b.grade_level,

            x.enrollment_academic_year,
            x.enrollment_academic_year_display,
            x.enrollment_type,
            x.overall_status,
            x.funnel_status,
            x.status_category,
            x.offered_status,
            x.offered_status_detailed,
            x.detailed_status_ranking,
            x.detailed_status_branched_ranking,
            x.detailed_status,
            x.sre_academic_year_start,
            x.sre_academic_year_end,

            calendar_day,

            metric,

        from {{ ref("stg_google_sheets__finalsite__school_scaffold") }} as b
        inner join
            {{ ref("stg_google_sheets__finalsite__status_crosswalk") }} as x
            on b.academic_year = x.enrollment_academic_year
        cross join
            unnest(
                generate_date_array(
                    -- trunk-ignore(sqlfluff/LT01)
                    date_trunc(x.sre_academic_year_start, week(monday)),
                    -- trunk-ignore(sqlfluff/LT01)
                    date_trunc(x.sre_academic_year_end, week(monday)),
                    interval 1 day
                )
            ) as calendar_day
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
    ),

    max_custom_status as (
        select
            enrollment_academic_year,
            enrollment_academic_year_display,
            student_org,
            student_region,
            student_school,
            student_finalsite_student_id,
            student_grade_level,
            calendar_day,

            max(student_applicant_ops) over (
                partition by enrollment_academic_year, student_finalsite_student_id
            ) as application_cumulative,

            max(student_offered_ops) over (
                partition by enrollment_academic_year, student_finalsite_student_id
            ) as offers_cumulative,

            max(student_overall_conversion_ops) over (
                partition by enrollment_academic_year, student_finalsite_student_id
            ) as conversion_cumulative,

            max(student_pending_offer_ops) over (
                partition by
                    enrollment_academic_year, student_finalsite_student_id, calendar_day
            ) as pending_offer_daily,

        from {{ ref("int_tableau__finalsite_student_scaffold") }}
    ),

    pending_offer_calcs as (
        select
            enrollment_academic_year,
            enrollment_academic_year_display,
            student_org,
            student_region,
            student_school,
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
                        partition by
                            enrollment_academic_year, student_finalsite_student_id
                        order by calendar_day asc
                    )
                    <= 4
                then 'Pending Offer <= 4'
                when
                    pending_offer_daily = 1
                    and sum(pending_offer_daily) over (
                        partition by
                            enrollment_academic_year, student_finalsite_student_id
                        order by calendar_day asc
                    )
                    between 5 and 10
                then 'Pending Offer >= 5 & <=10'
                when
                    pending_offer_daily = 1
                    and sum(pending_offer_daily) over (
                        partition by
                            enrollment_academic_year, student_finalsite_student_id
                        order by calendar_day asc
                    )
                    > 10
                then 'Pending Offer > 10'
            end as pending_offer_timing_status,

        from max_custom_status
    ),

    final as (
        select
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
            on s.enrollment_academic_year = p.enrollment_academic_year
            and s.region = p.student_region
            and s.school = p.student_school
            and s.grade_level = p.student_grade_level
            and s.calendar_day = p.calendar_day
        where s.metric = 'Applications'

        union all

        select
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
            on s.enrollment_academic_year = p.enrollment_academic_year
            and s.region = p.student_region
            and s.school = p.student_school
            and s.grade_level = p.student_grade_level
            and s.calendar_day = p.calendar_day
        where s.metric = 'Offers'

        union all

        select
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
            on s.enrollment_academic_year = p.enrollment_academic_year
            and s.region = p.student_region
            and s.school = p.student_school
            and s.grade_level = p.student_grade_level
            and s.calendar_day = p.calendar_day
        where s.metric = 'Conversion'

        union all

        select
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
            on s.enrollment_academic_year = p.enrollment_academic_year
            and s.region = p.student_region
            and s.school = p.student_school
            and s.grade_level = p.student_grade_level
            and s.calendar_day = p.calendar_day
        where s.metric = 'Pending Offers'

        union all

        select
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
            on s.enrollment_academic_year = p.enrollment_academic_year
            and s.region = p.student_region
            and s.school = p.student_school
            and s.grade_level = p.student_grade_level
            and s.calendar_day = p.calendar_day
            and s.metric = p.pending_offer_timing_status
    )

select
    f.enrollment_academic_year,
    f.enrollment_academic_year_display,
    f.org,
    f.region,
    f.school,
    f.grade_level,
    f.calendar_day,
    f.metric,
    f.student_finalsite_student_id,

    g.goal_value,

    if(f.metric = 'Offers', 'Offers', f.metric) as goal_type,
    if(f.metric = 'Offers', 'Offers Target', null) as goal_name,

from final as f
left join
    {{ ref("stg_google_sheets__finalsite__goals") }} as g
    on f.enrollment_academic_year = g.enrollment_academic_year
    and f.school = g.school
    and g.goal_type = 'Applications'
    and g.goal_granularity = 'School'
where f.calendar_day = current_date('{{ var("local_timezone") }}')
