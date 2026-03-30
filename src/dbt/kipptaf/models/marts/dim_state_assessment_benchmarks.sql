select
    academic_year,
    test_name,
    season,
    school_level,
    grade_range_band,
    discipline,
    test_code,
    region,
    comparison_demographic_group_aligned,
    comparison_demographic_subgroup_aligned,

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

    max(
        case when comparison_entity = 'City' then total_proficient_students end
    ) as city_total_proficient_students,
    max(
        case when comparison_entity = 'State' then total_proficient_students end
    ) as state_total_proficient_students,
    max(
        case
            when comparison_entity = 'Neighborhood Schools'
            then total_proficient_students
        end
    ) as neighborhood_schools_total_proficient_students,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "academic_year",
                "test_name",
                "test_code",
                "region",
                "school_level",
                "grade_range_band",
                "season",
                "comparison_demographic_group_aligned",
                "comparison_demographic_subgroup_aligned",
            ]
        )
    }} as state_assessment_benchmarks_key,

from {{ ref("stg_google_sheets__state_test_comparison_demographics") }}
group by
    academic_year,
    test_name,
    season,
    school_level,
    grade_range_band,
    discipline,
    test_code,
    region,
    comparison_demographic_group_aligned,
    comparison_demographic_subgroup_aligned
