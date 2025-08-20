-- trunk-ignore(sqlfluff/ST06)
select
    -- trunk-ignore-begin(sqlfluff/RF05)
    ktc.contact_currently_enrolled_school as `Currently Enrolled School`,
    ktc.last_name as `Last Name`,
    ktc.first_name as `First Name`,
    ktc.contact_id as `Salesforce ID`,
    ktc.ktc_cohort as `HS Cohort`,

    format_date('%m/%d/%Y', ktc.dob) as `Birthdate`,

    c.reason as `Subject`,
    c.topic as `Comments`,
    c.response as `Next Steps`,
    c.record_id as dlcall_log_id,

    format_date('%m/%d/%Y', c.call_date_time) as `Contact Date`,

    if(c.call_status = 'Completed', 'Successful', 'Outreach') as `Status`,

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
    end as `Type`,

    null as `Category`,
    null as `Current Category Ranking`,
-- trunk-ignore-end(sqlfluff/RF05)
from {{ ref("int_kippadb__roster") }} as ktc
inner join
    {{ ref("int_deanslist__comm_log") }} as c
    on ktc.student_number = c.student_school_id
    and regexp_contains(c.reason, r'^KF:')
