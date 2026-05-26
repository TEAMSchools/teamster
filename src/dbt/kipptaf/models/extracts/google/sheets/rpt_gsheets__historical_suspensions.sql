with
    agg_by_school as (
        select
            student_school_id,
            create_ts_academic_year,
            school_id,

            count(
                distinct if(is_suspension, incident_penalty_id, null)
            ) as suspension_count_all,

            count(
                distinct if(
                    is_suspension and suspension_type = 'OSS', incident_penalty_id, null
                )
            ) as suspension_count_oss,

            count(
                distinct if(
                    is_suspension and suspension_type = 'ISS', incident_penalty_id, null
                )
            ) as suspension_count_iss,

            sum(if(is_suspension, num_days, null)) as days_suspended_all,

            sum(
                if(is_suspension and suspension_type = 'OSS', num_days, null)
            ) as days_suspended_oss,

            sum(
                if(is_suspension and suspension_type = 'ISS', num_days, null)
            ) as days_suspended_iss,
        from {{ ref("int_deanslist__incidents__penalties") }}
        where referral_tier not in ('Non-Behavioral', 'Social Work')
        group by student_school_id, create_ts_academic_year, school_id
    )

select
    co.academic_year,
    co.academic_year_display,
    co.region,
    co.school,
    co.iep_status,
    co.lep_status,
    co.gender,
    co.grade_level,

    coalesce(ag.suspension_count_all, 0) as suspension_count_all,
    coalesce(ag.suspension_count_oss, 0) as suspension_count_oss,
    coalesce(ag.suspension_count_iss, 0) as suspension_count_iss,
    coalesce(ag.days_suspended_all, 0) as days_suspended_all,
    coalesce(ag.days_suspended_oss, 0) as days_suspended_oss,
    coalesce(ag.days_suspended_iss, 0) as days_suspended_iss,

    if(ag.suspension_count_all > 0, 1, 0) as is_suspended_all_y1_int,
    if(ag.suspension_count_oss > 0, 1, 0) as is_suspended_oss_y1_int,
from {{ ref("int_extracts__student_enrollments") }} as co
left join
    agg_by_school as ag
    on co.student_number = ag.student_school_id
    and co.academic_year = ag.create_ts_academic_year
    and co.deanslist_school_id = ag.school_id
where co.academic_year >= 2019 and co.grade_level != 99
