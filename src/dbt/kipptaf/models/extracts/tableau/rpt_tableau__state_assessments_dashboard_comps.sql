select
    b.academic_year,
    b.assessment_name,
    b.test_code,
    b.total_proficient_students,
    b.total_students,
    b.percent_proficient,

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
    and b.district_state = 'KATF NJ'

union all

select
    academic_year,
    assessment_name,
    test_code,
    total_proficient_students,
    total_students,
    percent_proficient,

    coalesce(region, 'Miami') as region,

    case
        when region is null
        then 'Total'
        when focus_level in ('ml_status', 'iep_status', 'lunch_status,')
        then 'Subgroup'
        else initcap(regexp_replace(focus_level, r'_', ' '))
    end as comparison_demographic_group,

    case
        when region is null and focus_level = 'all_null'
        then 'All Students'
        else coalesce(gender, aggregate_ethnicity, lunch_status, ml_status, iep_status)
    end as comparison_demographic_subgroup,

    if(region is null, district_state, 'Region') as comparison_entity,

from {{ ref("int_tableau__state_assessments_demographic_comps_cubed") }}
where
    academic_year is not null
    and assessment_name is not null
    and test_code is not null
    and district_state = 'KATF FL'
