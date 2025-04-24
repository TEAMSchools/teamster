{%- set ref_application = ref("stg_kippadb__application") -%}

with
    app_acct as (
        select
            {{
                dbt_utils.star(
                    from=ref_application,
                    relation_alias="app",
                    except=["starting_application_status"],
                )
            }},

            coalesce(
                app.starting_application_status, app.application_status
            ) as starting_application_status,

            if(app.type_for_roll_ups = 'College', true, false) as is_college,
            if(app.type_for_roll_ups = 'Alternative Program', true, false) as is_cte,
            if(
                app.type_for_roll_ups
                in ('Alternative Program', 'Organization', 'Other')
                or (app.type_for_roll_ups = 'College' and acc.type = 'Private 2 yr'),
                true,
                false
            ) as is_certificate,

            if(
                app.match_type in ('Likely Plus', 'Target', 'Reach'), true, false
            ) as is_ltr,
            if(
                app.starting_application_status = 'Wishlist', true, false
            ) as is_wishlist,
            if(
                app.application_submission_status = 'Submitted', true, false
            ) as is_submitted,
            if(app.application_status = 'Accepted', true, false) as is_accepted,

            if(
                app.application_admission_type = 'Early Action', true, false
            ) as is_early_action,
            if(
                app.application_admission_type = 'Early Decision', true, false
            ) as is_early_decision,

            if(app.honors_special_program_name like '%EOF%', true, false) as is_eof,
            if(
                app.honors_special_program_name like '%EOF%'
                and app.honors_special_program_status in ('Applied', 'Accepted'),
                true,
                false
            ) as is_eof_applied,
            if(
                app.honors_special_program_name like '%EOF%'
                and app.honors_special_program_status = 'Accepted',
                true,
                false
            ) as is_eof_accepted,

            if(
                app.matriculation_decision = 'Matriculated (Intent to Enroll)'
                and not app.transfer_application,
                true,
                false
            ) as is_matriculated,

            acc.name as account_name,
            acc.type as account_type,
            acc.adjusted_6_year_minority_graduation_rate,
            acc.competitiveness_ranking,
            acc.act25,
            acc.act75,
            acc.act_composite_25_75,
            acc.adjusted_6_year_graduation_rate,
            acc.billing_state as account_billing_state,
            acc.hbcu,

            enr.status as enrollment_status,
            enr.pursuing_degree_type as enrollment_pursuing_degree_type,
            enr.start_date as enrollment_start_date,

            if(
                app.type_for_roll_ups = 'College' and acc.type like '%4 yr', true, false
            ) as is_4yr_college,
            if(
                app.type_for_roll_ups = 'College' and acc.type = 'Public 2 yr',
                true,
                false
            ) as is_2yr_college,

            row_number() over (
                partition by
                    app.applicant, app.matriculation_decision, app.transfer_application
                order by enr.start_date asc
            ) as rn_app_enr,

            coalesce(n.meets_full_need, false) as meets_full_need,
            coalesce(n.is_strong_oos_option, false) as is_strong_oos_option,
        from {{ ref_application }} as app
        inner join {{ ref("stg_kippadb__account") }} as acc on app.school = acc.id
        inner join
            {{ ref("base_kippadb__contact") }} as c on app.applicant = c.contact_id
        left join
            {{ ref("stg_kippadb__enrollment") }} as enr
            on app.applicant = enr.student
            and app.school = enr.school
            and c.contact_kipp_hs_class = enr.start_date_year
            and enr.rn_stu_school_start = 1
        left join
            {{ ref("stg_kippadb__nsc_crosswalk") }} as n
            on acc.id = n.account_id
            and n.rn_account = 1
    )

select
    *,
    if(is_early_action or is_early_decision, true, false) as is_early_action_decision,
    if(is_submitted and is_2yr_college, true, false) as is_submitted_aa,
    if(is_submitted and is_4yr_college, true, false) as is_submitted_ba,
    if(is_submitted and is_certificate, true, false) as is_submitted_certificate,
    if(is_submitted and is_2yr_college and is_accepted, true, false) as is_accepted_aa,
    if(is_submitted and is_4yr_college and is_accepted, true, false) as is_accepted_ba,
    if(
        is_submitted and is_certificate and is_accepted, true, false
    ) as is_accepted_certificate,
    row_number() over (
        partition by applicant, school
        order by is_matriculated desc, is_accepted desc, is_submitted desc
    ) as rn_application_school,
from app_acct
