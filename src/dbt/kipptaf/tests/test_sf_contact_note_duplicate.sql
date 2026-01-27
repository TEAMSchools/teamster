{{
    config(
        severity="warn",
        store_failures=true,
        store_failures_as="view",
        meta={
            "dagster": {
                "ref": {"name": "stg_kippadb__contact_note"},
            },
        },
    )
}}

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

    dups as (
        select
            contact,
            `subject`,
            comments,
            next_steps,
            `date`,
            `status`,
            `type`,

            count(id) as rows_total,

        from salesforce_notes
        group by contact, `subject`, comments, next_steps, `date`, `status`, `type`
    ),

    row_counting as (
        select
            s.*,

            d.rows_total,

            row_number() over (
                partition by s.contact, s.comments order by s.name
            ) as order_rows,

        from salesforce_notes as s
        inner join
            dups as d
            on s.contact = d.contact
            and s.subject = d.subject
            and s.comments = d.comments
            and d.rows_total > 1
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
where order_rows > 1
