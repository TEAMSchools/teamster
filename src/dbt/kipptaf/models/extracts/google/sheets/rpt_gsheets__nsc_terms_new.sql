with
    nsc_with_account as (
        select
            n.contact_id,
            n.enrollment_begin,
            n.enrollment_end,
            n.enrollment_status,
            n.graduated,
            n.two_year_four_year,

            x.account_id,

            /* deduplicate in case NSC sends multiple rows for the same semester */
            row_number() over (
                partition by n.contact_id, x.account_id, n.enrollment_begin
                order by n.search_date desc
            ) as rn_semester,

        from {{ ref("stg_nsc__student_tracker") }} as n
        inner join
            {{ ref("stg_google_sheets__kippadb__nsc_crosswalk") }} as x
            on n.college_code_branch = x.college_code_nsc
            and x.rn_college_code_nsc = 1
        where n.record_found_y_n = 'Y'
    ),

    nsc_semesters as (
        select
            contact_id,
            account_id,
            enrollment_begin,
            enrollment_end,
            enrollment_status,
            graduated,
            two_year_four_year,
        from nsc_with_account
        where rn_semester = 1
    )

select
    e.id as enrollment__c,
    n.enrollment_begin as term_start_date__c,
    n.enrollment_end as term_end_date__c,
    n.enrollment_status as term_enrollment_status__c,
    n.enrollment_status as term_attending_status__c,

    case
        when extract(month from n.enrollment_begin) between 8 and 12 then 'Fall'
        when extract(month from n.enrollment_begin) between 1 and 5 then 'Spring'
        else 'Summer'
    end as term_season__c,

    {{
        date_to_fiscal_year(
            date_field="n.enrollment_begin", start_month=7, year_source="start"
        )
    }} as year__c,

    true as verified_by_nsc__c,

from nsc_semesters as n
inner join
    {{ ref("stg_kippadb__enrollment") }} as e
    on n.contact_id = e.student
    and n.account_id = e.school
    /* enrollment_begin must fall within the enrollment's active date range */
    and n.enrollment_begin
    between e.start_date and coalesce(e.actual_end_date, date(9999, 12, 31))
left join
    {{ ref("stg_kippadb__term") }} as t
    on e.id = t.enrollment
    and n.enrollment_begin = t.term_start_date
where t.id is null
