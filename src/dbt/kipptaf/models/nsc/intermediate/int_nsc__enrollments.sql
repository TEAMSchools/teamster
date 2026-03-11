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
    ),

    semesters_with_lag as (
        select
            contact_id,
            account_id,
            enrollment_begin,
            enrollment_end,
            enrollment_status,
            graduated,
            two_year_four_year,

            lag(enrollment_end) over (
                partition by contact_id, account_id order by enrollment_begin
            ) as prev_enrollment_end,
        from nsc_semesters
    ),

    enrollment_groups as (
        select
            contact_id,
            account_id,
            enrollment_begin,
            enrollment_end,
            enrollment_status,
            graduated,
            two_year_four_year,

            /*
              A gap > 200 days between the prior semester's end and this
              semester's begin signals a new enrollment period.
              Summer break ≈ 90 days; a missing semester ≈ 270 days.
            */
            sum(
                case
                    when prev_enrollment_end is null
                    then 1
                    when
                        date_diff(enrollment_begin, prev_enrollment_end, day)
                        > 200
                    then 1
                    else 0
                end
            ) over (
                partition by contact_id, account_id
                order by enrollment_begin
                rows between unbounded preceding and current row
            ) as enrollment_group,
        from semesters_with_lag
    )

select
    contact_id,
    account_id,
    enrollment_group,

    min(enrollment_begin) as enrollment_begin,
    max(enrollment_end) as enrollment_end,

    countif(graduated = 'Y') > 0 as any_graduated,
    countif(enrollment_status = 'W') > 0 as any_withdrawn,

    /* most recent semester's status fields */
    array_agg(
        enrollment_status order by enrollment_begin desc limit 1
    )[offset(0)] as current_enrollment_status,
    array_agg(
        two_year_four_year order by enrollment_begin desc limit 1
    )[offset(0)] as current_two_year_four_year,

from enrollment_groups
group by contact_id, account_id, enrollment_group
