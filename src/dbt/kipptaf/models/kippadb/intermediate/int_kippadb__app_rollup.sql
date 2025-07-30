with
    app_agg as (
        select
            applicant,
            max(is_eof) as is_eof_applicant,
            max(is_matriculated) as is_matriculated,
            max(is_submitted_aa) as is_submitted_aa,
            max(is_submitted_ba) as is_submitted_ba,
            max(is_submitted_certificate) as is_submitted_certificate,
            max(is_accepted_aa) as is_accepted_aa,
            max(is_accepted_ba) as is_accepted_ba,
            max(is_accepted_certificate) as is_accepted_certificate,
            max(is_early_action_decision) as is_early_action_decision,

            sum(if(is_submitted, 1, 0)) as n_submitted,
            sum(if(is_accepted, 1, 0)) as n_accepted,

            sum(if(application_submission_status = 'Wishlist', 1, 0)) as n_wishlist,

            max(
                case
                    when is_early_action_decision and is_submitted and is_accepted
                    then true
                    when is_early_action_decision and is_submitted and not is_accepted
                    then false
                end
            ) as is_accepted_early,
            max(
                case
                    when
                        is_early_action_decision
                        and is_submitted
                        and is_accepted
                        and adjusted_6_year_minority_graduation_rate >= 60
                    then true
                    when
                        is_early_action_decision
                        and is_submitted
                        and not is_accepted
                        and adjusted_6_year_minority_graduation_rate >= 60
                    then false
                end
            ) as is_accepted_early_ecc_60_plus,
            max(
                case
                    when
                        is_early_action_decision
                        and is_submitted
                        and is_accepted
                        and adjusted_6_year_minority_graduation_rate >= 90
                    then true
                    when
                        is_early_action_decision
                        and is_submitted
                        and not is_accepted
                        and adjusted_6_year_minority_graduation_rate >= 90
                    then false
                end
            ) as is_accepted_early_ecc_90_plus,
            round(
                avg(
                    if(
                        application_submission_status = 'Wishlist',
                        adjusted_6_year_minority_graduation_rate,
                        null
                    )
                ),
                0
            ) as ecc_wishlist_avg,
            round(
                min(
                    if(
                        application_submission_status = 'Wishlist',
                        adjusted_6_year_minority_graduation_rate,
                        null
                    )
                ),
                0
            ) as ecc_wishlist_min,
            round(
                avg(
                    if(
                        application_submission_status = 'Submitted',
                        adjusted_6_year_minority_graduation_rate,
                        null
                    )
                ),
                0
            ) as ecc_submitted_avg,
            round(
                min(
                    if(
                        application_submission_status = 'Submitted',
                        adjusted_6_year_minority_graduation_rate,
                        null
                    )
                ),
                0
            ) as ecc_submitted_min,
            round(
                avg(
                    if(
                        application_status = 'Accepted',
                        adjusted_6_year_minority_graduation_rate,
                        null
                    )
                ),
                0
            ) as ecc_accepted_avg,
            round(
                min(
                    if(
                        application_status = 'Accepted',
                        adjusted_6_year_minority_graduation_rate,
                        null
                    )
                ),
                0
            ) as ecc_accepted_min,
            round(
                avg(
                    if(
                        matriculation_decision = 'Matriculated (Intent to Enroll)'
                        and not transfer_application,
                        adjusted_6_year_minority_graduation_rate,
                        null
                    )
                ),
                0
            ) as ecc_matriculated_avg,
            round(
                min(
                    if(
                        matriculation_decision = 'Matriculated (Intent to Enroll)'
                        and not transfer_application,
                        adjusted_6_year_minority_graduation_rate,
                        null
                    )
                ),
                0
            ) as ecc_matriculated_min,
            sum(
                if(
                    account_type in ('Public 4 yr', 'Private 4 yr')
                    and application_submission_status = 'Wishlist',
                    1,
                    0
                )
            ) as n_4_year_wishlist,
            count(
                if(
                    adjusted_6_year_minority_graduation_rate >= 55
                    and application_submission_status = 'Wishlist',
                    id,
                    null
                )
            ) as n_55plus_ecc_wishlist,
            count(
                if(
                    adjusted_6_year_minority_graduation_rate >= 60
                    and application_submission_status = 'Wishlist',
                    id,
                    null
                )
            ) as n_60plus_ecc_wishlist,
            count(
                if(
                    adjusted_6_year_minority_graduation_rate >= 60
                    and application_submission_status = 'Submitted',
                    id,
                    null
                )
            ) as n_60plus_ecc_submitted,
            count(
                if(
                    adjusted_6_year_minority_graduation_rate >= 68
                    and application_submission_status = 'Wishlist',
                    id,
                    null
                )
            ) as n_68plus_ecc_wishlist,
            count(
                if(
                    account_billing_state = 'NJ'
                    and application_submission_status = 'Wishlist',
                    id,
                    null
                )
            ) as n_nj_wishlist,
            count(
                if(
                    account_billing_state = 'NJ'
                    and application_submission_status = 'Submitted',
                    id,
                    null
                )
            ) as n_nj_submitted,
            count(
                if(
                    meets_full_need and application_submission_status = 'Wishlist',
                    id,
                    null
                )
            ) as n_meets_full_need_wishlist,
            count(
                if(
                    meets_full_need and application_submission_status = 'Submitted',
                    id,
                    null
                )
            ) as n_meets_full_need_submitted,
            count(
                if(
                    is_strong_oos_option and application_submission_status = 'Wishlist',
                    id,
                    null
                )
            ) as n_strong_oos_wishlist,
            count(
                if(
                    is_strong_oos_option
                    and application_submission_status = 'Submitted',
                    id,
                    null
                )
            ) as n_strong_oos_submitted,
            count(
                if(
                    account_type in (
                        'Non-profit',
                        'NonProfit',
                        'Private',
                        'Private 2 yr',
                        'Public 2 yr'
                    )
                    and application_submission_status = 'Wishlist',
                    id,
                    null
                )
            ) as n_aa_cte_wishlist,
            count(
                if(
                    account_type in (
                        'Non-profit',
                        'NonProfit',
                        'Private',
                        'Private 2 yr',
                        'Public 2 yr'
                    )
                    and application_submission_status = 'Submitted',
                    id,
                    null
                )
            ) as n_aa_cte_submitted,
            count(
                if(
                    adjusted_6_year_minority_graduation_rate >= 68
                    and application_submission_status = 'Wishlist'
                    and is_early_action_decision,
                    id,
                    null
                )
            ) as n_68plus_ecc_ea_ed_wishlist,
            count(
                if(
                    meets_full_need
                    and application_submission_status = 'Wishlist'
                    and is_early_action_decision,
                    id,
                    null
                )
            ) as n_meets_full_need_ea_ed_wishlist,
            count(
                if(
                    meets_full_need
                    and application_submission_status = 'Submitted'
                    and is_early_action_decision,
                    id,
                    null
                )
            ) as n_meets_full_need_ea_ed_submitted,
            count(
                if(
                    meets_full_need
                    and application_submission_status = 'Wishlist'
                    and is_early_action_decision
                    and adjusted_6_year_minority_graduation_rate >= 85,
                    id,
                    null
                )
            ) as n_meets_full_need_ea_ed_85ecc_wishlist,
            sum(if(application_status is not null, 1, 0)) as n_app_outcomes,
            count(
                if(
                    application_submission_status = 'Submitted'
                    and adjusted_6_year_minority_graduation_rate >= 68,
                    id,
                    null
                )
            ) as n_68_plus_ecc_submitted,
            count(
                if(
                    application_submission_status = 'Submitted'
                    and adjusted_6_year_minority_graduation_rate >= 60,
                    id,
                    null
                )
            ) as n_60_plus_ecc_submitted,
            count(
                if(
                    application_submission_status = 'Submitted'
                    and adjusted_6_year_minority_graduation_rate >= 55,
                    id,
                    null
                )
            ) as n_55_plus_ecc_submitted,
            count(
                if(
                    application_submission_status = 'Submitted'
                    and is_early_action_decision
                    and adjusted_6_year_minority_graduation_rate >= 85,
                    id,
                    null
                )
            ) as n_85plus_ecc_ea_ed_submitted,
            count(
                if(
                    application_submission_status = 'Submitted'
                    and is_early_action_decision
                    and adjusted_6_year_minority_graduation_rate >= 68,
                    id,
                    null
                )
            ) as n_68plus_ecc_ea_ed_submitted,
            count(
                if(
                    application_submission_status = 'Submitted'
                    and is_early_action_decision
                    and meets_full_need
                    and adjusted_6_year_minority_graduation_rate >= 68,
                    id,
                    null
                )
            ) as n_meets_full_need_68plus_ecc_ea_ed_submitted,
            count(
                if(
                    application_submission_status = 'Submitted'
                    and is_early_action_decision
                    and meets_full_need
                    and adjusted_6_year_minority_graduation_rate >= 85,
                    id,
                    null
                )
            ) as n_meets_full_need_85plus_ecc_ea_ed_submitted,

            max(
                if(
                    application_status = 'Accepted',
                    adjusted_6_year_minority_graduation_rate,
                    null
                )
            ) as max_ecc_accepted,
        from {{ ref("base_kippadb__application") }}
        group by applicant
    )

select
    aa.applicant,
    aa.is_eof_applicant,
    aa.is_matriculated,
    aa.is_submitted_aa,
    aa.is_submitted_ba,
    aa.is_submitted_certificate,
    aa.is_accepted_aa,
    aa.is_accepted_ba,
    aa.is_accepted_certificate,
    aa.is_early_action_decision,
    aa.n_submitted,
    aa.n_accepted,
    aa.n_wishlist,
    aa.is_accepted_early,
    aa.is_accepted_early_ecc_60_plus,
    aa.is_accepted_early_ecc_90_plus,
    aa.ecc_wishlist_avg,
    aa.ecc_wishlist_min,
    aa.ecc_submitted_avg,
    aa.ecc_submitted_min,
    aa.ecc_accepted_avg,
    aa.ecc_accepted_min,
    aa.ecc_matriculated_avg,
    aa.ecc_matriculated_min,
    aa.n_4_year_wishlist,
    aa.n_55plus_ecc_wishlist,
    aa.n_60plus_ecc_wishlist,
    aa.n_68plus_ecc_wishlist,
    aa.n_nj_wishlist,
    aa.n_meets_full_need_wishlist,
    aa.n_strong_oos_wishlist,
    aa.n_aa_cte_wishlist,
    aa.n_68plus_ecc_ea_ed_wishlist,
    aa.n_meets_full_need_ea_ed_wishlist,
    aa.n_meets_full_need_ea_ed_85ecc_wishlist,
    aa.n_app_outcomes,
    aa.n_nj_submitted,
    aa.n_strong_oos_submitted,
    aa.n_meets_full_need_submitted,
    aa.n_68_plus_ecc_submitted,
    aa.n_60_plus_ecc_submitted,
    aa.n_55_plus_ecc_submitted,
    aa.n_meets_full_need_ea_ed_submitted,
    aa.n_85plus_ecc_ea_ed_submitted,
    aa.n_68plus_ecc_ea_ed_submitted,
    aa.n_meets_full_need_68plus_ecc_ea_ed_submitted,
    aa.n_meets_full_need_85plus_ecc_ea_ed_submitted,
    aa.n_aa_cte_submitted,
    aa.max_ecc_accepted,

    ocf.best_guess_pathway,

    r.student_number,

    case
        when
            ocf.best_guess_pathway = '4-year'
            and round(r.contact_college_match_display_gpa, 2) >= 3.50
            and aa.n_wishlist >= 9
            and aa.n_68plus_ecc_wishlist >= 7
            and aa.n_nj_wishlist >= 4
            and aa.n_meets_full_need_wishlist >= 2
            and aa.n_meets_full_need_ea_ed_85ecc_wishlist >= 1
            and aa.n_68plus_ecc_ea_ed_wishlist >= 2
        then 1
        when
            ocf.is_ed_ea != 'Yes'
            and ocf.best_guess_pathway = '4-year'
            and round(r.contact_college_match_display_gpa, 2) >= 3.00
            and aa.n_wishlist >= 9
            and aa.n_60plus_ecc_wishlist >= 7
            and aa.n_nj_wishlist >= 6
            and aa.n_strong_oos_wishlist >= 2
        then 1
        when
            ocf.is_ed_ea = 'Yes'
            and ocf.best_guess_pathway = '4-year'
            and round(r.contact_college_match_display_gpa, 2) >= 3.00
            and aa.n_wishlist >= 9
            and aa.n_60plus_ecc_wishlist >= 7
            and aa.n_nj_wishlist >= 6
            and aa.n_strong_oos_wishlist >= 2
            and aa.n_68plus_ecc_ea_ed_wishlist >= 2
            and aa.n_meets_full_need_ea_ed_wishlist >= 1
        then 1
        when
            ocf.best_guess_pathway = '4-year'
            and round(r.contact_college_match_display_gpa, 2) >= 2.50
            and aa.n_wishlist >= 6
            and aa.n_nj_wishlist >= 6
            and aa.n_55plus_ecc_wishlist >= 4
        then 1
        when
            ocf.best_guess_pathway = '4-year'
            and round(r.contact_college_match_display_gpa, 2) >= 2.00
            and aa.n_wishlist >= 6
            and aa.n_nj_wishlist >= 6
        then 1
        when
            ocf.best_guess_pathway = '4-year'
            and round(r.contact_college_match_display_gpa, 2) < 2.00
            and aa.n_wishlist >= 3
            and aa.n_nj_wishlist >= 3
            and aa.n_aa_cte_wishlist >= 1
        then 1
        when
            ocf.best_guess_pathway = '2-year'
            and aa.n_wishlist >= 3
            and (
                aa.n_aa_cte_wishlist >= 3
                or (aa.n_aa_cte_wishlist >= 2 and aa.n_4_year_wishlist >= 1)
            )
        then 1
        when
            ocf.best_guess_pathway in ('CTE', 'Workforce')
            and aa.n_wishlist >= 3
            and aa.n_aa_cte_wishlist >= 3
        then 1
        else 0
    end as is_wishlist_quality_bar_int,

    case
        when
            round(r.contact_college_match_display_gpa, 2) >= 3.50
            and aa.n_meets_full_need_85plus_ecc_ea_ed_submitted >= 1
            and aa.n_68_plus_ecc_submitted >= 2
        then 1
        when
            ocf.is_ed_ea = 'Yes'
            and aa.n_68_plus_ecc_submitted >= 2
            and aa.n_meets_full_need_68plus_ecc_ea_ed_submitted >= 1
        then 1
        else 0
    end as is_submitted_quality_bar_ea_int,

    case
        when
            ocf.best_guess_pathway = '4-year'
            and round(r.contact_college_match_display_gpa, 2) >= 3.50
            and aa.n_submitted >= 9
            and aa.n_68_plus_ecc_submitted >= 7
            and aa.n_nj_submitted >= 4
            and aa.n_meets_full_need_submitted >= 2
            and aa.n_meets_full_need_85plus_ecc_ea_ed_submitted >= 1
            and aa.n_68plus_ecc_ea_ed_submitted >= 2
        then 1
        when
            ocf.is_ed_ea != 'Yes'
            and ocf.best_guess_pathway = '4-year'
            and round(r.contact_college_match_display_gpa, 2) >= 3.00
            and aa.n_submitted >= 9
            and aa.n_60plus_ecc_submitted >= 7
            and aa.n_nj_submitted >= 6
            and aa.n_strong_oos_submitted >= 2
        then 1
        when
            ocf.is_ed_ea = 'Yes'
            and ocf.best_guess_pathway = '4-year'
            and round(r.contact_college_match_display_gpa, 2) >= 3.00
            and aa.n_submitted >= 9
            and aa.n_68_plus_ecc_submitted >= 7
            and aa.n_nj_submitted >= 6
            and aa.n_strong_oos_submitted >= 2
            and aa.n_68plus_ecc_ea_ed_submitted >= 2
            and aa.n_meets_full_need_ea_ed_submitted >= 1
        then 1
        when
            ocf.best_guess_pathway = '4-year'
            and round(r.contact_college_match_display_gpa, 2) >= 2.50
            and aa.n_submitted >= 6
            and aa.n_nj_submitted >= 6
            and aa.n_55_plus_ecc_submitted >= 4
        then 1
        when
            ocf.best_guess_pathway = '4-year'
            and round(r.contact_college_match_display_gpa, 2) >= 2.00
            and aa.n_submitted >= 6
            and aa.n_nj_submitted >= 6
        then 1
        when
            ocf.best_guess_pathway = '4-year'
            and round(r.contact_college_match_display_gpa, 2) < 2.00
            and aa.n_submitted >= 3
            and aa.n_nj_submitted >= 3
            and aa.n_aa_cte_submitted >= 1
        then 1
        else 0
    end as is_submitted_quality_bar_4yr_int,
from app_agg as aa
inner join {{ ref("int_kippadb__roster") }} as r on aa.applicant = r.contact_id
left join
    {{ ref("stg_overgrad__students") }} as os on r.contact_id = os.external_student_id
left join
    {{ ref("int_overgrad__custom_fields_pivot") }} as ocf
    on os.id = ocf.id
    and ocf._dbt_source_model = 'stg_overgrad__students'
