with
    -- trunk-ignore(sqlfluff/ST03)
    person_data as (
        select
            _dagster_partition_key as academic_year,
            application_academic_school_year,
            application_approved_benefit_type,
            eligibility_benefit_type,
            eligibility_determination_reason,
            eligibility,

            cast(is_directly_certified as boolean) as is_directly_certified,

            cast(person_identifier as int) as person_identifier,

            cast(
                regexp_replace(total_balance, r'[,$]', '') as numeric
            ) as total_balance,
            cast(
                regexp_replace(total_negative_balance, r'[,$]', '') as numeric
            ) as total_negative_balance,
            cast(
                regexp_replace(total_positive_balance, r'[,$]', '') as numeric
            ) as total_positive_balance,

            parse_date('%m/%d/%Y', eligibility_start_date) as eligibility_start_date,
            parse_date('%m/%d/%Y', eligibility_end_date) as eligibility_end_date,
        from {{ source("titan", "src_titan__person_data") }}
    ),

    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="person_data",
                partition_by="person_identifier, academic_year",
                order_by="eligibility_end_date desc",
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select
    *,

    case
        eligibility
        when '1'
        then 'F'
        when '2'
        then 'R'
        when '3'
        then 'P'
        else left(eligibility, 1)
    end as eligibility_name,
from deduplicate
