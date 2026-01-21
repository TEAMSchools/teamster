with
    salesforce_notes as (
        select
            n.id,
            n.name,
            n.contact as contact__c,
            n.`subject` as subject__c,
            n.`date` as date__c,
            n.`status` as status__c,
            n.`type` as type__c,
            n.academic_year,

            trim(
                regexp_replace(regexp_replace(n.comments, r'\r|\n', ' '), r'\s+', ' ')
            ) as comments__c,

            trim(
                regexp_replace(regexp_replace(n.next_steps, r'\r|\n', ' '), r'\s+', ' ')
            ) as next_steps__c,

        from {{ ref("stg_kippadb__contact_note") }} as n
        left join {{ ref("int_kippadb__roster") }} as ktc on n.contact = ktc.contact_id
        where
            n.academic_year >= 2025
            -- this record is not accesible to fix on SF neither by UI nor via data
            -- loader
            and n.id != 'a0LQg00000SOadzMAD'
            and ktc.contact_advising_provider is null
    ),

    dups as (
        select
            contact__c,
            subject__c,
            comments__c,
            next_steps__c,
            date__c,
            status__c,
            type__c,

            count(distinct id) as rows_total,

        from salesforce_notes
        group by all
        having count(distinct id) > 1
    ),

    row_counting as (
        select
            s.*,
            d.rows_total,

            row_number() over (
                partition by s.contact__c, s.comments__c order by s.name
            ) as order_rows,

        from salesforce_notes as s
        left join
            dups as d
            on s.contact__c = d.contact__c
            and s.subject__c = d.subject__c
            and s.comments__c = d.comments__c
        where d.rows_total is not null
    )

select
    id,
    name,
    contact__c,
    subject__c,
    comments__c,
    next_steps__c,
    date__c,
    status__c,
    type__c,
from row_counting
where order_rows != 1
