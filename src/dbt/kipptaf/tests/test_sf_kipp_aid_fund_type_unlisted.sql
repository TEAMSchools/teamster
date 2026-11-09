-- depends_on: {{ ref("stg_kippadb__kipp_aid") }}
with
    kipp_aid as (
        select
            id,

            regexp_contains(notes__c, r'\[MAHER_FUND\|[^\]]*\]') as is_maher,
            regexp_extract(
                notes__c, r'\[MAHER_FUND\|[^\]]*?type=([A-Za-z]+)'
            ) as fund_type,
        from {{ source("kippadb", "kipp_aid") }}
        where not isdeleted
    ),

    checked as (
        select
            id,
            is_maher,
            fund_type,

            -- keep in step with the list in stg_kippadb__kipp_aid
            coalesce(
                fund_type in ('Emergency', 'Enrichment', 'Unclassified'), false
            ) as is_listed_type,
        from kipp_aid
    )

select id, fund_type,
from checked
where is_maher and not is_listed_type
