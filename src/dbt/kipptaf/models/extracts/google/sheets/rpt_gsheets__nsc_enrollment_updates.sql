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

            extract(year from n.enrollment_begin) as enrollment_begin_year,

            row_number() over (
                partition by
                    n.contact_id, x.account_id, extract(year from n.enrollment_begin)
                order by n.enrollment_begin desc
            ) as rn_recent,

        from {{ ref("stg_nsc__student_tracker") }} as n
        inner join
            {{ ref("stg_google_sheets__kippadb__nsc_crosswalk") }} as x
            on n.college_code_branch = x.college_code_nsc
            and x.rn_college_code_nsc = 1
        where n.record_found_y_n = 'Y'
    ),

    nsc_enrollment as (
        select
            contact_id,
            account_id,
            enrollment_begin_year,

            min(enrollment_begin) as enrollment_begin,
            max(enrollment_end) as enrollment_end,

            /* any_graduated: if any NSC row for this enrollment shows graduation */
            countif(graduated = 'Y') > 0 as any_graduated,
            /* any_withdrawn: W is the NSC single-character code for Withdrawn */
            countif(enrollment_status = 'W') > 0 as any_withdrawn,

            max(
                if(rn_recent = 1, enrollment_status, null)
            ) as current_enrollment_status,

        from nsc_with_account
        group by contact_id, account_id, enrollment_begin_year
    ),

    nsc_enrollment_derived as (
        select
            contact_id,
            account_id,
            enrollment_begin_year,
            enrollment_end,
            current_enrollment_status,

            case
                when any_graduated
                then 'Graduated'
                when any_withdrawn
                then 'Withdrew'
                else 'Attending'
            end as derived_status,

        from nsc_enrollment
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
    and n.enrollment_begin_year = e.start_date_year
where
    not e.do_not_overwrite_with_nsc_data
    and (
        n.enrollment_end is distinct from e.actual_end_date
        or n.derived_status is distinct from e.status
        or n.current_enrollment_status is distinct from e.attending_status
    )
