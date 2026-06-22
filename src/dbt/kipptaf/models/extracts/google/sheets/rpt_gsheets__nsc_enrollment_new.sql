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
    ),

    /* Two independent credential signals per stint, combined in the final
       SELECT via coalesce. Kept separate so each branch is a flat lookup:
         credential_from_class_level — NSC's reported credential, when the
           class_level code is explicit (A, B, C, N, M, D, L, P, G). See
           int_nsc__enrollment_stints.current_class_level for code meanings.
         credential_from_institution — fallback for year-in-school codes
           (F, S, J, R) and NULL class_level, derived from the Salesforce
           Account.type ("Public 2 yr", "Private 4 yr", etc.). */
    stints_with_credentials as (
        select
            n.contact_id,
            n.account_id,
            n.stint_num,
            n.stint_begin,
            n.stint_end,
            n.current_enrollment_status,
            n.current_class_level,
            n.derived_status,

            a.`name` as school_name,

            case
                n.current_class_level
                when 'A'
                then "Associate's (2 year)"
                when 'B'
                then "Bachelor's (4-year)"
                when 'C'
                then 'Certificate'
                when 'N'
                then 'Course Credit (Non-Degree Seeking)'
                when 'M'
                then "Master's"
                when 'D'
                then 'Graduate Degree'
                when 'L'
                then 'Graduate Degree'
                when 'P'
                then 'Graduate Degree'
                when 'G'
                then 'Graduate Degree'
            end as credential_from_class_level,
            case
                when a.type like '%2 yr%'
                then "Associate's (2 year)"
                when a.type like '%4 yr%'
                then "Bachelor's (4-year)"
            end as credential_from_institution,
        from {{ ref("int_nsc__enrollment_stints") }} as n
        left join {{ ref("stg_kippadb__account") }} as a on n.account_id = a.id
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

    /* Precedence: NSC's explicit class_level credential first, then
       institution-type fallback for year-in-school codes (F/S/J/R) and NULL
       class_level. NULL out means no signal at all (rare; intern reviews
       and infers). Specific degree titles (MBA, JD, etc.) are not resolved
       here — NSC only emits degree_title on its graduation-summary row,
       which is not the term row that current_class_level is sourced from. */
    coalesce(
        n.credential_from_class_level, n.credential_from_institution
    ) as pursuing_degree_type__c,

    /* Audit-only helper columns — delete before Salesforce upload. */
    r.lastfirst as alum_name,
    r.contact_advising_provider,
    r.ktc_status,
    n.school_name,
from stints_with_credentials as n
left join
    covered_stints as c
    on n.contact_id = c.contact_id
    and n.account_id = c.account_id
    and n.stint_num = c.stint_num
left join {{ ref("int_kippadb__roster") }} as r on n.contact_id = r.contact_id
where c.contact_id is null
