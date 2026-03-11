with
    latest_status_calc as (
        select
            r.enrollment_academic_year,
            r.enrollment_academic_year_display,
            r.org,
            r.region,
            r.schoolid,
            r.school,
            r.finalsite_enrollment_id as finalsite_id,
            r.powerschool_student_number,
            r.first_name,
            r.last_name,
            r.grade_level,
            r.enrollment_type,
            r.self_contained,
            r.gender,
            r.birthdate,
            r.detailed_status,
            r.status_start_date,
            r.status_order,

            x.status_group_name,
            x.status_group_value,
            x.grouped_status_order,
            x.grouped_status_timeframe,

            'All' as aligned_enrollment_type,

            first_value(r.detailed_status) over (
                partition by r.finalsite_enrollment_id order by r.status_start_date desc
            ) as latest_status,

        from {{ ref("int_finalsite__status_report_unpivot") }} as r
        inner join
            {{ ref("int_google_sheets__finalsite__status_crosswalk_unpivot") }} as x
            on r._dagster_partition_key = x._dagster_partition_key
            and r.enrollment_type = x.enrollment_type
            and r.detailed_status = x.detailed_status
            and x.valid_detailed_status
            and not x.qa_flag
        /* hardcoding years here to ensure the correct file from FS is being used
           (these change by region at different dates) */
        where r.enrollment_academic_year = 2026 and r.file_year = 2026
    ),

    -- trunk-ignore(sqlfluff/ST03)
    cleaned_data as (
        select
            enrollment_academic_year,
            enrollment_academic_year_display,
            org,
            region,
            schoolid,
            finalsite_id,
            powerschool_student_number,
            first_name,
            last_name,
            grade_level,
            gender,
            birthdate,
            self_contained,
            enrollment_type,
            aligned_enrollment_type,
            status_group_value as grouped_status,
            grouped_status_order,
            grouped_status_timeframe,
            latest_status,

            if(latest_status = detailed_status, true, false) as latest_detailed_match,

            if(
                status_group_value in ('Inquiries', 'Applications'), region, school
            ) as school,

            max(status_start_date) over (
                partition by enrollment_academic_year, finalsite_id, status_group_value
            ) as grouped_status_start_date,

        from latest_status_calc
    ),

    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="cleaned_data",
                partition_by="finalsite_id, grouped_status",
                order_by="grouped_status_start_date desc",
            )
        }}
    ),

    roster as (
        -- ever statuses
        select
            enrollment_academic_year,
            enrollment_academic_year_display,
            org,
            region,
            schoolid,
            school,
            finalsite_id,
            powerschool_student_number,
            first_name,
            last_name,
            grade_level,
            gender,
            birthdate,
            self_contained,
            enrollment_type,
            grouped_status,
            latest_status,
            aligned_enrollment_type,
            grouped_status_order,
            grouped_status_timeframe,
            grouped_status_start_date,

            case
                grouped_status
                when 'Applications'
                then 'App Target'
                when 'Assigned School'
                then 'Overall Conversion'
                when 'Offers'
                then 'Offers Target'
                else grouped_status
            end as goal_name,

            case
                when
                    grouped_status in (
                        'Accepted to Enrolled',
                        'Offers to Accepted',
                        'Offers to Enrolled'
                    )
                then 'Conversion'
                else grouped_status
            end as goal_type,

        from deduplicate
        where grouped_status_timeframe = 'Ever'

        union all

        -- regular current
        select
            enrollment_academic_year,
            enrollment_academic_year_display,
            org,
            region,
            schoolid,
            school,
            finalsite_id,
            powerschool_student_number,
            first_name,
            last_name,
            grade_level,
            gender,
            birthdate,
            self_contained,
            enrollment_type,
            grouped_status,
            latest_status,
            aligned_enrollment_type,
            grouped_status_order,
            grouped_status_timeframe,
            grouped_status_start_date,

            grouped_status as goal_name,

            case
                when
                    grouped_status in (
                        'Accepted to Enrolled',
                        'Offers to Accepted',
                        'Offers to Enrolled'
                    )
                then 'Conversion'
                else grouped_status
            end as goal_type,

        from deduplicate
        where grouped_status_timeframe = 'Current'
    ),

    add_group_status_end_date as (
        select
            enrollment_academic_year,
            finalsite_id,
            enrollment_type,
            goal_type,
            goal_name,
            grouped_status,
            grouped_status_order,
            grouped_status_start_date,

            lead(grouped_status_start_date, 1, current_date('America/New_York')) over (
                partition by finalsite_id
                order by grouped_status_start_date asc, grouped_status_order asc
            ) as grouped_status_end_date,

        from roster
        where grouped_status_order != 0 and enrollment_type = 'New'
    ),

    days_in_grouped_status_calc as (
        select
            enrollment_academic_year,
            finalsite_id,
            enrollment_type,
            goal_type,
            goal_name,
            grouped_status,
            grouped_status_order,
            grouped_status_start_date,
            grouped_status_end_date,

            if(
                grouped_status_end_date = grouped_status_start_date,
                1,
                date_diff(grouped_status_end_date, grouped_status_start_date, day)
            ) as days_in_grouped_status,

        from add_group_status_end_date
    ),

    filter_days_in_status as (
        select
            * except (goal_name),

            case
                when goal_name = 'Pending Offers' and days_in_grouped_status <= 4
                then '<= 4 Days'
                when
                    goal_name = 'Pending Offers'
                    and days_in_grouped_status between 5 and 10
                then '>= 5 Days & <= 10 Days'
                when goal_name = 'Pending Offers' and days_in_grouped_status > 10
                then '> 10 Days'
                else goal_name
            end as goal_name,

        from days_in_grouped_status_calc
    ),

    final_roster as (
        select
            enrollment_academic_year,
            enrollment_academic_year_display,
            org,
            region,
            schoolid,
            school,
            finalsite_id,
            powerschool_student_number,
            first_name,
            last_name,
            grade_level,
            gender,
            birthdate,
            self_contained,
            enrollment_type,
            grouped_status,
            latest_status,
            aligned_enrollment_type,
            grouped_status_order,
            grouped_status_timeframe,
            grouped_status_start_date,

            goal_type,

            goal_name,

        from roster

        union all

        -- moved here to not include these expanded goal types in days in status calc
        select
            d.enrollment_academic_year,
            d.enrollment_academic_year_display,
            d.org,
            d.region,
            d.schoolid,
            d.school,
            d.finalsite_id,
            d.powerschool_student_number,
            d.first_name,
            d.last_name,
            d.grade_level,
            d.gender,
            d.birthdate,
            d.self_contained,
            d.enrollment_type,
            d.grouped_status,
            d.latest_status,
            d.aligned_enrollment_type,
            d.grouped_status_order,
            d.grouped_status_timeframe,
            d.grouped_status_start_date,

            d.grouped_status as goal_type,

            grouped_status_expand as goal_name,

        from deduplicate as d
        cross join
            unnest(
                ['<= 4 Days', '>= 5 & <= 10 Days', '> 10 Days']
            ) as grouped_status_expand
        where
            d.grouped_status_timeframe = 'Current'
            and d.grouped_status = 'Pending Offers'
    )

-- maintain pending offers general
select
    r.enrollment_academic_year,
    r.enrollment_academic_year_display,
    r.org,
    r.region,
    r.schoolid,
    r.school,
    r.finalsite_id,
    r.powerschool_student_number,
    r.first_name,
    r.last_name,
    r.grade_level,
    r.gender,
    r.birthdate,
    r.self_contained,
    r.enrollment_type,
    r.grouped_status,
    r.latest_status,
    r.aligned_enrollment_type,
    r.grouped_status_order,
    r.grouped_status_timeframe,
    r.grouped_status_start_date,
    r.goal_name,
    r.goal_type,

    d.grouped_status_end_date,
    d.days_in_grouped_status,

    e.enroll_status,
    e.is_enrolled_fdos,
    e.is_enrolled_oct01,
    e.is_enrolled_oct15,

from final_roster as r
left join
    filter_days_in_status as d
    on r.enrollment_academic_year = d.enrollment_academic_year
    and r.finalsite_id = d.finalsite_id
    and r.enrollment_type = d.enrollment_type
    and r.grouped_status = d.grouped_status
    and r.goal_type = d.goal_type
    and r.goal_name = d.goal_name
left join
    {{ ref("int_extracts__student_enrollments") }} as e
    on r.enrollment_academic_year = e.academic_year
    and r.finalsite_id = e.infosnap_id
    and e.rn_year = 1
where r.goal_name not in ('<= 4 Days', '>= 5 & <= 10 Days', '> 10 Days')

union all
-- ensure pending offers timeframes have day in status
select
    r.enrollment_academic_year,
    r.enrollment_academic_year_display,
    r.org,
    r.region,
    r.schoolid,
    r.school,
    r.finalsite_id,
    r.powerschool_student_number,
    r.first_name,
    r.last_name,
    r.grade_level,
    r.gender,
    r.birthdate,
    r.self_contained,
    r.enrollment_type,
    r.grouped_status,
    r.latest_status,
    r.aligned_enrollment_type,
    r.grouped_status_order,
    r.grouped_status_timeframe,
    r.grouped_status_start_date,
    r.goal_name,
    r.goal_type,

    d.grouped_status_end_date,
    d.days_in_grouped_status,

    e.enroll_status,
    e.is_enrolled_fdos,
    e.is_enrolled_oct01,
    e.is_enrolled_oct15,

from final_roster as r
left join
    filter_days_in_status as d
    on r.enrollment_academic_year = d.enrollment_academic_year
    and r.finalsite_id = d.finalsite_id
    and r.enrollment_type = d.enrollment_type
    and r.grouped_status = d.grouped_status
    and r.goal_type = d.goal_type
left join
    {{ ref("int_extracts__student_enrollments") }} as e
    on r.enrollment_academic_year = e.academic_year
    and r.finalsite_id = e.infosnap_id
    and e.rn_year = 1
where r.goal_name in ('<= 4 Days', '>= 5 & <= 10 Days', '> 10 Days')
