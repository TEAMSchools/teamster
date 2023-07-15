{%- set ref_application = ref("stg_kippadb__application") -%}

select
    {{
        dbt_utils.star(
            from=ref_application,
            relation_alias="app",
            except=["starting_application_status"],
        )
    }},
    ifnull(
        app.starting_application_status, app.application_status
    ) as starting_application_status,
    if(app.type_for_roll_ups = 'Alternative Program', 1, 0) as is_cte,
    if(app.application_admission_type = 'Early Action', 1, 0) as is_early_action,
    if(app.application_admission_type = 'Early Decision', 1, 0) as is_early_decision,
    if(
        app.application_admission_type in ('Early Action', 'Early Decision'), 1, 0
    ) as is_early_actiondecision,
    if(app.application_submission_status = 'Submitted', 1, 0) as is_submitted,
    if(app.application_status = 'Accepted', 1, 0) as is_accepted,
    if(app.match_type in ('Likely Plus', 'Target', 'Reach'), 1, 0) as is_ltr,
    if(app.starting_application_status = 'Wishlist', 1, 0) as is_wishlist,
    if(
        app.honors_special_program_name = 'EOF'
        and app.honors_special_program_status in ('Applied', 'Accepted'),
        1,
        0
    ) as is_eof_applied,
    if(
        app.honors_special_program_name = 'EOF'
        and app.honors_special_program_status = 'Accepted',
        1,
        0
    ) as is_eof_accepted,

    acc.name as account_name,
    acc.type as account_type,

    if(
        app.type_for_roll_ups = 'College' and acc.type like '%4 yr', 1, 0
    ) as is_4yr_college,
    if(
        app.type_for_roll_ups = 'College' and acc.type like '%2 yr', 1, 0
    ) as is_2yr_college,
from {{ ref_application }} as app
inner join {{ ref("stg_kippadb__account") }} as acc on app.school = acc.id
