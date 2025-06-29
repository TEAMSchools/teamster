with
    ktaf as (
        select
            b.academic_year,
            b.assessment_name,
            b.test_code,
            b.total_proficient_students,
            b.total_students,
            b.percent_proficient,
            b.focus_level,

            if(b.region is null, regions, b.region) as region,

            case
                when b.region is null
                then 'Total'
                when b.focus_level in ('ml_status', 'iep_status', 'lunch_status,')
                then 'Subgroup'
                else initcap(regexp_replace(b.focus_level, r'_', ' '))
            end as comparison_demographic_group,

            case
                when b.region is null and b.focus_level = 'all_null'
                then 'All Students'
                else
                    coalesce(
                        b.gender,
                        b.aggregate_ethnicity,
                        b.lunch_status,
                        b.ml_status,
                        b.iep_status
                    )
            end as comparison_demographic_subgroup,

            if(b.region is null, b.district_state, 'Region') as comparison_entity,

        from {{ ref("int_tableau__state_assessments_demographic_comps_cubed") }} as b
        cross join unnest(['Camden', 'Newark']) as regions
        where
            b.academic_year is not null
            and b.assessment_name is not null
            and b.test_code is not null
            and b.district_state = 'KTAF NJ'

        union all

        select
            academic_year,
            assessment_name,
            test_code,
            total_proficient_students,
            total_students,
            percent_proficient,
            focus_level,

            coalesce(region, 'Miami') as region,

            case
                when focus_level in ('ml_status', 'iep_status', 'lunch_status')
                then 'Subgroup'
                when region is null and focus_level = 'all_null'
                then 'Total'
                else initcap(regexp_replace(focus_level, r'_', ' '))
            end as comparison_demographic_group,

            case
                when region is null and focus_level = 'all_null'
                then 'All Students'
                else
                    coalesce(
                        gender, aggregate_ethnicity, lunch_status, ml_status, iep_status
                    )
            end as comparison_demographic_subgroup,

            if(region is null, district_state, 'Region') as comparison_entity,

        from {{ ref("int_tableau__state_assessments_demographic_comps_cubed") }}
        where
            academic_year is not null
            and assessment_name is not null
            and test_code is not null
            and district_state = 'KTAF FL'
    ),

    final as (
        select
            academic_year,
            assessment_name,
            region,
            comparison_entity,
            comparison_demographic_subgroup,
            focus_level,

            total_students,
            percent_proficient,

            comparison_demographic_group,

            total_proficient_students,

            if(test_code like 'ALG01%', 'ALG01', test_code) as test_code,

            case
                when
                    test_code in (
                        'ELA09',
                        'ELA10',
                        'ELA11',
                        'ELAGP',
                        'ALG01_HS',
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
                when
                    test_code in (
                        'ELA09',
                        'ELA10',
                        'ELA11',
                        'ELAGP',
                        'ALG01_HS',
                        'GEO01',
                        'ALG02',
                        'MATGP',
                        'SCI11'
                    )
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

        from ktaf
        where
            comparison_demographic_subgroup
            not in ('Not ML', 'Students Without Disabilities', 'Non-Binary')

        union all

        select
            academic_year,
            test_name as assessment_name,
            region,
            comparison_entity,
            comparison_demographic_subgroup,
            null as focus_level,

            total_students,
            percent_proficient,

            comparison_demographic_group,

            round(percent_proficient * total_students, 0) as total_proficient_students,

            test_code,

            case
                when comparison_demographic_subgroup = 'Grade - 08'
                then 'MS'
                when comparison_demographic_subgroup in ('Grade - 09', 'Grade - 10')
                then 'HS'
                when test_code in ('ELA09', 'ELA10', 'ELA11', 'ELAGP', 'MATGP', 'SCI11')
                then 'HS'
                when safe_cast(right(test_code, 2) as numeric) between 5 and 8
                then 'MS'
                else 'ES'
            end as school_level,

            case
                when comparison_demographic_subgroup in ('Grade - 09', 'Grade - 10')
                then 'HS'
                when test_code in ('ELA09', 'ELA10', 'ELA11', 'ELAGP', 'MATGP', 'SCI11')
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

        from {{ ref("stg_google_sheets__state_test_comparison_demographics") }}
        where comparison_demographic_subgroup != 'SE Accommodation'
    )

select
    academic_year,
    school_level,
    grade_range_band,
    assessment_name,
    discipline,
    test_code,
    region,
    comparison_entity,
    comparison_demographic_group,
    comparison_demographic_subgroup,
    total_proficient_students,
    total_students,
    percent_proficient,
    focus_level,

    row_number() over (
        partition by
            academic_year,
            school_level,
            grade_range_band,
            assessment_name,
            discipline,
            test_code,
            region,
            comparison_entity,
            comparison_demographic_group,
            comparison_demographic_subgroup,
            focus_level
    ) as rn,

from final
qualify rn = 1
