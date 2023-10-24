with
    income_form_data as (  -- noqa: ST03
        select
            reference_code,
            student_identifier,
            _dagster_partition_key as academic_year,
            parse_date('%m/%d/%Y', date_signed) as date_signed,
            coalesce(
                safe_cast(eligibility_result.long_value as string),
                eligibility_result.string_value
            ) as eligibility_result,
        from {{ source("titan", "src_titan__income_form_data") }}
    ),

    deduplicate as (
        -- noqa: disable=TMP
        {{
            dbt_utils.deduplicate(
                relation="income_form_data",
                partition_by="student_identifier, academic_year",
                order_by="date_signed desc",
            )
        }}
    -- noqa: enable=TMP
    ),

    with_eligibility_name as (
        select
            reference_code,
            student_identifier,
            academic_year,
            date_signed,
            eligibility_result,
            case
                eligibility_result
                when '1'
                then 'F'
                when '2'
                then 'R'
                when '3'
                then 'P'
                when 'NJEIE'
                then 'P'
                else eligibility_result
            end as eligibility_name,
        from deduplicate
    )

select *, eligibility_result || ' - Income Form' as lunch_application_status,
from with_eligibility_name
