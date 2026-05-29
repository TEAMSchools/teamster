with
    /* Anti-join against existing enrollments via date-range overlap.
       An existing enrollment "covers" a stint iff they share student + school
       AND their date windows overlap (stint_begin <= existing_end AND
       stint_end >= existing_start). Open-ended existing enrollments use
       9999-12-31 as the implicit end. */
    covered_stints as (
        select distinct n.contact_id, n.account_id, n.stint_num,
        from {{ ref("int_nsc__enrollment_stints") }} as n
        inner join
            {{ ref("stg_kippadb__enrollment") }} as e
            on n.contact_id = e.student
            and n.account_id = e.school
            and n.stint_begin <= coalesce(e.actual_end_date, date(9999, 12, 31))
            and n.stint_end >= e.`start_date`
    )

select
    n.contact_id as student__c,
    n.account_id as school__c,
    n.stint_begin as start_date__c,
    n.stint_end as actual_end_date__c,
    n.current_enrollment_status as attending_status__c,
    n.derived_status as status__c,

    'NSC' as source__c,
    true as created_for_nsc_data__c,
    true as nsc_verified__c,

    case
        n.current_two_year_four_year
        when '4-year'
        then "Bachelor's (4-year)"
        when '2-year'
        then "Associate's (2 year)"
    end as pursuing_degree_type__c,
from {{ ref("int_nsc__enrollment_stints") }} as n
left join
    covered_stints as c
    on n.contact_id = c.contact_id
    and n.account_id = c.account_id
    and n.stint_num = c.stint_num
where c.contact_id is null
