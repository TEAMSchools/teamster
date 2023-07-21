select
    person_identifier,
    application_academic_school_year,
    application_approved_benefit_type,
    eligibility.long_value as eligibility,
    eligibility_benefit_type,
    eligibility_determination_reason,
    is_directly_certified,
    total_balance.double_value as total_balance,
    total_positive_balance.double_value as total_positive_balance,
    total_negative_balance.double_value as total_negative_balance,
    parse_date('%m/%d/%Y', eligibility_start_date) as eligibility_start_date,
    parse_date('%m/%d/%Y', eligibility_end_date) as eligibility_end_date,
    safe_cast(split(application_academic_school_year, '/')[0] as int) as academic_year,
    case
        eligibility.long_value
        when 1
        then 'F'
        when 2
        then 'R'
        when 3
        then 'P'
        else safe_cast(eligibility.long_value as string)
    end as eligibility_name,
from {{ source("titan", "src_titan__person_data") }}
