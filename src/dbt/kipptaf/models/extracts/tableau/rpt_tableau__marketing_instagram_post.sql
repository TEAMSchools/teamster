{{ config(enabled=false) }}

select
    h.ig_account_id,
    h.username,
    h.permalink,
    h.is_story,
    h.media_type,
    h.media_product_type,
    h.id as id_history,
    h.created_date as created_time,

    i._fivetran_id,
    i._fivetran_synced,
    i.carousel_album_engagement,
    i.carousel_album_impressions,
    i.carousel_album_reach,
    i.carousel_album_saved,
    i.carousel_album_video_views,
    i.comment_count,
    i.like_count,
    i.reel_comments,
    i.reel_likes,
    i.reel_plays,
    i.reel_reach,
    i.reel_saved,
    i.reel_shares,
    i.reel_total_interactions,
    i.story_exits,
    i.story_impressions,
    i.story_reach,
    i.story_replies,
    i.story_taps_back,
    i.story_taps_forward,
    i.video_photo_engagement,
    i.video_photo_impressions,
    i.video_photo_reach,
    i.video_photo_saved,
    i.video_views,
    i.total_like_comments,
    i.id as id_insights,

    null as caption,
from {{ ref("stg_instagram_business__media_history") }} as h
left join {{ ref("stg_instagram_business__media_insights") }} as i on h.id = i.id
