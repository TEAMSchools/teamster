with
    nsc_with_account as (
        select
            n.contact_id,
            n.enrollment_begin,
            n.enrollment_end,
            n.enrollment_status,
            n.graduated,
            n.graduation_date,
            n.two_year_four_year,
            n.search_date,

            x.account_id,
        from {{ ref("stg_nsc__student_tracker") }} as n
        inner join
            {{ ref("stg_google_sheets__kippadb__nsc_crosswalk") }} as x
            on n.college_code_branch = x.college_code_nsc
            and x.rn_college_code_nsc = 1
        where n.record_found_y_n = 'Y'
    ),

    /* NSC reports the same term across successive search_date pulls; keep
       the most recently confirmed copy of each (contact, school, term). */
    nsc_terms_deduped as (
        {{
            dbt_utils.deduplicate(
                relation="nsc_with_account",
                partition_by="contact_id, account_id, enrollment_begin",
                order_by="search_date desc",
            )
        }}
    ),

    nsc_terms_with_gap as (
        select
            contact_id,
            account_id,
            enrollment_begin,
            enrollment_end,
            enrollment_status,
            two_year_four_year,

            date_diff(
                enrollment_begin,
                lag(enrollment_end) over (
                    partition by contact_id, account_id order by enrollment_begin
                ),
                month
            ) as gap_months,
        from nsc_terms_deduped
        where enrollment_begin is not null
    ),

    /* A new stint begins on the first row per (contact, school) and any time
       the gap from the previous term's end to the current term's begin
       exceeds 6 months (summer breaks bridge; a gap year does not). */
    nsc_term_stints as (
        select
            contact_id,
            account_id,
            enrollment_begin,
            enrollment_end,
            enrollment_status,
            two_year_four_year,

            countif(gap_months is null or gap_months > 6) over (
                partition by contact_id, account_id
                order by enrollment_begin
                rows between unbounded preceding and current row
            ) as stint_num,
        from nsc_terms_with_gap
    ),

    /* Pick the most recent term per stint to source 'current' status fields. */
    stint_latest_term_raw as (
        {{
            dbt_utils.deduplicate(
                relation="nsc_term_stints",
                partition_by="contact_id, account_id, stint_num",
                order_by="enrollment_begin desc",
            )
        }}
    ),

    stint_latest_term as (
        select
            contact_id,
            account_id,
            stint_num,
            enrollment_status as current_enrollment_status,
            two_year_four_year as current_two_year_four_year,
        from stint_latest_term_raw
    ),

    stint_aggregates as (
        select
            contact_id,
            account_id,
            stint_num,

            min(enrollment_begin) as stint_begin,
            max(enrollment_end) as stint_end,

            countif(enrollment_status = 'W') > 0 as any_withdrawn,
        from nsc_term_stints
        group by contact_id, account_id, stint_num
    ),

    /* NSC graduation rows have NULL term dates but carry a graduation_date.
       Attribute graduation to the stint whose date range contains
       graduation_date; if no stint contains it (e.g. graduation pre-dates the
       NSC-tracked terms), fall back to the latest stint at that school. */
    graduation_per_school as (
        select contact_id, account_id, max(graduation_date) as graduation_date,
        from nsc_with_account
        where graduated = 'Y'
        group by contact_id, account_id
    ),

    stint_graduation_match as (
        select
            a.contact_id,
            a.account_id,
            a.stint_num,
            a.stint_begin,
            a.stint_end,
            a.any_withdrawn,

            g.graduation_date,

            g.graduation_date
            between a.stint_begin and a.stint_end as graduation_in_stint,
            a.stint_num = max(a.stint_num) over (
                partition by a.contact_id, a.account_id
            ) as is_latest_stint,
        from stint_aggregates as a
        left join
            graduation_per_school as g
            on a.contact_id = g.contact_id
            and a.account_id = g.account_id
    ),

    stint_with_grad_flag as (
        select
            contact_id,
            account_id,
            stint_num,
            stint_begin,
            stint_end,
            any_withdrawn,

            case
                when graduation_date is null
                then false
                when
                    sum(if(graduation_in_stint, 1, 0)) over (
                        partition by contact_id, account_id
                    )
                    > 0
                then graduation_in_stint
                else is_latest_stint
            end as any_graduated,
        from stint_graduation_match
    )

select
    a.contact_id,
    a.account_id,
    a.stint_num,
    a.stint_begin,
    a.stint_end,
    a.any_withdrawn,
    l.current_enrollment_status,
    l.current_two_year_four_year,

    a.any_graduated,

    case
        when a.any_graduated
        then 'Graduated'
        when a.any_withdrawn
        then 'Withdrew'
        else 'Attending'
    end as derived_status,
from stint_with_grad_flag as a
inner join
    stint_latest_term as l
    on a.contact_id = l.contact_id
    and a.account_id = l.account_id
    and a.stint_num = l.stint_num
