with
    person_data as (
        select
            person_identifier,
            application_academic_school_year,
            application_approved_benefit_type,
            eligibility_benefit_type,
            eligibility_determination_reason,
            is_directly_certified,
            total_balance.double_value as total_balance,
            total_positive_balance.double_value as total_positive_balance,
            total_negative_balance.double_value as total_negative_balance,
            _dagster_partition_key as academic_year,
            parse_date('%m/%d/%Y', eligibility_start_date) as eligibility_start_date,
            parse_date('%m/%d/%Y', eligibility_end_date) as eligibility_end_date,
            coalesce(
                eligibility.string_value, safe_cast(eligibility.long_value as string)
            ) as eligibility,
        from {{ source("titan", "src_titan__person_data") }}
    )

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
from person_data
