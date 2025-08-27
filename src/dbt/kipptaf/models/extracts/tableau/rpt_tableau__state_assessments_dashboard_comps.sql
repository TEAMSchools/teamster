with
    -- trunk-ignore(sqlfluff/ST03)
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
                when b.focus_level = 'all_null'
                then 'Total'
                when b.focus_level in ('ml_status', 'iep_status', 'lunch_status')
                then 'Subgroup'
                else initcap(regexp_replace(b.focus_level, r'_', ' '))
            end as comparison_demographic_group,

            case
                when b.focus_level = 'all_null'
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
                when focus_level = 'all_null'
                then 'Total'
                when focus_level in ('ml_status', 'iep_status', 'lunch_status')
                then 'Subgroup'
                else initcap(regexp_replace(focus_level, r'_', ' '))
            end as comparison_demographic_group,

            case
                when focus_level = 'all_null'
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

    -- deduping here because of how group by cube generates rows
    dedup_ktaf as (
        {{
            dbt_utils.deduplicate(
                relation="ktaf",
                partition_by="academic_year, region, comparison_entity,comparison_demographic_group,comparison_demographic_subgroup,focus_level,assessment_name,test_code",
                order_by="academic_year",
            )
        }}
    ),

    appended as (
        select
            academic_year,
            assessment_name,
            region,
            comparison_entity,
            focus_level,

            total_students,
            percent_proficient,

            comparison_demographic_group,
            comparison_demographic_subgroup,

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
                when test_code = 'ALG01_MS'
                then 'MS'
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

        from dedup_ktaf
        where
            comparison_demographic_subgroup
            not in ('Not ML', 'Students Without Disabilities', 'Non-Binary')

        union all

        select
            academic_year,
            test_name as assessment_name,
            region,
            comparison_entity,
            null as focus_level,

            total_students,
            percent_proficient,

            if(
                comparison_demographic_subgroup
                in ('Grade - 08', 'Grade - 09', 'Grade - 10'),
                'Total',
                comparison_demographic_group
            ) as comparison_demographic_group,

            if(
                comparison_demographic_group = 'Grade',
                'All Students',
                comparison_demographic_subgroup
            ) as comparison_demographic_subgroup,

            round(percent_proficient * total_students, 0) as total_proficient_students,

            test_code,

            case
                when
                    comparison_demographic_subgroup = 'Grade - 08'
                    and test_code = 'ALG01'
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
                    test_code in (
                        'ELA09',
                        'ELA10',
                        'ELA11',
                        'ELAGP',
                        'ALG02',
                        'GEO01',
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

        from {{ ref("stg_google_sheets__state_test_comparison_demographics") }}
        where comparison_demographic_subgroup != 'SE Accommodation'
    ),

    grouped_comps as (
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
            focus_level,

            sum(total_proficient_students) as total_proficient_students,

            sum(total_students) as total_students,

            safe_divide(
                sum(total_proficient_students), sum(total_students)
            ) as percent_proficient,

        from appended
        where comparison_demographic_subgroup != 'Blank'
        group by
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
    )

select
    a.academic_year,
    a.school_level,
    a.grade_range_band,
    a.assessment_name,
    a.discipline,
    a.test_code,
    a.region,
    a.comparison_entity,
    a.comparison_demographic_group,
    a.comparison_demographic_subgroup,
    a.total_proficient_students,
    a.total_students,
    a.percent_proficient,

    if(b.percent_proficient = a.percent_proficient, true, false) as region_matched,
    if(b.percent_proficient > a.percent_proficient, true, false) as region_outperformed,

    if(
        b.percent_proficient = a.percent_proficient
        or b.percent_proficient > a.percent_proficient,
        true,
        false
    ) as region_matched_or_outperformed,

from grouped_comps as a
left join
    grouped_comps as b
    on a.academic_year = b.academic_year
    and a.academic_year = b.academic_year
    and a.school_level = b.school_level
    and a.grade_range_band = b.grade_range_band
    and a.assessment_name = b.assessment_name
    and a.discipline = b.discipline
    and a.test_code = b.test_code
    and a.region = b.region
    and a.comparison_entity = b.comparison_entity
    and a.comparison_demographic_group = b.comparison_demographic_group
    and a.comparison_demographic_subgroup = b.comparison_demographic_subgroup
    and b.comparison_entity = 'Region'
