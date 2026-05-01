with
    -- trunk-ignore(sqlfluff/ST03): referenced by string in dbt_utils.deduplicate
    nsc_colleges as (
        select college_code_branch, college_name, college_state,
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
    d.college_code_branch,
    d.college_name,
    d.college_state as state_abbreviation,

    x.nces_id,
    x.meets_full_need as meets_full_financial_need,
    x.is_strong_oos_option as is_strong_out_of_state_option,

    a.competitiveness_ranking as selectivity_tier,
    a.`type` as account_type,
    a.hbcu as is_hbcu,

    {{ dbt_utils.generate_surrogate_key(["d.college_code_branch"]) }} as college_key,
from deduplicated as d
left join
    {{ ref("stg_google_sheets__kippadb__nsc_crosswalk") }} as x
    on d.college_code_branch = x.college_code_nsc
    and x.rn_college_code_nsc = 1
left join {{ ref("stg_kippadb__account") }} as a on x.account_id = a.id
