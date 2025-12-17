select
    *,

    'Spring' as season,

    case
        when comparison_demographic_subgroup = 'Grade - 08' and test_code = 'ALG01'
        then 'MS'
        when comparison_demographic_subgroup in ('Grade - 09', 'Grade - 10')
        then 'HS'
        when
            test_code in (
                'ELA09',
                'ELA10',
                'ELA11',
                'ELAGP',
                'ALG01',
                'GEO01',
                'ALG02',
                'MATGP',
                'SCI11'
            )
        then 'HS'
        when safe_cast(right(test_code, 2) as numeric) between 5 and 8
        then 'MS'
        else 'ES'
    end as school_level,

    case
        when comparison_demographic_subgroup in ('Grade - 09', 'Grade - 10')
        then 'HS'
        when
            test_code
            in ('ELA09', 'ELA10', 'ELA11', 'ELAGP', 'ALG02', 'GEO01', 'MATGP', 'SCI11')
        then 'HS'
        else '3-8'
    end as grade_range_band,

    case
        when left(test_code, 3) in ('MAT', 'ALG', 'GEO')
        then 'Math'
        when left(test_code, 3) = 'ELA'
        then 'ELA'
        when left(test_code, 3) = 'SCI'
        then 'Science'
        when left(test_code, 3) = 'SOC'
        then 'Social Studies'
    end as discipline,

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
