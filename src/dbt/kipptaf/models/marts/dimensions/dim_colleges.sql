with
    nsc_colleges as (
        select college_code_branch, college_name, college_state, two_year_four_year,
        from {{ ref("stg_nsc__student_tracker") }}
        where record_found_y_n = 'Y'
    ),

    deduplicated as (
        {{
            dbt_utils.deduplicate(
                relation="nsc_colleges",
                partition_by="college_code_branch",
                order_by="college_name desc",
            )
        }}
    )

select
    {{ dbt_utils.generate_surrogate_key(["college_code_branch"]) }} as college_key,

    college_code_branch,
    college_name,
    college_state,
    two_year_four_year,

    x.nces_id,
    x.meets_full_need,
    x.is_strong_oos_option,

    a.competitiveness_ranking as selectivity,
    a.`type` as account_type,
    a.hbcu as is_hbcu,
from deduplicated as d
left join
    {{ ref("stg_google_sheets__kippadb__nsc_crosswalk") }} as x
    on d.college_code_branch = x.college_code_nsc
    and x.rn_college_code_nsc = 1
left join {{ ref("stg_kippadb__account") }} as a on x.account_id = a.id
