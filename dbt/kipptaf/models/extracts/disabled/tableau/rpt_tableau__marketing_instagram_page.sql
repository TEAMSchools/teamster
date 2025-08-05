select
    ui.id,
    ui.`date`,
    ui.profile_views,
    ui.reach,
    ui.reach_28_d,

    uh.followers_count,
    uh.media_count,
from {{ source("instagram_business", "user_insights") }} as ui
left join
    {{ ref("stg_instagram_business__user_history") }} as uh
    on ui.id = uh.id
    and ui.`date` >= uh._fivetran_synced_date_prev
    and ui.`date` < uh._fivetran_synced_date
