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

    calcs as (
        select
            dli.student_school_id as student_number,

            cw.academic_year,
            cw.schoolid,
            cw.week_start_monday,
            cw.week_end_sunday,
            cw.week_number_academic_year,
            cw.is_current_week_mon_sun,

            count(
                distinct if(dlp.is_suspension, dlp.incident_penalty_id, null)
            ) as suspension_count_all,

            count(
                distinct if(
                    dlp.is_suspension and st.suspension_type = 'OSS',
                    dlp.incident_penalty_id,
                    null
                )
            ) as suspension_count_oss,

            count(
                distinct if(
                    dlp.is_suspension and st.suspension_type = 'ISS',
                    dlp.incident_penalty_id,
                    null
                )
            ) as suspension_count_iss,

            sum(if(dlp.is_suspension, dlp.num_days, null)) as days_suspended_all,

            sum(
                if(dlp.is_suspension and st.suspension_type = 'OSS', dlp.num_days, null)
            ) as days_suspended_oss,

            sum(
                if(dlp.is_suspension and st.suspension_type = 'ISS', dlp.num_days, null)
            ) as days_suspended_iss,

            count(distinct dli.incident_id) as referral_count_all,

            count(
                distinct if(dli.referral_tier = 'High', dli.incident_id, null)
            ) as referral_count_high,

            count(
                distinct if(dli.referral_tier = 'Middle', dli.incident_id, null)
            ) as referral_count_middle,

            count(
                distinct if(dli.referral_tier = 'low', dli.incident_id, null)
            ) as referral_count_low,
        from {{ ref("stg_deanslist__incidents") }} as dli
        inner join
            {{ ref("stg_deanslist__incidents__penalties") }} as dlp
            on dli.incident_id = dlp.incident_id
            and {{ union_dataset_join_clause(left_alias="dli", right_alias="dlp") }}
        inner join suspension_type as st on dlp.penalty_name = st.penalty_name
        inner join
            {{ ref("stg_people__location_crosswalk") }} as lc
            on dlp.school_id = lc.deanslist_school_id
        inner join
            {{ ref("int_powerschool__calendar_week") }} as cw
            on lc.powerschool_school_id = cw.schoolid
            and dli.create_ts_academic_year = cw.academic_year
            and dlp.start_date between cw.week_start_monday and cw.week_end_sunday
        left join
            {{ ref("int_deanslist__incidents__custom_fields__pivot") }} as cf
            on dli.incident_id = cf.incident_id
            and {{ union_dataset_join_clause(left_alias="dli", right_alias="cf") }}
        where dli.referral_tier not in ('Non-Behavioral', 'Social Work')
        group by
            dli.student_school_id,
            cw.academic_year,
            cw.schoolid,
            cw.week_start_monday,
            cw.week_end_sunday,
            cw.week_number_academic_year,
            cw.is_current_week_mon_sun
    )

select
    student_number,
    academic_year,
    schoolid,
    week_start_monday,
    week_end_sunday,
    week_number_academic_year,
    is_current_week_mon_sun,

    sum(suspension_count_all) over (
        partition by student_number, academic_year, schoolid
        order by week_start_monday asc
    ) as suspension_all_running,
from calcs
