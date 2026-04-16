with
    appended as (
        /* NJ: cross join fans out district-level rows to Camden + Newark */
        select
            academic_year,
            assessment_name,
            comparison_entity,
            comparison_demographic_group,
            comparison_demographic_subgroup,
            focus_level,
            school_level,
            grade_range_band,
            discipline,
            total_proficient_students,
            total_students,
            percent_proficient,

            if(test_code like 'ALG01%', 'ALG01', test_code) as test_code,

            if(region is null, regions, region) as region,

        from {{ ref("int_tableau__state_assessments_demographic_comps") }}
        cross join unnest(['Camden', 'Newark']) as regions
        where
            district_state = 'KTAF NJ'
            and (region is null or region = regions)
            and comparison_demographic_subgroup
            not in ('Not ML', 'Students Without Disabilities', 'Non-Binary', 'Blank')

        union all

        /* FL */
        select
            academic_year,
            assessment_name,
            comparison_entity,
            comparison_demographic_group,
            comparison_demographic_subgroup,
            focus_level,
            school_level,
            grade_range_band,
            discipline,
            total_proficient_students,
            total_students,
            percent_proficient,

            if(test_code like 'ALG01%', 'ALG01', test_code) as test_code,

            coalesce(region, 'Miami') as region,

        from {{ ref("int_tableau__state_assessments_demographic_comps") }}
        where
            district_state = 'KTAF FL'
            and comparison_demographic_subgroup
            not in ('Not ML', 'Students Without Disabilities', 'Non-Binary', 'Blank')

        union all

        /* Google Sheets benchmarks */
        select
            academic_year,
            assessment_name,
            comparison_entity,
            comparison_demographic_group,
            comparison_demographic_subgroup,
            null as focus_level,
            school_level,
            grade_range_band,
            discipline,
            total_proficient_students,
            total_students,
            percent_proficient,
            aligned_test_code as test_code,
            region,

        from {{ ref("stg_google_sheets__state_test_comparison_demographics") }}
        where comparison_demographic_subgroup not in ('SE Accommodation', 'Blank')
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
        b.percent_proficient >= a.percent_proficient, true, false
    ) as region_matched_or_outperformed,

from grouped_comps as a
left join
    grouped_comps as b
    on a.academic_year = b.academic_year
    and a.school_level = b.school_level
    and a.grade_range_band = b.grade_range_band
    and a.assessment_name = b.assessment_name
    and a.discipline = b.discipline
    and a.test_code = b.test_code
    and a.region = b.region
    and a.comparison_demographic_group = b.comparison_demographic_group
    and a.comparison_demographic_subgroup = b.comparison_demographic_subgroup
    and b.comparison_entity = 'Region'
