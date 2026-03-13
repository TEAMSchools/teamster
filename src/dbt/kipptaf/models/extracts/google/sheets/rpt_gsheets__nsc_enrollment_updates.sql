with
    nsc_enrollment_derived as (
        select
            contact_id,
            account_id,
            enrollment_begin,
            enrollment_end,
            current_enrollment_status,

            case
                when any_graduated
                then 'Graduated'
                when any_withdrawn
                then 'Withdrew'
                else 'Attending'
            end as derived_status,

        from {{ ref("int_nsc__enrollments") }}
    )

select
    e.id,
    n.enrollment_end as actual_end_date__c,
    n.derived_status as status__c,
    n.current_enrollment_status as attending_status__c,
    true as nsc_verified__c,
    current_date('{{ var("local_timezone") }}') as date_last_verified__c,

from nsc_enrollment_derived as n
inner join
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
where
    not e.do_not_overwrite_with_nsc_data
    and (
        n.enrollment_end is distinct from e.actual_end_date
        or n.derived_status is distinct from e.status
        or n.current_enrollment_status is distinct from e.attending_status
    )
qualify
    row_number() over (
        partition by e.id
        order by abs(date_diff(n.enrollment_begin, e.start_date, day))
    ) = 1
