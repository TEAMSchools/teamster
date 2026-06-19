with
    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    nsc_with_account as (
        select
            n.contact_id,
            n.enrollment_begin,
            n.enrollment_end,
            n.enrollment_status,
            n.search_date,

            x.account_id,
        from {{ ref("stg_nsc__student_tracker") }} as n
        inner join
            {{ ref("stg_google_sheets__kippadb__nsc_crosswalk") }} as x
            on n.college_code_branch = x.college_code_nsc
            and x.rn_college_code_nsc = 1
        where n.record_found_y_n = 'Y' and n.enrollment_begin is not null
    ),

    /* NSC repeats the same term across successive search_date pulls. */
    nsc_terms_deduped as (
        {{
            dbt_utils.deduplicate(
                relation="nsc_with_account",
                partition_by="contact_id, account_id, enrollment_begin",
                order_by="search_date desc",
            )
        }}
    ),

    /* Term -> parent enrollment via date overlap. When multiple existing
       enrollments overlap one NSC term (split stints), pick the parent with
       the latest start_date (the most recent active enrollment at term
       start). */
    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    term_enrollment_match as (
        select
            n.contact_id,
            n.account_id,
            n.enrollment_begin,
            n.enrollment_end,
            n.enrollment_status,

            e.id as enrollment_id,
            e.`start_date` as enrollment_start_date,
        from nsc_terms_deduped as n
        inner join
            {{ ref("stg_kippadb__enrollment") }} as e
            on n.contact_id = e.student
            and n.account_id = e.school
            /* Half-open: prevents a term on the shared boundary date of
               consecutive Salesforce enrollments from matching both. */
            and n.enrollment_begin >= e.`start_date`
            and n.enrollment_begin < coalesce(e.actual_end_date, date(9999, 12, 31))
    ),

    term_with_parent as (
        {{
            dbt_utils.deduplicate(
                relation="term_enrollment_match",
                partition_by="contact_id, account_id, enrollment_begin",
                order_by="enrollment_start_date desc, enrollment_id",
            )
        }}
    )

select
    n.enrollment_id as enrollment__c,
    n.enrollment_begin as term_start_date__c,
    n.enrollment_end as term_end_date__c,
    /* NSC term data has a single status field; Salesforce stores it in both */
    n.enrollment_status as term_enrollment_status__c,
    n.enrollment_status as term_attending_status__c,

    true as verified_by_nsc__c,

    case
        when extract(month from n.enrollment_begin) between 8 and 12
        then 'Fall'
        when extract(month from n.enrollment_begin) between 1 and 5
        then 'Spring'
        else 'Summer'
    end as term_season__c,

    {{
        date_to_fiscal_year(
            date_field="n.enrollment_begin", start_month=7, year_source="start"
        )
    }} as year__c,

    /* Audit-only helper columns — delete before Salesforce upload. */
    r.lastfirst as alum_name,
    a.`name` as school_name,
from term_with_parent as n
left join
    {{ ref("stg_kippadb__term") }} as t
    on n.enrollment_id = t.enrollment
    and n.enrollment_begin = t.term_start_date
left join {{ ref("int_kippadb__roster") }} as r on n.contact_id = r.contact_id
left join {{ ref("stg_kippadb__account") }} as a on n.account_id = a.id
where t.id is null
