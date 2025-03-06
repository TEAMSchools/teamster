with
    psat as (
        select
            cb_id,
            latest_psat_total,
            latest_psat_math_section,
            latest_psat_ebrw,
            latest_psat_reading,
            gender,

            safe_cast(birth_date as date) as birth_date,

            safe_cast(latest_psat_math_test as integer) as latest_psat_math_test,

            safe_cast(latest_psat_date as date) as latest_psat_date,

            coalesce(
                district_student_id.long_value,
                cast(district_student_id.double_value as int)
            ) as district_student_id,

            coalesce(
                secondary_id.long_value, cast(secondary_id.double_value as int)
            ) as secondary_id,

            coalesce(
                latest_psat_grade.long_value,
                cast(latest_psat_grade.double_value as int)
            ) as latest_psat_grade,

            if(
                _dagster_partition_key = 'PSATNM',
                'psatnmsqt',
                lower(_dagster_partition_key)
            ) as test_name,

            case
                _dagster_partition_key
                when 'PSATNM'
                then 'PSAT NMSQT'
                when 'PSAT89'
                then 'PSAT 8/9'
                when 'PSAT10'
                then 'PSAT10'
            end as test_type,
        from {{ source("collegeboard", "src_collegeboard__psat") }}
    )

select
    *,

    concat(
        format_date('%b', latest_psat_date), ' ', format_date('%g', latest_psat_date)
    ) as administration_round,

    {{
        date_to_fiscal_year(
            date_field="latest_psat_date", start_month=7, year_source="start"
        )
    }} as academic_year,
from psat
