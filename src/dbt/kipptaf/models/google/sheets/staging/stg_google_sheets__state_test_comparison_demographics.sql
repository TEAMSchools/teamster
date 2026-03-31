select
    *,

    case
        when test_code = 'ALG01' and school_level != 'MS_HS'
        then concat(test_code, '_', school_level)
        else test_code
    end as aligned_level_test_code,

    if(
        comparison_demographic_subgroup in ('Grade - 08', 'Grade - 09', 'Grade - 10'),
        'Total',
        comparison_demographic_group
    ) as comparison_demographic_group_aligned,

    if(
        comparison_demographic_group = 'Grade',
        'All Students',
        comparison_demographic_subgroup
    ) as comparison_demographic_subgroup_aligned,

    round(percent_proficient * total_students, 0) as total_proficient_students,

from
    {{
        source(
            "google_sheets", "src_google_sheets__state_test_comparison_demographics"
        )
    }}
