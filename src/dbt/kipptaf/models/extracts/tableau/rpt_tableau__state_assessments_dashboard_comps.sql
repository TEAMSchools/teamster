select
    academic_year,
    assessment_name,
    test_code,
    region,
    school_level,
    total_proficient_students,
    total_students,
    percent_proficient,

    case
        when region is null
        then 'Total'
        when focus_level in ('ml_status', 'iep_status', 'lunch_status,')
        then 'Subgroup'
        else initcap(regexp_replace(focus_level, r'_', ' '))
    end as comparison_demographic_group,

    case
        when region is null
        then 'All Students'
        else coalesce(gender, aggregate_ethnicity, lunch_status, ml_status, iep_status)
    end as comparison_demographic_subgroup,

    if(region is null, district_state, 'Region') as comparison_entity,

from {{ ref("int_tableau__state_assessments_demographic_comps_cubed") }}
where
    academic_year is not null
    and assessment_name is not null
    and test_code is not null
    and district_state is not null
