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
    if(app.type_for_roll_ups = 'College', true, false) as is_college,
    if(app.type_for_roll_ups = 'Alternative Program', true, false) as is_cte,
    if(
        type_for_roll_ups
        in ('Alternative Program', 'Organization', 'Other', 'Private 2 yr'),
        true,
        false
    ) as is_certificate,

    if(app.match_type in ('Likely Plus', 'Target', 'Reach'), true, false) as is_ltr,
    if(app.starting_application_status = 'Wishlist', true, false) as is_wishlist,
    if(app.application_submission_status = 'Submitted', true, false) as is_submitted,
    if(app.application_status = 'Accepted', true, false) as is_accepted,

    if(app.application_admission_type = 'Early Action', true, false) as is_early_action,
    if(
        app.application_admission_type = 'Early Decision', true, false
    ) as is_early_decision,
    if(
        app.application_admission_type in ('Early Action', 'Early Decision'),
        true,
        false
    ) as is_early_action_decision,

    if(
        app.honors_special_program_name = 'EOF'
        and app.honors_special_program_status in ('Applied', 'Accepted'),
        true,
        false
    ) as is_eof_applied,
    if(
        app.honors_special_program_name = 'EOF'
        and app.honors_special_program_status = 'Accepted',
        true,
        false
    ) as is_eof_accepted,

    if(
        app.matriculation_decision = 'Matriculated (Intent to Enroll)'
        and app.transfer_application = false,
        true,
        false
    ) as is_matriculated,

    acc.name as account_name,
    acc.type as account_type,

    if(
        app.type_for_roll_ups = 'College' and acc.type like '%4 yr', true, false
    ) as is_4yr_college,
    if(
        app.type_for_roll_ups = 'College' and acc.type like '%2 yr', true, false
    ) as is_2yr_college,

{# row_number() over (
        partition by app.applicant, app.matriculation_decision, app.transfer_application
        order by app.enrollment_start_date asc
    ) as rn #}
from {{ ref_application }} as app
inner join {{ ref("stg_kippadb__account") }} as acc on app.school = acc.id
