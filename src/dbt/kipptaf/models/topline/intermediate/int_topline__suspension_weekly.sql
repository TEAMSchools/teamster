with
    suspension_type as (
        select penalty_name, 'ISS' as suspension_type,
        from
            unnest(
                [
                    'In School Suspension',
                    'KM: In-School Suspension',
                    'KNJ: In-School Suspension'
                ]
            ) as penalty_name

        union all

        select penalty_name, 'OSS' as suspension_type,
        from
            unnest(
                [
                    'Out of School Suspension',
                    'KM: Out-of-School Suspension',
                    'KNJ: Out-of-School Suspension'
                ]
            ) as penalty_name
    ),

    incidents_penalties as (
        select
            i.student_school_id,
            i.school_id,
            i.incident_id,
            i._dbt_source_relation,
            i.create_ts_academic_year,
            i.referral_tier,

            p.start_date,
            p.end_date,
            p.num_days,
            p.incident_penalty_id,
            p.is_suspension,

            s.suspension_type,
        from {{ ref("stg_deanslist__incidents") }} as i
        left join
            {{ ref("stg_deanslist__incidents__penalties") }} as p
            on i.incident_id = p.incident_id
            and {{ union_dataset_join_clause(left_alias="i", right_alias="p") }}
        left join suspension_type as s on p.penalty_name = s.penalty_name
        where i.referral_tier not in ('Non-Behavioral', 'Social Work')
    ),

    calcs as (
        select
            co.student_number,
            co.academic_year,
            co.schoolid,
            co.week_start_monday,
            co.week_end_sunday,
            co.week_number_academic_year,
            co.is_current_week_mon_sun,

            count(
                distinct if(ip.is_suspension, ip.incident_penalty_id, null)
            ) as suspension_count_all,
            count(
                distinct if(
                    ip.is_suspension and ip.suspension_type = 'OSS',
                    ip.incident_penalty_id,
                    null
                )
            ) as suspension_count_oss,
            count(
                distinct if(
                    ip.is_suspension and ip.suspension_type = 'ISS',
                    ip.incident_penalty_id,
                    null
                )
            ) as suspension_count_iss,
            sum(if(ip.is_suspension, ip.num_days, null)) as days_suspended_all,
            sum(
                if(ip.is_suspension and ip.suspension_type = 'OSS', ip.num_days, null)
            ) as days_suspended_oss,
            sum(
                if(ip.is_suspension and ip.suspension_type = 'ISS', ip.num_days, null)
            ) as days_suspended_iss,
            count(distinct ip.incident_id) as referral_count_all,
            count(
                distinct if(ip.referral_tier = 'High', ip.incident_id, null)
            ) as referral_count_high,
            count(
                distinct if(ip.referral_tier = 'Middle', ip.incident_id, null)
            ) as referral_count_middle,
            count(
                distinct if(ip.referral_tier = 'low', ip.incident_id, null)
            ) as referral_count_low,
        from {{ ref("int_extracts__student_enrollments_weeks") }} as co
        left join
            incidents_penalties as ip
            on co.student_number = ip.student_school_id
            and co.academic_year = ip.create_ts_academic_year
            and co.deanslist_school_id = ip.school_id
            and ip.start_date between co.week_start_monday and co.week_end_sunday
        group by
            co.student_number,
            co.academic_year,
            co.schoolid,
            co.week_start_monday,
            co.week_end_sunday,
            co.week_number_academic_year,
            co.is_current_week_mon_sun
    )

select
    student_number,
    academic_year,
    schoolid,
    week_start_monday,
    week_end_sunday,
    week_number_academic_year,
    is_current_week_mon_sun,

    /* suspension counts */
    sum(suspension_count_all) over (
        partition by student_number, academic_year, schoolid
        order by week_start_monday asc
    ) as suspension_all_running,
    sum(suspension_count_oss) over (
        partition by student_number, academic_year, schoolid
        order by week_start_monday asc
    ) as suspension_oss_running,
    sum(suspension_count_iss) over (
        partition by student_number, academic_year, schoolid
        order by week_start_monday asc
    ) as suspension_iss_running,

    /* days suspended */
    coalesce(
        sum(days_suspended_all) over (
            partition by student_number, academic_year, schoolid
            order by week_start_monday asc
        ),
        0
    ) as days_suspended_all_running,
    coalesce(
        sum(days_suspended_oss) over (
            partition by student_number, academic_year, schoolid
            order by week_start_monday asc
        ),
        0
    ) as days_suspended_oss_running,
    coalesce(
        sum(days_suspended_iss) over (
            partition by student_number, academic_year, schoolid
            order by week_start_monday asc
        ),
        0
    ) as days_suspended_iss_running,

    /* referral counts */
    sum(referral_count_all) over (
        partition by student_number, academic_year, schoolid
        order by week_start_monday asc
    ) as referral_count_all_running,
    sum(referral_count_high) over (
        partition by student_number, academic_year, schoolid
        order by week_start_monday asc
    ) as referral_count_high_running,
    sum(referral_count_middle) over (
        partition by student_number, academic_year, schoolid
        order by week_start_monday asc
    ) as referral_count_middle_running,
    sum(referral_count_low) over (
        partition by student_number, academic_year, schoolid
        order by week_start_monday asc
    ) as referral_count_low_running,

    /* is_suspended running calcs */
    if(
        sum(suspension_count_all) over (
            partition by student_number, academic_year, schoolid
            order by week_start_monday asc
        )
        > 0,
        1,
        0
    ) as is_suspended_y1_all_running,
    if(
        sum(suspension_count_oss) over (
            partition by student_number, academic_year, schoolid
            order by week_start_monday asc
        )
        > 0,
        1,
        0
    ) as is_suspended_y1_oss_running,
    if(
        sum(suspension_count_iss) over (
            partition by student_number, academic_year, schoolid
            order by week_start_monday asc
        )
        > 0,
        1,
        0
    ) as is_suspended_y1_iss_running,
    if(
        sum(suspension_count_all) over (
            partition by student_number, academic_year, schoolid
            order by week_start_monday asc
        )
        > 1,
        1,
        0
    ) as is_suspended_y1_all_2plus_running,
    if(
        sum(suspension_count_oss) over (
            partition by student_number, academic_year, schoolid
            order by week_start_monday asc
        )
        > 1,
        1,
        0
    ) as is_suspended_y1_oss_2plus_running,
    if(
        sum(suspension_count_iss) over (
            partition by student_number, academic_year, schoolid
            order by week_start_monday asc
        )
        > 1,
        1,
        0
    ) as is_suspended_y1_iss_2plus_running,
from calcs
