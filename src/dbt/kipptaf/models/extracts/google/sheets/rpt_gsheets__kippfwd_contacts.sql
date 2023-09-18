select
    ktc.contact_currently_enrolled_school as `Currently Enrolled School`,
    ktc.last_name as `Last Name`,
    ktc.first_name as `First Name`,
    ktc.contact_id as `Salesforce ID`,
    ktc.ktc_cohort as `HS Cohort`,

    format_date('%m/%d/%Y', s.dob) as `Birthdate`,

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
    null as `Current Category Ranking`
from {{ ref("int_kippadb__roster") }} as ktc
inner join
    {{ ref("stg_powerschool__students") }} as s on ktc.student_number = s.student_number
inner join
    {{ ref("stg_deanslist__comm_log") }} as c
    on c.student_school_id = ktc.student_number
    and regexp_contains(c.reason, r'^KF:')
