select
    b.academic_year,
    b.assessment_name,
    b.test_code,
    b.total_proficient_students,
    b.total_students,
    b.percent_proficient,

    case
        when b.region is null and b.district_state = 'KTAF NJ'
        then regions
        when b.region is null and b.district_state = 'KTAF FL'
        then 'Miami'
        else b.region
    end as region,

    case
        when b.region is null
        then 'Total'
        when b.focus_level in ('ml_status', 'iep_status', 'lunch_status,')
        then 'Subgroup'
        else initcap(regexp_replace(b.focus_level, r'_', ' '))
    end as comparison_demographic_group,

    case
        when b.region is null and focus_level = 'all_null'
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
    and b.district_state is not null
