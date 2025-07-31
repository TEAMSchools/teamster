with
    psat as (
        select
            name_first,
            name_mi,
            name_last,
            gender,

            cast(cb_id as int) as cb_id,
            cast(latest_psat_ebrw as int) as latest_psat_ebrw,
            cast(latest_psat_math_section as int) as latest_psat_math_section,
            cast(latest_psat_reading as int) as latest_psat_reading,
            cast(latest_psat_total as int) as latest_psat_total,

            cast(latest_psat_math_test as numeric) as latest_psat_math_test,

            cast(cast(district_student_id as numeric) as int) as district_student_id,
            cast(cast(latest_psat_grade as numeric) as int) as latest_psat_grade,
            cast(cast(secondary_id as numeric) as int) as secondary_id,

            cast(birth_date as date) as birth_date,
            cast(latest_psat_date as date) as latest_psat_date,

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
