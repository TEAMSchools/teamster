with
    salesforce_notes as (
        select
            n.id,
            n.name,
            n.contact,
            n.subject,
            n.date,
            n.status,
            n.type,
            n.academic_year,

            trim(
                regexp_replace(regexp_replace(n.comments, r'\r|\n', ' '), r'\s+', ' ')
            ) as comments,

            trim(
                regexp_replace(regexp_replace(n.next_steps, r'\r|\n', ' '), r'\s+', ' ')
            ) as next_steps,

        from {{ ref("stg_kippadb__contact_note") }} as n
        left join {{ ref("stg_kippadb__contact") }} as ktc on n.contact = ktc.id
        where n.academic_year >= 2025 and ktc.advising_provider is null
    ),

    row_counting as (
        select
            *,

            row_number() over (
                partition by
                    contact, `subject`, comments, next_steps, `date`, `status`, `type`
                order by `name`
            ) as order_rows,

        from salesforce_notes
    )

select
    id,
    `name`,
    contact as contact__c,
    `subject` as subject__c,
    comments as comments__c,
    next_steps as next_steps__c,
    `date` as date__c,
    `status` as status__c,
    `type` as type__c,
from row_counting
where order_rows > 1 and comments != ''
