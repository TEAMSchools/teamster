with
    custom_rows as (
        select
            academic_year,
            assessment_name,
            season,
            school_level,
            grade_range_band,
            discipline,
            aligned_test_code,
            region,
            comparison_entity,
            comparison_demographic_group,
            comparison_demographic_subgroup,
            percent_proficient,
            total_students,

        from
            {{
                source(
                    "google_sheets",
                    "src_google_sheets__state_test_comparison_demographics",
                )
            }}
        where remove_row is null

        union all

        -- HS-only ALG01 totals are not provided by official comp data sources
        select
            academic_year,
            assessment_name,
            season,
            grade_range_band as school_level,
            grade_range_band,
            discipline,
            aligned_test_code,
            region,
            comparison_entity,
            'Total' as comparison_demographic_group,
            'All Students' as comparison_demographic_subgroup,

            sum(percent_proficient) as percent_proficient,
            sum(total_students) as total_students,

        from
            {{
                source(
                    "google_sheets",
                    "src_google_sheets__state_test_comparison_demographics",
                )
            }}
        where remove_row and aligned_test_code = 'ALG01'
        group by
            academic_year,
            assessment_name,
            season,
            grade_range_band,
            discipline,
            aligned_test_code,
            region,
            comparison_entity
    )

select
    *,

    case
        when aligned_test_code = 'ALG01' and school_level != 'MS_HS'
        then concat(aligned_test_code, '_', school_level)
        else aligned_test_code
    end as aligned_level_test_code,

    if(
        comparison_demographic_subgroup in ('Grade - 08', 'Grade - 09', 'Grade - 10'),
        'Total',
        comparison_demographic_group
    ) as aligned_comparison_demographic_group,

    if(
        comparison_demographic_group = 'Grade',
        'All Students',
        comparison_demographic_subgroup
    ) as aligned_comparison_demographic_subgroup,

    round(percent_proficient * total_students, 0) as total_proficient_students,

from custom_rows
