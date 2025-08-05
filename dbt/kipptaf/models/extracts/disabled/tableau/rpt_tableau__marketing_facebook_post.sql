select
    ph.id,
    ph.page_id,
    ph.status_type,
    ph._fivetran_synced,
    safe_cast(ph.updated_time as date) as updated_date,
    safe_cast(ph.created_time as date) as created_date,

    -- post lifetime metrics
    max(pm.post_impressions) as post_impressions,
    max(pm.post_impressions_paid) as post_impressions_paid,
    max(pm.post_impressions_organic) as post_impressions_organic,
    max(pm.post_impressions_nonviral) as post_impressions_nonviral,
    max(pm.post_impressions_viral) as post_impressions_viral,
    max(pm.post_clicks) as post_clicks,

    max(pm.post_reactions_like_total)
    + max(pm.post_reactions_love_total)
    + max(pm.post_reactions_wow_total)
    + max(pm.post_reactions_haha_total)
    + max(pm.post_reactions_sorry_total)
    + max(pm.post_reactions_anger_total) as total_post_engagement,

    row_number() over (partition by ph.id order by ph.updated_time desc) as row_recent,
from {{ source("facebook_pages", "post_history") }} as ph
inner join
    {{ source("facebook_pages", "lifetime_post_metrics_total") }} as pm
    on ph.id = pm.post_id
group by
    ph.id,
    ph.updated_time,
    ph.created_time,
    ph.page_id,
    ph.status_type,
    ph._fivetran_synced
