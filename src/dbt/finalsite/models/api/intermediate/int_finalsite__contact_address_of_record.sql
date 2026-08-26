with
    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    candidate_households as (
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
        {{
            dbt_utils.deduplicate(
                relation="address_candidates",
                partition_by="finalsite_enrollment_id",
                order_by="is_complete_address desc, household_id asc",
            )
        }}
    ),

    counted as (
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
