with
    survey_reconciliation_raw as (
        select response_id, item_title, text_value, create_timestamp,
        from {{ ref("base_google_forms__form_responses") }}
        where
            form_id = '1oUBls4Kaj0zcbQyeWowe8Es1BFqunolAPEamzT6enQs'
            and item_title in ('Survey response ID', 'Salesforce contact ID')
    ),

    survey_reconciliation as (
        select
            survey_response_id,
            sf_contact_id,

            row_number() over (
                partition by survey_response_id order by create_timestamp desc
            ) as rn_response_id,
        from
            survey_reconciliation_raw pivot (
                max(text_value) for item_title in (
                    'Survey response ID' as survey_response_id,
                    'Salesforce contact ID' as sf_contact_id
                )
            )
    ),

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
        from {{ ref("stg_kippadb__internships_programs") }} as p
        inner join
            {{ ref("stg_kippadb__account") }} as a
            on p.program_or_organization_name = a.id
        where
            p.internship_or_program_type = 'College Program'
            and p.application_status not in ('Not Matched', 'Wait-listed')
        group by all

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

            p.college_programs,
            p.is_basta,
            p.is_braven,

            lower(r.contact_email) as sf_email,
            lower(r.contact_secondary_email) as sf_secondary_email,
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
        left join programs as p on r.contact_id = p.student
        where
            r.ktc_status in ('HSG', 'TAF')
            and r.ktc_cohort <= {{ var("current_academic_year") }}
            and r.contact_id is not null
    ),

    survey_union as (
        select
            ri.response_date_submitted,
            ri.respondent_salesforce_id,

            'Alchemer survey' as survey_title,
            sr.question_short_name,
            sr.response_string_value,

            cast(ri.survey_id as string) as survey_id,
            cast(ri.response_id as string) as response_id,
            lower(ri.respondent_user_principal_name) as respondent_user_principal_name,
        /* hardcode disabled model */
        from kipptaf_surveys.int_surveys__response_identifiers as ri
        inner join
            /* hardcode disabled model */
            kipptaf_alchemer.base_alchemer__survey_results as sr
            on ri.survey_id = sr.survey_id
            and ri.response_id = sr.response_id
        where ri.survey_id = 6734664  /* 'KIPP Forward Career Launch Survey' */

        union all

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

            coalesce(annual_income, annual_income_alt) as annual_income,
            coalesce(benefits, benefits_alt) as benefits,
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

    case
        when sp.annual_income like '%-%'
        then
            cast(
                replace(
                    regexp_extract(sp.annual_income, r'\$([0-9,]+) -'), ',', ''
                ) as float64
            )
        when sp.annual_income like '%or more%'
        then
            cast(
                replace(
                    regexp_extract(sp.annual_income, r'\$([0-9,]+) or more'), ',', ''
                ) as float64
            )
        else
            cast(
                replace(
                    regexp_extract(sp.annual_income, r'\$([0-9,]+)'), ',', ''
                ) as float64
            )
    end as annual_income_clean,

    if(
        r.actual_end_date_month < 7,
        concat('Spring ', r.expected_grad_date_month),
        concat('Fall ', r.expected_grad_date_year)
    ) as season_label_expected,
    if(
        r.actual_end_date_month < 7,
        concat('Spring ', r.actual_end_date_year),
        concat('Fall ', r.actual_end_date_year)
    ) as season_label,
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
