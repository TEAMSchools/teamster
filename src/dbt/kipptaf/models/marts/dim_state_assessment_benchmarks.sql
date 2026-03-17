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
        case when comparison_entity = 'Neighborhood Schools' then percent_proficient end
    ) as neighborhood_schools_percent_proficient,

    max(
        case when comparison_entity = 'City' then total_students end
    ) as city_total_students,
    max(
        case when comparison_entity = 'State' then total_students end
    ) as state_total_students,
    max(
        case when comparison_entity = 'Neighborhood Schools' then total_students end
    ) as neighborhood_schools_total_students,

    {{
        dbt_utils.generate_surrogate_key(
            ["academic_year", "test_name", "test_code", "region"]
        )
    }} as state_assessment_benchmarks_key,

from {{ ref("stg_google_sheets__state_test_comparison") }}
group by academic_year, test_name, test_code, region
