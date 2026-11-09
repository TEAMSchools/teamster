-- depends_on: {{ ref("stg_kippadb__contact_note") }}
with
    salesforce_notes as (
        select
            n.id,
            n.name,
            n.contact__c,
            n.subject__c,
            n.date__c,
            n.status__c,
            n.type__c,

            regexp_replace(trim(n.comments__c), r'\s+', ' ') as comments__c,
            regexp_replace(trim(n.next_steps__c), r'\s+', ' ') as next_steps__c,

            {{
                date_to_fiscal_year(
                    date_field="n.date__c", start_month=7, year_source="start"
                )
            }} as academic_year,
        from {{ source("kippadb", "contact_note") }} as n
        left join {{ ref("stg_kippadb__contact") }} as ktc on n.contact__c = ktc.id
        where
            not n.isdeleted
            and n.id != 'a0LQg00000SOadzMAD'
            and ktc.advising_provider is null
    ),

    row_counting as (
        select
            *,

            row_number() over (
                partition by
                    contact__c,
                    subject__c,
                    comments__c,
                    next_steps__c,
                    date__c,
                    status__c,
                    type__c
                order by `name`
            ) as order_rows,
        from salesforce_notes
        where academic_year >= 2025
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
where order_rows > 1 and comments__c != ''
