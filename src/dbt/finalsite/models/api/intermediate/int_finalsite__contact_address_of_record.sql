with
    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    candidate_households as (
        -- Any household carrying a street line is a candidate. Completeness is
        -- deliberately NOT a gate: an incomplete address is visibly wrong in
        -- Focus and can be corrected there, whereas withholding it is silent.
        -- Households with no street at all ARE excluded — Miami holds 94 such
        -- city/state/ZIP fragments, and each would otherwise count as its own
        -- candidate and manufacture ambiguity that is not real.
        select
            finalsite_enrollment_id,
            household_id,
            address_1,
            address_2,
            city,
            state,
            zip,
            country,
            is_complete_address,
        from {{ ref("int_finalsite__contacts__households") }}
        where address_1 is not null
    ),

    address_candidates as (
        -- One row per (contact, distinct address). Address identity is an
        -- exact match on the five mailing fields — no case-folding, no
        -- punctuation-stripping, no ZIP+4 truncation. Two spellings of the
        -- same address (`123 Main St.` vs `123 MAIN ST`) therefore stay
        -- distinct candidates, and the contact is withheld as ambiguous rather
        -- than guessed at. country and is_complete_address are not part of the
        -- identity, so they come from the canonical lowest-household_id row
        -- rather than being aggregated across rows, which would blend values
        -- from different households.
        {{
            dbt_utils.deduplicate(
                relation="candidate_households",
                partition_by=(
                    "finalsite_enrollment_id, address_1, address_2, city,"
                    " state, zip"
                ),
                order_by="household_id asc",
            )
        }}
    ),

    candidate_counts as (
        select finalsite_enrollment_id, count(*) as candidate_count,
        from address_candidates
        group by finalsite_enrollment_id
    ),

    resolved_candidates as (
        -- Only a contact with exactly one distinct address gets an address at
        -- all. Two or more means Finalsite does not say which one to use, and
        -- the feed is import-once, so a guess would be permanent.
        select
            a.finalsite_enrollment_id,
            a.address_1,
            a.address_2,
            a.city,
            a.state,
            a.zip,
            a.country,
            a.is_complete_address,
        from address_candidates as a
        inner join
            candidate_counts as c
            on a.finalsite_enrollment_id = c.finalsite_enrollment_id
        where c.candidate_count = 1
    ),

    counted as (
        -- Spined on the full contact list so a contact with no street-bearing
        -- household still gets a row, with candidate_count 0.
        select
            c.finalsite_enrollment_id,

            r.address_1,
            r.address_2,
            r.city,
            r.state,
            r.zip,
            r.country,
            r.is_complete_address,
            r.finalsite_enrollment_id as resolved_contact_id,

            coalesce(cc.candidate_count, 0) as candidate_count,
        from {{ ref("stg_finalsite__contacts") }} as c
        left join
            candidate_counts as cc
            on c.finalsite_enrollment_id = cc.finalsite_enrollment_id
        left join
            resolved_candidates as r
            on c.finalsite_enrollment_id = r.finalsite_enrollment_id
    )

select
    finalsite_enrollment_id,
    address_1,
    address_2,
    city,
    state,
    zip,
    country,
    is_complete_address,
    candidate_count,

    case
        when resolved_contact_id is not null
        then 'resolved'
        when candidate_count = 0
        then 'no_street'
        else 'ambiguous'
    end as resolution_status,
from counted
