with
    programs as (
        select
            p.student,

            string_agg(
                concat(
                    a.name,
                    if(
                        p.opportunity_dates is not null,
                        concat(' (', p.opportunity_dates, ')'),
                        ''
                    )
                ),
                '; '
            ) as college_programs,

            max(if(a.name = 'Project BASTA', true, false)) as is_basta,
            max(if(a.name = 'Braven', true, false)) as is_braven,
            max(if(a.name = 'Backrs', true, false)) as is_backrs,

            max(
                if(
                    a.name in ('KIPP New Jersey - Camden', 'KIPP New Jersey - Newark'),
                    true,
                    false
                )
            ) as is_kippnj_internship,
        from {{ ref("stg_kippadb__internships_programs") }} as p
        inner join
            {{ ref("stg_kippadb__account") }} as a
            on p.program_or_organization_name = a.id
        where
            p.internship_or_program_type = 'College Program'
            and p.application_status not in ('Not Matched', 'Wait-listed')
        group by p.student
    ),

    career_conversations as (
        select
            contact_id,

            sum(cc1) as cc1_count,
            sum(cc2) as cc2_count,
            sum(cc3) as cc3_count,
            sum(cc4) as cc4_count,
            sum(cc5) as cc5_count,
            sum(cc1 + cc2 + cc3 + cc4 + cc5) as cc_total_count,
        from {{ ref("int_kippadb__contact_note_rollup") }}
        group by contact_id
    ),

    career_conversation_checklist as (
        select
            contact_id,

            (
                select countif(item),
                from
                    unnest(
                        [
                            is_resume_score,
                            is_linkedin,
                            is_mock_interview_or_prep,
                            is_professional_references_list,
                            is_job_search_template,
                            is_cover_letter_template,
                            is_work_samples
                        ]
                    ) as item
            ) as career_conversation_items_complete_count,

            if(
                is_resume_score
                and is_linkedin
                and is_mock_interview_or_prep
                and is_professional_references_list
                and is_job_search_template
                and is_cover_letter_template
                and is_work_samples,
                true,
                false
            ) as is_career_conversation_complete,
        from {{ ref("stg_google_appsheet__kfwd_career_conversations__output") }}
    ),

    roster as (
        select
            r.contact_id,
            r.contact_first_name as sf_first_name,
            r.contact_last_name as sf_last_name,
            r.lastfirst as sf_lastfirst,
            r.contact_kipp_ms_graduate,
            r.contact_kipp_hs_graduate,
            r.contact_kipp_hs_class,
            r.contact_college_match_display_gpa as college_match_display_gpa,
            r.contact_kipp_region_name as kipp_region_name,
            r.contact_description,
            r.contact_gender,
            r.contact_ethnicity,
            r.contact_expected_college_graduation as expected_college_grad_date,
            r.contact_actual_college_graduation_date as actual_college_grad_date,
            r.contact_current_kipp_student as current_kipp_student,
            r.contact_owner_name,
            r.contact_postsec_advisor as postsec_advisor,
            r.es_graduated,
            r.tier,
            r.contact_advising_provider as advising_provider,
            r.contact_most_recent_iep_date as most_recent_iep_date,
            r.contact_middle_school_attended as middle_school_attended,
            r.contact_high_school_graduated_from as high_school_graduated_from,
            r.ktc_cohort,
            r.contact_currently_enrolled_school as currently_enrolled_school,
            r.contact_current_college_cumulative_gpa as current_college_cumulative_gpa,
            r.contact_mobile_phone as primary_phone,
            r.contact_home_phone as secondary_phone,

            e.pursuing_degree_type,
            e.type,
            e.start_date,
            e.actual_end_date,
            e.major,
            e.status,

            a.adjusted_6_year_minority_graduation_rate as ecc,
            a.name as institution,

            sr.survey_response_id as reconciliation_response_id,

            p.college_programs,

            cc.notes as career_conversation_notes,

            lower(r.contact_email) as sf_email,
            lower(r.contact_secondary_email) as sf_secondary_email,

            coalesce(p.is_basta, false) as is_basta,
            coalesce(p.is_braven, false) as is_braven,
            coalesce(p.is_backrs, false) as is_backrs,
            coalesce(p.is_kippnj_internship, false) as is_kippnj_internship,
            coalesce(cc.is_resume_score, false) as is_resume_score,
            coalesce(cc.is_linkedin, false) as is_linkedin,
            coalesce(cc.is_mock_interview_or_prep, false) as is_mock_interview_or_prep,
            coalesce(
                cc.is_professional_references_list, false
            ) as is_professional_references_list,
            coalesce(cc.is_job_search_template, false) as is_job_search_template,
            coalesce(cc.is_cover_letter_template, false) as is_cover_letter_template,
            coalesce(cc.is_work_samples, false) as is_work_samples,
            coalesce(ccr.cc1_count, 0) as cc1_count,
            coalesce(ccr.cc2_count, 0) as cc2_count,
            coalesce(ccr.cc3_count, 0) as cc3_count,
            coalesce(ccr.cc4_count, 0) as cc4_count,
            coalesce(ccr.cc5_count, 0) as cc5_count,
            coalesce(ccr.cc_total_count, 0) as cc_total_count,
            coalesce(
                ccc.career_conversation_items_complete_count, 0
            ) as career_conversation_items_complete_count,
            coalesce(
                ccc.is_career_conversation_complete, false
            ) as is_career_conversation_complete,

            extract(
                month from r.contact_expected_college_graduation
            ) as expected_grad_date_month,
            extract(
                year from r.contact_expected_college_graduation
            ) as expected_grad_date_year,
            extract(month from e.actual_end_date) as actual_end_date_month,
            extract(year from e.actual_end_date) as actual_end_date_year,

            if(
                e.status = 'Graduated',
                row_number() over (
                    partition by e.student order by e.actual_end_date asc
                ),
                1
            ) as rn_graduated,

            case
                when r.contact_college_match_display_gpa >= 3.50
                then '3.50+'
                when r.contact_college_match_display_gpa >= 3.00
                then '3.00-3.49'
                when r.contact_college_match_display_gpa >= 2.50
                then '2.50-2.99'
                when r.contact_college_match_display_gpa >= 2.00
                then '2.00-2.50'
                when r.contact_college_match_display_gpa < 2.00
                then '<2.00'
            end as hs_gpa_bands,

        from {{ ref("int_kippadb__roster") }} as r
        left join
            {{ ref("stg_kippadb__enrollment") }} as e
            on r.contact_id = e.student
            and e.type not in ('High School', 'Middle School')
            and e.status = 'Graduated'
        left join {{ ref("stg_kippadb__account") }} as a on e.school = a.id
        left join
            {{ ref("int_surveys__kfwd_career_launch_reconciliation") }} as sr
            on r.contact_id = sr.sf_contact_id
        left join programs as p on r.contact_id = p.student
        left join
            {{ ref("stg_google_appsheet__kfwd_career_conversations__output") }} as cc
            on r.contact_id = cc.contact_id
        left join career_conversations as ccr on r.contact_id = ccr.contact_id
        left join career_conversation_checklist as ccc on r.contact_id = ccc.contact_id
        where
            r.ktc_status in ('HSG', 'TAF')
            and r.ktc_cohort <= {{ var("current_academic_year") }}
            and r.contact_id is not null
    ),

    survey_pivot as (
        select
            survey_id,
            survey_title,
            response_id,
            response_date_submitted,
            respondent_user_principal_name,
            respondent_salesforce_id,

            /* pivot cols */
            after_grad,
            alumni_dob,
            alumni_email,
            alumni_phone,
            cell_number,
            company,
            complete_program,
            debt_amount,
            debt_binary,
            first_name,
            grad_school_major,
            grad_school_name,
            highest_level_of_education,
            job_sat,
            last_name,
            linkedin,
            linkedin_link,
            not_pursuing_plan,
            reenrollment,
            `role`,
            satisfied_program,
            search_focus,

            coalesce(annual_income, annual_income_alt) as annual_income,
            coalesce(benefits, benefits_alt) as benefits,
        from
            {{ ref("int_surveys__kfwd_career_launch_responses") }} pivot (
                max(response_string_value) for question_short_name in (
                    'after_grad',
                    'alumni_dob',
                    'alumni_email',
                    'alumni_phone',
                    'annual_income',
                    'annual_income_alt',
                    'benefits',
                    'benefits_alt',
                    'cell_number',
                    'company',
                    'complete_program',
                    'debt_amount',
                    'debt_binary',
                    'first_name',
                    'grad_school_major',
                    'grad_school_name',
                    'highest_level_of_education',
                    'job_sat',
                    'last_name',
                    'linkedin',
                    'linkedin_link',
                    'not_pursuing_plan',
                    'reenrollment',
                    'role',
                    'satisfied_program',
                    'search_focus'
                )
            )
    ),

    survey_clean as (
        select
            *,

            cast(
                replace(
                    case
                        when annual_income like '%-%'
                        then regexp_extract(annual_income, r'\$([0-9,]+) -')
                        when annual_income like '%or more%'
                        then regexp_extract(annual_income, r'\$([0-9,]+) or more')
                        else regexp_extract(annual_income, r'\$([0-9,]+)')
                    end,
                    ',',
                    ''
                ) as float64
            ) as annual_income_clean,
        from survey_pivot
    ),

    excluded_responses as (
        select survey_response_id,
        from {{ ref("int_surveys__kfwd_career_launch_reconciliation") }}
        where reconcile_or_exclude = 'Exclude'
    ),

    survey_filtered as (
        select sc.*,
        from survey_clean as sc
        left join excluded_responses as er on sc.response_id = er.survey_response_id
        where er.survey_response_id is null
    )

select
    r.contact_id,
    r.sf_first_name,
    r.sf_last_name,
    r.sf_lastfirst,
    r.contact_kipp_ms_graduate,
    r.contact_kipp_hs_graduate,
    r.contact_kipp_hs_class,
    r.college_match_display_gpa,
    r.kipp_region_name,
    r.contact_description,
    r.contact_gender,
    r.contact_ethnicity,
    r.expected_college_grad_date,
    r.actual_college_grad_date,
    r.current_kipp_student,
    r.contact_owner_name,
    r.pursuing_degree_type,
    r.type,
    r.start_date,
    r.actual_end_date,
    r.major,
    r.status,
    r.ecc,
    r.institution,
    r.reconciliation_response_id,
    r.college_programs,
    r.is_basta,
    r.is_braven,
    r.is_backrs,
    r.is_kippnj_internship,
    r.hs_gpa_bands,
    r.sf_email,
    r.sf_secondary_email,
    r.expected_grad_date_month,
    r.expected_grad_date_year,
    r.actual_end_date_month,
    r.actual_end_date_year,
    r.rn_graduated,
    r.es_graduated,
    r.tier,
    r.advising_provider,
    r.postsec_advisor,
    r.most_recent_iep_date,
    r.middle_school_attended,
    r.high_school_graduated_from,
    r.ktc_cohort,
    r.currently_enrolled_school,
    r.current_college_cumulative_gpa,
    r.primary_phone,
    r.secondary_phone,
    r.career_conversation_notes,
    r.is_resume_score,
    r.is_linkedin,
    r.is_mock_interview_or_prep,
    r.is_professional_references_list,
    r.is_job_search_template,
    r.is_cover_letter_template,
    r.is_work_samples,
    r.cc1_count,
    r.cc2_count,
    r.cc3_count,
    r.cc4_count,
    r.cc5_count,
    r.cc_total_count,
    r.career_conversation_items_complete_count,
    r.is_career_conversation_complete,

    sp.survey_id,
    sp.survey_title,
    sp.response_id,
    sp.response_date_submitted,
    sp.respondent_user_principal_name,
    sp.after_grad,
    sp.alumni_dob,
    sp.alumni_email,
    sp.alumni_phone,
    sp.cell_number,
    sp.company,
    sp.complete_program,
    sp.debt_amount,
    sp.debt_binary,
    sp.first_name,
    sp.grad_school_major,
    sp.grad_school_name,
    sp.highest_level_of_education,
    sp.job_sat,
    sp.last_name,
    sp.linkedin,
    sp.linkedin_link,
    sp.not_pursuing_plan,
    sp.reenrollment,
    sp.role,
    sp.satisfied_program,
    sp.search_focus,
    sp.annual_income,
    sp.benefits,
    sp.annual_income_clean,

    if(
        r.expected_grad_date_month < 7,
        concat('Spring ', r.expected_grad_date_year),
        concat('Fall ', r.expected_grad_date_year)
    ) as season_label_expected,

    if(
        r.actual_end_date_month < 7,
        concat('Spring ', r.actual_end_date_year),
        concat('Fall ', r.actual_end_date_year)
    ) as season_label,

    if(r.contact_id is null, true, false) as is_unmatched_response,

    if(r.most_recent_iep_date is not null, true, false) as is_special_education,

    if(r.advising_provider = 'KIPP NYC', 'Collab', r.contact_owner_name) as advisor,

    if(
        r.contact_id is not null,
        row_number() over (
            partition by r.contact_id
            order by
                /* bulk_add wins; intended only for alumni with no survey response */
                if(sp.survey_id = 'bulk_add', 0, 1), sp.response_date_submitted desc
        ),
        null
    ) as rn_respondent,
from roster as r
full join
    survey_filtered as sp
    on r.rn_graduated = 1
    and (
        r.sf_email = sp.respondent_user_principal_name
        or r.sf_secondary_email = sp.respondent_user_principal_name
        or r.reconciliation_response_id = sp.response_id
        or r.contact_id = sp.respondent_salesforce_id
    )
