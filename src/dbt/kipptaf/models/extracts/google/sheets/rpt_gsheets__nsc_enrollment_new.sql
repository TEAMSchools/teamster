with
    /* Anti-join against existing enrollments via date-range overlap.
       An existing enrollment "covers" a stint iff they share student + school
       AND their date windows overlap. Open-ended endpoints on either side
       use 9999-12-31 (NSC term rows may carry a NULL enrollment_end for
       in-progress terms, propagating to stint_end). */
    -- grain projection: every selected column is functionally determined
    -- by the partition key; not a mask for upstream duplicates
    covered_stints as (
        select distinct n.contact_id, n.account_id, n.stint_num,
        from {{ ref("int_nsc__enrollment_stints") }} as n
        inner join
            {{ ref("stg_kippadb__enrollment") }} as e
            on n.contact_id = e.student
            and n.account_id = e.school
            and n.stint_begin <= coalesce(e.actual_end_date, date(9999, 12, 31))
            and coalesce(n.stint_end, date(9999, 12, 31)) >= e.`start_date`
    )

/* Audit helpers (alum_name, school_name) intentionally last so the upload
   columns sit contiguously on the left of the sheet. */
-- trunk-ignore(sqlfluff/ST06): audit helpers placed last for sheet-deletion
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

    /* Audit-only helper columns — delete before Salesforce upload. */
    r.lastfirst as alum_name,
    r.contact_advising_provider,
    r.ktc_status,
    a.`name` as school_name,
from {{ ref("int_nsc__enrollment_stints") }} as n
left join
    covered_stints as c
    on n.contact_id = c.contact_id
    and n.account_id = c.account_id
    and n.stint_num = c.stint_num
left join {{ ref("int_kippadb__roster") }} as r on n.contact_id = r.contact_id
left join {{ ref("stg_kippadb__account") }} as a on n.account_id = a.id
where c.contact_id is null
