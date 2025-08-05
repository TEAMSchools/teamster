-- History w/ recent row
with
    media_history as (
        select
            *,
            cast(created_time as date) as created_date,
            case
                username
                when 'kippnj'
                then '17841401733578100'
                when 'kippmiami'
                then '17841407132914300'
            end as ig_account_id,

        from {{ source("instagram_business", "media_history") }}
        where carousel_album_id is null
    )

    {{
        dbt_utils.deduplicate(
            relation="media_history",
            partition_by="id",
            order_by="_fivetran_synced desc",
        )
    }}
