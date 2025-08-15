select
    i.*,

    u.full_name as approver_full_name,
    u.lastfirst as approver_lastfirst,

    cfp.* except (incident_id),

    case
        when i.category_tier in ('SW', 'SS', 'SSC')
        then 'Social Work'
        when i.category_tier = 'TX'
        then 'Non-Behavioral'
        when i.category in ('School Clinic', 'Incident Report/Accident Report')
        then 'Non-Behavioral'
        /* Miami-only */
        when i.category_tier in ('T4', 'T3') and {{ project_name }} = '%kippmiami%'
        then 'Low'
        when i.category_tier = 'T1' and {{ project_name }} = like '%kippmiami%'
        then 'High'
        /* all other regions */
        when i.category_tier in ('T1', 'Tier 1')
        then 'Low'
        when i.category_tier in ('T2', 'Tier 2')
        then 'Middle'
        when i.category_tier in ('T3', 'Tier 3')
        then 'High'
        when i.category is not null
        then 'Other'
    end as referral_tier,
from {{ ref("stg_deanslist__incidents") }} as i
left join {{ ref("stg_deanslist__users") }} as u on i.approver_name = u.dl_user_id
left join
    {{ ref("int_deanslist__incidents__custom_fields__pivot") }} as cfp
    on i.incident_id = cfp.incident_id
