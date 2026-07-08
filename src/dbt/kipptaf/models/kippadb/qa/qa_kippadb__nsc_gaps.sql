with
    roster as (
        select distinct
            contact_id,
            contact_graduation_year,
            contact_advising_provider,

            coalesce(
                contact_actual_hs_graduation_date, contact_expected_hs_graduation
            ) as hs_grad_date,
        from {{ ref("int_kippadb__roster") }}
        where
            contact_id is not null
            /* scope to actual HS graduates through class of current_academic_year
               + 1; without these guards the post-2022 advising-null branch sweeps
               in the current grade 8-12 roster, for whom an NSC postsecondary
               request is premature */
            and contact_actual_hs_graduation_date is not null
            and contact_graduation_year <= {{ var("current_academic_year") + 1 }}
            and (
                contact_graduation_year <= 2022
                or (
                    contact_graduation_year > 2022 and contact_advising_provider is null
                )
            )
    ),

    nsc_found as (
        select distinct contact_id,
        from {{ ref("stg_nsc__student_tracker") }}
        where record_found_y_n = 'Y'
    ),

    /* a term reaches its contact only through its enrollment; verified_by_nsc is
       a date (the NSC verification date), so non-null means NSC-verified */
    verified_terms as (
        select
            e.student as contact_id,

            max(
                coalesce(
                    t.term_end_date,
                    safe.parse_date('%Y%m%d', substr(t.nsc_enrollment_end, 1, 8))
                )
            ) as latest_verified_term_end,
        from {{ ref("stg_kippadb__term") }} as t
        inner join {{ ref("stg_kippadb__enrollment") }} as e on t.enrollment = e.id
        where t.verified_by_nsc is not null
        group by e.student
    ),

    completed as (
        select distinct contact_id,
        from {{ ref("int_nsc__enrollment_stints") }}
        where derived_status = 'Graduated'
    ),

    classified as (
        select
            r.contact_id,
            r.contact_graduation_year,
            r.contact_advising_provider,
            r.hs_grad_date,

            vt.latest_verified_term_end,

            cp.contact_id is not null as completed_college_flag,

            case
                when vt.contact_id is not null
                then 'forward_gap'
                when nf.contact_id is not null
                then 'unverified_only'
                else 'no_nsc_record'
            end as gap_type,
        from roster as r
        left join nsc_found as nf on r.contact_id = nf.contact_id
        left join verified_terms as vt on r.contact_id = vt.contact_id
        left join completed as cp on r.contact_id = cp.contact_id
    )

select
    contact_id,
    contact_graduation_year,
    contact_advising_provider,
    gap_type,
    completed_college_flag,

    if(
        gap_type = 'forward_gap',
        latest_verified_term_end
        < date_sub(current_date('{{ var("local_timezone") }}'), interval 6 month),
        cast(null as bool)
    ) as is_stale_6mo,

    if(
        gap_type = 'forward_gap',
        latest_verified_term_end < date({{ var("current_academic_year") }}, 7, 1),
        cast(null as bool)
    ) as is_stale_prior_ay,

    case
        when gap_type = 'forward_gap'
        then coalesce(latest_verified_term_end, hs_grad_date)
        else hs_grad_date
    end as suggested_search_from,
from classified
/* exclude forward_gap alumni still currently enrolled per the verified record;
   guard on is not null so a null end date falls through rather than being
   silently filtered by the null comparison */
where
    not (
        gap_type = 'forward_gap'
        and latest_verified_term_end is not null
        and latest_verified_term_end >= current_date('{{ var("local_timezone") }}')
    )
