with
    income_form_data as (
        select
            reference_code,
            student_identifier,
            parse_date('%m/%d/%Y', date_signed) as date_signed,
            coalesce(
                safe_cast(eligibility_result.long_value as string),
                eligibility_result.string_value
            ) as eligibility_result,
            safe_cast(split(academic_year, '/')[0] as int) as academic_year,
        from {{ source("titan", "src_titan__income_form_data") }}
    ),

    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="income_form_data",
                partition_by="student_identifier, academic_year",
                order_by="date_signed desc",
            )
        }}
    ),

    with_eligibility_name as (
        select
            *,
            case
                eligibility_result
                when '1'
                then 'F'
                when '2'
                then 'R'
                when '3'
                then 'P'
                else eligibility_result
            end as eligibility_name,
        from deduplicate
    )

select *, eligibility_name || ' - Income Form' as lunch_application_status,
from with_eligibility_name
