with
    survey_reconciliation as (
        select
            answer_survey_response_id as survey_response_id,
            sf_contact_id,

            row_number() over (
                partition by survey_response_id order by date_submitted desc
            ) as rn_response_id,
        from
            {{ ref("int_surveys__survey_responses") }} pivot (
                max(answer) for question_title in (
                    'Survey response ID' as answer_survey_response_id,
                    'Salesforce contact ID' as sf_contact_id
                )
            )
        where survey_title = 'Career Launch Survey invalid response reconciliation'
    ),

    roster as (
        select
            r.contact_id,
            r.contact_first_name as sf_first_name,
            r.contact_last_name as sf_last_name,
            r.contact_kipp_ms_graduate,
            r.contact_kipp_hs_graduate,
            r.contact_kipp_hs_class,
            r.contact_college_match_display_gpa,
            r.contact_kipp_region_name,
            r.contact_description,
            r.contact_gender,
            r.contact_ethnicity,
            r.contact_expected_college_graduation as expected_college_grad_date,
            r.contact_actual_college_graduation_date as actual_college_grad_date,

            e.pursuing_degree_type,
            e.type,
            e.start_date,
            e.actual_end_date,
            e.major,
            e.status,

            a.adjusted_6_year_minority_graduation_rate as ecc,
            a.name as institution,

            sr.survey_response_id as reconciliation_response_id,

            lower(r.contact_email) as sf_email,
            lower(r.contact_secondary_email) as sf_secondary_email,
            extract(month from e.actual_end_date) as actual_end_date_month,
            extract(year from e.actual_end_date) as actual_end_date_year,
            if(
                e.status = 'Graduated',
                row_number() over (
                    partition by e.student order by e.actual_end_date asc
                ),
                1
            ) as rn_graduated,
        from {{ ref("int_kippadb__roster") }} as r
        left join
            {{ ref("stg_kippadb__enrollment") }} as e
            on r.contact_id = e.student
            and e.type not in ('High School', 'Middle School')
            and e.status = 'Graduated'
        left join {{ ref("stg_kippadb__account") }} as a on e.school = a.id
        left join
            survey_reconciliation as sr
            on r.contact_id = sr.sf_contact_id
            and sr.rn_response_id = 1
        where
            r.ktc_status in ('HSG', 'TAF')
            and r.ktc_cohort <= {{ var("current_academic_year") }}
    ),

    survey_union as (
        select
            safe_cast(fr.last_submitted_time as timestamp) as response_date_submitted,
            null as respondent_salesforce_id,
            'Google Form v1' as survey_title,
            fr.item_abbreviation as question_short_name,
            fr.text_value as response_string_value,
            cast(fr.form_id as string) as survey_id,
            cast(fr.response_id as string) as response_id,
            lower(fr.respondent_email) as respondent_user_principal_name,
        from {{ ref("base_google_forms__form_responses") }} as fr
        /* 'KIPP Forward Career Launch Survey - OLD' */
        where fr.form_id = '1qfXBcMxp9712NEnqOZS2S-Zm_SAvXRi_UndXxYZUZho'

        union all

        select
            safe_cast(fr.last_submitted_time as timestamp) as response_date_submitted,
            null as respondent_salesforce_id,
            'Google Form v2' as survey_title,
            fr.item_abbreviation as question_short_name,
            fr.text_value as response_string_value,
            cast(fr.form_id as string) as survey_id,
            cast(fr.response_id as string) as response_id,
            lower(fr.respondent_email) as respondent_user_principal_name,
        from {{ ref("base_google_forms__form_responses") }} as fr
        /* 'KIPP Forward Career Launch Survey' */
        where fr.form_id = '1c4SLP61YIVnUUvRl_IUdFuLXdtI1Vsq9OE3Jrz3HR0U'
    ),

    survey_pivot as (
        select
            survey_id,
            survey_title,
            response_id,
            response_date_submitted,
            respondent_user_principal_name,

            /* pivot cols */
            after_grad,
            alumni_dob,
            alumni_email,
            alumni_phone,
            coalesce(annual_income, annual_income_alt) as annual_income,
            coalesce(benefits, benefits_alt) as benefits,
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
            role,
            satisfied_program,
            search_focus,
        from
            survey_union pivot (
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
                    'email',
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
    )

select
    r.*,

    sp.*,

    if(r.contact_id is null, true, false) as is_unmatched_response,
    if(
        r.contact_id is not null,
        row_number() over (
            partition by r.contact_id order by sp.response_date_submitted desc
        ),
        null
    ) as rn_respondent,
from roster as r
full join
    survey_pivot as sp
    on r.rn_graduated = 1
    and (
        r.sf_email = sp.respondent_user_principal_name
        or r.sf_secondary_email = sp.respondent_user_principal_name
        or r.reconciliation_response_id = sp.response_id
    )
