with
    clean_cols as (
        select
            test_season,
            test_code,
            county_name,
            district_name,
            school_name,
            safe_cast(academic_year as int) as academic_year,
            upper(dfg) as dfg,
            upper(subgroup) as subgroup,
            case
                upper(subgroup_type)
                when 'NATIVE HAWAIIAN'
                then 'NATIVE HAWAIIAN OR OTHER PACIFIC ISLANDER'
                when 'NON ECON. DISADVANTAGED'
                then 'NON-ECON. DISADVANTAGED'
                when 'STUDENTS WITH DISABLITIES'
                then 'STUDENTS WITH DISABILITIES'
                else upper(subgroup_type)
            end as subgroup_type,
            if(
                upper(county_code) in ('DFG', 'STATE'),
                upper(county_code),
                right('0' || county_code, 2)
            ) as county_code,
            if(
                district_code = 'DFG Not Designated',
                district_code,
                right('0000' || district_code, 4)
            ) as district_code,
            right(concat('000', safe_cast(school_code as int)), 3) as school_code,

            safe_cast(nullif(reg_to_test, '') as int) as reg_to_test,
            safe_cast(nullif(not_tested, '') as int) as not_tested,
            safe_cast(nullif(valid_scores, '') as int) as valid_scores,
            safe_cast(nullif(mean_score, '') as int) as mean_score,

            safe_cast(nullif(l1_percent, '*') as numeric) as l1_percent,
            safe_cast(nullif(l2_percent, '*') as numeric) as l2_percent,
            safe_cast(nullif(l3_percent, '*') as numeric) as l3_percent,
            safe_cast(nullif(l4_percent, '*') as numeric) as l4_percent,
            safe_cast(nullif(l5_percent, '*') as numeric) as l5_percent,
        from {{ source("njdoe", "src_njdoe__parcc") }}
    )

select
    *,
    (l1_percent / 100) * valid_scores as l1_count,
    (l2_percent / 100) * valid_scores as l2_count,
    (l3_percent / 100) * valid_scores as l3_count,
    (l4_percent / 100) * valid_scores as l4_count,
    (l5_percent / 100) * valid_scores as l5_count,
    ((l4_percent / 100) * valid_scores)
    + ((l5_percent / 100) * valid_scores) as proficient_count,
from clean_cols
