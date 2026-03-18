with
    roster as (
        select
            contact_id,
            student_number,
            first_name,
            last_name,
            contact_owner_name,
            contact_currently_enrolled_school,
            best_guess_pathway,
            is_ed_ea,

            round(contact_college_match_display_gpa, 2) as gpa,
        from {{ ref("int_kippadb__roster") }}
    ),

    overgrad_top_choice as (
        select
            student__external_student_id,
            university__ipeds_id,
            top_choice_schools,

            safe_cast(university__ipeds_id as string) as university_ipeds_id_str,
        from {{ ref("int_overgrad__admissions") }}
        where top_choice_schools is not null
    ),

    `rollup` as (
        select
            applicant,
            n_wishlist,
            n_submitted,
            n_4_year_wishlist,
            n_55plus_ecc_wishlist,
            n_60plus_ecc_wishlist,
            n_68plus_ecc_wishlist,
            n_nj_wishlist,
            n_meets_full_need_wishlist,
            n_strong_oos_wishlist,
            n_aa_cte_wishlist,
            n_68plus_ecc_ea_ed_wishlist,
            n_meets_full_need_ea_ed_wishlist,
            n_meets_full_need_ea_ed_85ecc_wishlist,
            n_55_plus_ecc_submitted,
            n_60_plus_ecc_submitted,
            n_68_plus_ecc_submitted,
            n_nj_submitted,
            n_meets_full_need_submitted,
            n_strong_oos_submitted,
            n_aa_cte_submitted,
            n_68plus_ecc_ea_ed_submitted,
            n_85plus_ecc_ea_ed_submitted,
            n_meets_full_need_ea_ed_submitted,
            n_meets_full_need_68plus_ecc_ea_ed_submitted,
            n_meets_full_need_85plus_ecc_ea_ed_submitted,
            is_wishlist_quality_bar_int,
            is_submitted_quality_bar_4yr_int,
            is_submitted_quality_bar_ea_int,
        from {{ ref("int_kippadb__app_rollup") }}
    )

-- trunk-ignore(sqlfluff/ST06)
select
    -- student identity
    r.contact_id,
    r.student_number,
    r.first_name,
    r.last_name,
    r.contact_owner_name as counselor,
    r.contact_currently_enrolled_school as high_school,

    -- quality bar drivers
    r.best_guess_pathway,
    r.is_ed_ea,
    r.gpa,

    -- application context
    a.id as application_id,
    a.name as application_name,
    a.account_name as college_name,
    a.account_type,
    a.account_billing_state,
    a.application_submission_status,
    a.application_admission_type,
    a.application_status,
    a.match_type,
    a.adjusted_6_year_minority_graduation_rate as ecc,

    a.meets_full_need,
    a.is_strong_oos_option as is_strong_oos,
    a.is_early_action_decision,
    og.top_choice_schools as overgrad_top_choice,
    ogc.n_overgrad_1st_choice,
    ogc.n_overgrad_2nd_choice,
    ogc.n_overgrad_3rd_choice,
    ogc.has_duplicate_overgrad_1st_choice,
    ogc.has_duplicate_overgrad_2nd_choice,
    ogc.has_duplicate_overgrad_3rd_choice,

    -- per-app quality bar component flags
    a.account_type in ('Public 4 yr', 'Private 4 yr') as is_4yr,
    a.account_billing_state = 'NJ' as is_nj,
    a.account_type in (
        'Non-profit', 'NonProfit', 'Private', 'Private 2 yr', 'Public 2 yr'
    ) as is_aa_cte,

    a.adjusted_6_year_minority_graduation_rate >= 55 as is_55plus_ecc,
    a.adjusted_6_year_minority_graduation_rate >= 60 as is_60plus_ecc,
    a.adjusted_6_year_minority_graduation_rate >= 68 as is_68plus_ecc,
    a.adjusted_6_year_minority_graduation_rate >= 85 as is_85plus_ecc,

    -- student-level wishlist counts (actual vs required)
    ro.n_wishlist,
    ro.n_4_year_wishlist,
    ro.n_55plus_ecc_wishlist,
    ro.n_60plus_ecc_wishlist,
    ro.n_68plus_ecc_wishlist,
    ro.n_nj_wishlist,
    ro.n_meets_full_need_wishlist,
    ro.n_strong_oos_wishlist,
    ro.n_aa_cte_wishlist,
    ro.n_68plus_ecc_ea_ed_wishlist,
    ro.n_meets_full_need_ea_ed_wishlist,
    ro.n_meets_full_need_ea_ed_85ecc_wishlist,

    -- student-level submitted counts (actual vs required)
    ro.n_submitted,
    ro.n_55_plus_ecc_submitted,
    ro.n_60_plus_ecc_submitted,
    ro.n_68_plus_ecc_submitted,
    ro.n_nj_submitted,
    ro.n_meets_full_need_submitted,
    ro.n_strong_oos_submitted,
    ro.n_aa_cte_submitted,
    ro.n_68plus_ecc_ea_ed_submitted,
    ro.n_85plus_ecc_ea_ed_submitted,
    ro.n_meets_full_need_ea_ed_submitted,
    ro.n_meets_full_need_68plus_ecc_ea_ed_submitted,
    ro.n_meets_full_need_85plus_ecc_ea_ed_submitted,

    -- quality bar pass/fail outcomes
    ro.is_wishlist_quality_bar_int,
    ro.is_submitted_quality_bar_4yr_int,
    ro.is_submitted_quality_bar_ea_int,

    -- which quality bar tier applies to this student (for auditing context)
    case
        when r.best_guess_pathway = '4-year' and r.gpa >= 3.50
        then '4yr_3.50plus'
        when r.best_guess_pathway = '4-year' and r.is_ed_ea != 'Yes' and r.gpa >= 3.00
        then '4yr_3.00to3.49_no_ea'
        when r.best_guess_pathway = '4-year' and r.is_ed_ea = 'Yes' and r.gpa >= 3.00
        then '4yr_3.00to3.49_ea'
        when r.best_guess_pathway = '4-year' and r.gpa >= 2.50
        then '4yr_2.50to2.99'
        when r.best_guess_pathway = '4-year' and r.gpa >= 2.00
        then '4yr_2.00to2.49'
        when r.best_guess_pathway = '4-year' and r.gpa < 2.00
        then '4yr_under2.00'
        when r.best_guess_pathway = '2-year'
        then '2yr'
        when r.best_guess_pathway in ('CTE', 'Workforce')
        then 'cte_workforce'
    end as wishlist_quality_bar_tier,
from {{ ref("base_kippadb__application") }} as a
inner join roster as r on a.applicant = r.contact_id
inner join `rollup` as ro on a.applicant = ro.applicant
left join {{ ref("stg_kippadb__account") }} as acc on a.school = acc.id
left join
    overgrad_top_choice as og
    on a.applicant = og.student__external_student_id
    and acc.nces_id = og.university_ipeds_id_str
left join
    {{ ref("int_overgrad__choice_counts") }} as ogc
    on a.applicant = ogc.contact_id
where a.application_submission_status in ('Wishlist', 'Submitted')
