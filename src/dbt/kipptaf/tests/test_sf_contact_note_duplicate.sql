-- depends_on: {{ ref("stg_kippadb__contact_note") }}
with
    salesforce_notes as (
        select
            id,
            `name`,
            contact__c,
            subject__c,
            date__c,
            status__c,
            type__c,

            regexp_replace(trim(comments__c), r'\s+', ' ') as comments__c,
            regexp_replace(trim(next_steps__c), r'\s+', ' ') as next_steps__c,
        from {{ source("kippadb", "contact_note") }}
        -- record not accessible to fix on SF
        where not isdeleted and id != 'a0LQg00000SOadzMAD'
    ),

    row_counting as (
        select
            *,

            -- blank comments partition by id, matching stg_kippadb__contact_note
            row_number() over (
                partition by
                    contact__c,
                    subject__c,
                    if(comments__c != '', comments__c, id),
                    next_steps__c,
                    date__c,
                    status__c,
                    type__c
                order by `name`
            ) as order_rows,
        from salesforce_notes
    )

select
    id,
    `name`,
    contact__c,
    subject__c,
    comments__c,
    next_steps__c,
    date__c,
    status__c,
    type__c,
from row_counting
where order_rows > 1
