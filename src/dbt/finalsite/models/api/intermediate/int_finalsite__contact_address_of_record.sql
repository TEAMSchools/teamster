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
        -- same address therefore stay distinct candidates and are counted
        -- separately, which is what makes candidate_count meaningful.
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

    picked_address as (
        -- The address of record is the BEST candidate, not the only one. A
        -- complete address beats an incomplete one; ties fall to the lowest
        -- household_id so the pick is stable between runs. Withholding was
        -- worse than choosing: a blank address in an import-once feed is
        -- permanent and silent, while a wrong one is visible and correctable
        -- in the receiving system.
        {{
            dbt_utils.deduplicate(
                relation="address_candidates",
                partition_by="finalsite_enrollment_id",
                order_by="is_complete_address desc, household_id asc",
            )
        }}
    ),

    counted as (
        -- Spined on the full contact list so a contact with no street-bearing
        -- household still gets a row, with candidate_count 0.
        select
            c.finalsite_enrollment_id,

            p.address_1,
            p.address_2,
            p.city,
            p.state,
            p.zip,
            p.country,
            p.is_complete_address,

            coalesce(cc.candidate_count, 0) as candidate_count,
        from {{ ref("stg_finalsite__contacts") }} as c
        left join
            candidate_counts as cc
            on c.finalsite_enrollment_id = cc.finalsite_enrollment_id
        left join
            picked_address as p on c.finalsite_enrollment_id = p.finalsite_enrollment_id
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
        when candidate_count = 0
        then 'no_street'
        when candidate_count = 1
        then 'resolved'
        else 'picked'
    end as resolution_status,
from counted
