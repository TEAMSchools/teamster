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
    )

select
    dlp.student_school_id,
    dlp.create_ts_academic_year,

    rt.name as term,

    count(distinct dlp.incident_id) as referral_count_all,

    sum(if(dlp.is_suspension, dlp.num_days, null)) as days_suspended_all,

    count(
        distinct if(dlp.referral_tier = 'High', dlp.incident_id, null)
    ) as referral_count_high,

    count(
        distinct if(dlp.referral_tier = 'Middle', dlp.incident_id, null)
    ) as referral_count_middle,

    count(
        distinct if(dlp.referral_tier = 'low', dlp.incident_id, null)
    ) as referral_count_low,

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

    sum(
        if(dlp.is_suspension and st.suspension_type = 'OSS', dlp.num_days, null)
    ) as days_suspended_oss,

    sum(
        if(dlp.is_suspension and st.suspension_type = 'ISS', dlp.num_days, null)
    ) as days_suspended_iss,

from {{ ref("int_deanslist__incidents__penalties") }} as dlp
inner join suspension_type as st on dlp.penalty_name = st.penalty_name
inner join
    {{ ref("stg_people__location_crosswalk") }} as lc
    on dlp.school_id = lc.deanslist_school_id
inner join
    {{ ref("stg_reporting__terms") }} as rt
    on lc.powerschool_school_id = rt.school_id
    and dlp.create_ts_academic_year = rt.academic_year
    and dlp.start_date between rt.start_date and rt.end_date
    and rt.type = 'RT'
where dlp.referral_tier not in ('Non-Behavioral', 'Social Work')
group by dlp.student_school_id, dlp.create_ts_academic_year, rt.name

union all

select
    dlp.student_school_id,
    dlp.create_ts_academic_year,

    'Y1' as term,

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

    count(distinct dlp.incident_id) as referral_count_all,

    count(
        distinct if(dlp.referral_tier = 'High', dlp.incident_id, null)
    ) as referral_count_high,

    count(
        distinct if(dlp.referral_tier = 'Middle', dlp.incident_id, null)
    ) as referral_count_middle,

    count(
        distinct if(dlp.referral_tier = 'low', dlp.incident_id, null)
    ) as referral_count_low,
from {{ ref("int_deanslist__incidents__penalties") }} as dlp
left join suspension_type as st on dlp.penalty_name = st.penalty_name
where dlp.referral_tier not in ('Non-Behavioral', 'Social Work')
group by dlp.student_school_id, dlp.create_ts_academic_year
