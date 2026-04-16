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
            remove_row,

            if(
                comparison_demographic_group = 'Grade',
                'Total',
                comparison_demographic_group
            ) as comparison_demographic_group,

            if(
                comparison_demographic_subgroup = 'Grade - 08',
                'All Students',
                comparison_demographic_subgroup
            ) as comparison_demographic_subgroup,

            percent_proficient,
            total_students,

        from
            {{
                source(
                    "google_sheets",
                    "src_google_sheets__state_test_comparison_demographics",
                )
            }}
        where not remove_row

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
            remove_row,

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
        where remove_row and aligned_test_code = 'ALG01' and grade_range_band = 'HS'
        group by
            academic_year,
            assessment_name,
            season,
            grade_range_band,
            discipline,
            aligned_test_code,
            region,
            comparison_entity,
            remove_row
    )

select
    *,

    case
        when aligned_test_code = 'ALG01'
        then concat(aligned_test_code, '_', school_level)
        else aligned_test_code
    end as aligned_level_test_code,

    round(percent_proficient * total_students, 0) as total_proficient_students,

from custom_rows
