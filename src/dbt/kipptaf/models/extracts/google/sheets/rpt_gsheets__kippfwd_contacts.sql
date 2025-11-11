with
    deanslist_notes as (
        select
            ktc.contact_id,

            c.call_date,

            if(c.call_status = 'Completed', 'Successful', 'Outreach') as `status`,

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
            end as `subject`,

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
            end as `type`,

            {{ parse_html("c.topic") }} as topic,
            {{ parse_html("c.response") }} as response,

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
        /* record not fixable on SF by either UI or data loader */
        where c.record_id != 14846967
    ),

    salesforce_notes as (
        select
            id,
            contact,
            `subject`,
            `date`,
            `status`,
            `type`,

            {{ parse_html("comments") }} as comments,
            {{ parse_html("next_steps") }} as next_steps,

        from {{ ref("stg_kippadb__contact_note") }}
        where
            academic_year = {{ var("current_academic_year") }}
            /* record not fixable on SF by either UI or data loader */
            and id != 'a0LQg00000SOadzMAD'
    )

select
    d.contact_id as contact__c,
    d.subject as subject__c,
    d.call_date as date__c,
    d.status as status__c,
    d.type as type__c,
    d.topic as comments__c,
    d.response as next_steps__c,
from deanslist_notes as d
left join
    salesforce_notes as s
    on d.contact_id = s.contact
    and d.subject = s.subject
    and d.topic = s.comments
    and d.response = s.next_steps
    and d.call_date = s.date
    and d.status = s.status
    and d.type = s.type
where d.academic_year = {{ var("current_academic_year") }} and s.subject is null
