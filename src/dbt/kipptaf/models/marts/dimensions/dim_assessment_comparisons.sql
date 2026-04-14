with
    comparisons as (
        select
            academic_year,
            test_name,
            test_code,
            region,

            max(
                case when comparison_entity = 'City' then percent_proficient end
            ) as city_percent_proficient,
            max(
                case when comparison_entity = 'State' then percent_proficient end
            ) as state_percent_proficient,
            max(
                case
                    when comparison_entity = 'Neighborhood Schools'
                    then percent_proficient
                end
            ) as neighborhood_schools_percent_proficient,

            max(
                case when comparison_entity = 'City' then total_students end
            ) as city_total_students,
            max(
                case when comparison_entity = 'State' then total_students end
            ) as state_total_students,
            max(
                case
                    when comparison_entity = 'Neighborhood Schools' then total_students
                end
            ) as neighborhood_schools_total_students,
        from {{ ref("stg_google_sheets__state_test_comparison") }}
        group by academic_year, test_name, test_code, region
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            ["academic_year", "test_name", "test_code", "region"]
        )
    }} as assessment_comparison_key,

    {{ dbt_utils.generate_surrogate_key(["region"]) }} as region_key,

    academic_year,
    test_name,
    test_code,
    region,
    city_percent_proficient,
    state_percent_proficient,
    neighborhood_schools_percent_proficient,
    city_total_students,
    state_total_students,
    neighborhood_schools_total_students,
from comparisons
