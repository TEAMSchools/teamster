with
    incidents as (
        select
            i.*,

            cfp.* except (incident_id),

            u.full_name as approver_full_name,
            u.lastfirst as approver_lastfirst,

            case
                when left(i.category, 2) in ('SW', 'SS')
                then 'Social Work'
                when
                    left(i.category, 2) = 'TX'
                    or i.category like 'Documentation%'
                    or i.category
                    in ('School Clinic', 'Incident Report/Accident Report')
                then 'Non-Behavioral'
                when left(i.category, 2) = 'T1' or left(i.category, 6) = 'Tier 1'
                then 'Low'
                when left(i.category, 2) = 'T2' or left(i.category, 6) = 'Tier 2'
                then 'Middle'
                when left(i.category, 2) = 'T3' or left(i.category, 6) = 'Tier 3'
                then 'High'
                when i.category is not null
                then 'Other'
            end as referral_tier,
        from {{ ref("stg_deanslist__incidents") }} as i
        left join
            {{ ref("int_deanslist__incidents__custom_fields__pivot") }} as cfp
            on i.incident_id = cfp.incident_id
        left join
            {{ ref("stg_deanslist__users") }} as u on cfp.approver_name = u.dl_user_id
    )

select
    *,

    coalesce(
        referral_tier not in ('Social Work', 'Non-Behavioral'), false
    ) as is_behavioral_referral,
from incidents
