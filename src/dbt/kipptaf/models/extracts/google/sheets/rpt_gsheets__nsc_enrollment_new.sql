select
    n.contact_id as student__c,
    n.account_id as school__c,
    n.enrollment_begin as start_date__c,
    n.enrollment_end as actual_end_date__c,
    n.current_enrollment_status as attending_status__c,

    'NSC' as source__c,
    true as created_for_nsc_data__c,
    true as nsc_verified__c,

    case
        when n.any_graduated
        then 'Graduated'
        when n.any_withdrawn
        then 'Withdrew'
        else 'Attending'
    end as status__c,

    case
        n.current_two_year_four_year
        when '4-year'
        then "Bachelor's (4-year)"
        when '2-year'
        then "Associate's (2 year)"
    end as pursuing_degree_type__c,
from {{ ref("int_nsc__enrollments") }} as n
left join
    {{ ref("stg_kippadb__enrollment") }} as e
    on n.contact_id = e.student
    and n.account_id = e.school
    /*
      Match on date proximity (±180 days) rather than calendar year to handle
      enrollments that span an academic year boundary (e.g. Fall+Spring).
    */
    and n.enrollment_begin
    between date_sub(e.start_date, interval 180 day) and date_add(
        e.start_date, interval 180 day
    )
where e.id is null
