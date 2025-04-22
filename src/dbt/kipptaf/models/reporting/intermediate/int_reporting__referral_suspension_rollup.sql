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

    incidents as (
        select
            *,
            case
                when regexp_extract(category, r'^(.*?)\s*-\s*') in ('SW', 'SS', 'SSC')
                then 'Social Work'
                when
                    regexp_extract(category, r'^(.*?)\s*-\s*') = 'TX'

                    or category in ('School Clinic', 'Incident Report/Accident Report')
                then 'Non-Behavioral'
                when
                    (
                        regexp_extract(category, r'^(.*?)\s*-\s*') in ('T1', 'Tier 1')
                        and regexp_extract(_dbt_source_relation, r'(kipp\w+)_')
                        != 'kippmiami'
                    )
                    or (
                        regexp_extract(category, r'^(.*?)\s*-\s*') in ('T4', 'T3')
                        and regexp_extract(_dbt_source_relation, r'(kipp\w+)_')
                        = 'kippmiami'
                    )
                then 'Low'
                when regexp_extract(category, r'^(.*?)\s*-\s*') in ('T2', 'Tier 2')
                then 'Middle'
                when
                    (
                        regexp_extract(category, r'^(.*?)\s*-\s*') in ('T3', 'Tier 3')
                        and regexp_extract(_dbt_source_relation, r'(kipp\w+)_')
                        != 'kippmiami'
                    )
                    or (
                        regexp_extract(category, r'^(.*?)\s*-\s*') = 'T1'
                        and regexp_extract(_dbt_source_relation, r'(kipp\w+)_')
                        = 'kippmiami'
                    )
                then 'High'
                when category is null
                then null
                else 'Other'
            end as referral_tier,
        from {{ ref("stg_deanslist__incidents") }}
    )

select
    dli.student_school_id,
    dli.create_ts_academic_year,

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
from incidents as dli
left join
    {{ ref("stg_deanslist__incidents__penalties") }} as dlp
    on dli.incident_id = dlp.incident_id
    and {{ union_dataset_join_clause(left_alias="dli", right_alias="dlp") }}
left join
    {{ ref("int_deanslist__incidents__custom_fields__pivot") }} as cf
    on dli.incident_id = cf.incident_id
    and {{ union_dataset_join_clause(left_alias="dli", right_alias="cf") }}
left join suspension_type as st on dlp.penalty_name = st.penalty_name
where dli.referral_tier not in ('Non-Behavioral', 'Social Work')
group by all
