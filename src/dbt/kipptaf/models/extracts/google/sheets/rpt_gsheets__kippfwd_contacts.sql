with
    deanslist_notes as (
        select
            ktc.contact_id as contact__c,

            c.call_date as date__c,

            trim(
                regexp_replace(regexp_replace(c.topic, r'\r|\n', ' '), r'\s+', ' ')
            ) as comments__c,

            trim(
                regexp_replace(regexp_replace(c.response, r'\r|\n', ' '), r'\s+', ' ')
            ) as next_steps__c,

            if(c.call_status = 'Completed', 'Successful', 'Outreach') as status__c,

            -- do not use this for years prior to 2025
            case
                concat(cast(extract(month from c.call_date) as string), c.reason)
                when '8KF: AS'
                then 'AS1'
                when '9KF: AS'
                then 'AS1'
                when '10KF: AS'
                then 'AS2'
                when '11KF: AS'
                then 'AS3'
                when '12KF: AS'
                then 'AS4'
                when '1KF: AS'
                then 'AS5'
                when '2KF: AS'
                then 'AS6'
                when '3KF: AS'
                then 'AS7'
                when '4KF: AS'
                then 'AS8'
                when '5KF: AS'
                then 'AS9'
                when '6KF: AS'
                then 'AS10'
                when '7KF: AS'
                then 'AS11'
                else c.reason
            end as subject__c,

            case
                c.call_type
                when 'P'
                then 'Call'
                when 'VC'
                then 'Call'
                when 'IP'
                then 'In Person'
                when 'SMS'
                then 'Text'
                when 'E'
                then 'Email'
                when 'L'
                then 'Mail (Letter/Postcard)'
            end as type__c,

            {{
                date_to_fiscal_year(
                    date_field="call_date_time", start_month=7, year_source="start"
                )
            }} as academic_year,

        from {{ ref("int_kippadb__roster") }} as ktc
        inner join
            {{ ref("int_deanslist__comm_log") }} as c
            on ktc.student_number = c.student_school_id
            and regexp_contains(c.reason, r'^KF:')
        -- this record is not accesible to fix on SF neither by UI nor via data loader
        where record_id != 14846967
    ),

    salesforce_notes as (
        select
            id,
            contact as contact__c,
            `subject` as subject__c,
            `date` as date__c,
            `status` as status__c,
            `type` as type__c,
            academic_year,

            trim(
                regexp_replace(regexp_replace(comments, r'\r|\n', ' '), r'\s+', ' ')
            ) as comments__c,

            trim(
                regexp_replace(regexp_replace(next_steps, r'\r|\n', ' '), r'\s+', ' ')
            ) as next_steps__c,

        from {{ ref("stg_kippadb__contact_note") }}
        where
            academic_year = {{ var("current_academic_year") }}
            -- this record is not accesible to fix on SF neither by UI nor via data
            -- loader
            and id != 'a0LQg00000SOadzMAD'
    )

select
    d.contact__c,
    d.subject__c,
    d.comments__c,
    d.next_steps__c,
    d.date__c,
    d.status__c,
    d.type__c,

from deanslist_notes as d
left join
    salesforce_notes as s
    on d.contact__c = s.contact__c
    and d.subject__c = s.subject__c
    and d.comments__c = s.comments__c
    and d.next_steps__c = s.next_steps__c
    and d.date__c = s.date__c
    and d.status__c = s.status__c
    and d.type__c = s.type__c
where d.academic_year = {{ var("current_academic_year") }} and s.subject__c is null
