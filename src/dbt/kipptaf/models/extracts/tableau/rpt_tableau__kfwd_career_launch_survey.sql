with
    survey_reconciliation as (
        select
            survey_response_id as response_id,
            sf_contact_id,

            row_number() over (
                partition by survey_response_id order by date_submitted desc
            ) as rn_response_id,
        from
            (
                select date_submitted, answer, question_title,
                from {{ ref("int_surveys__survey_responses") }}
                where
                    survey_title
                    = 'Career Launch Survey invalid response reconciliation'
            ) pivot (
                max(answer) for question_title in (
                    'Survey response ID' as survey_response_id,
                    'Salesforce contact ID' as sf_contact_id
                )
            )
    ),

    alumni_data as (
        select
            r.contact_id as student,
            r.first_name as sf_first_name,
            r.last_name as sf_last_name,
            r.lastfirst as sf_lastfirst,
            r.contact_email as sf_email,
            r.contact_secondary_email as sf_secondary_email,
            r.ktc_cohort as kipp_hs_class,
            r.contact_kipp_hs_graduate as kipp_hs_graduate,
            r.contact_college_match_display_gpa as college_match_display_gpa,
            r.contact_kipp_region_name as kipp_region_name,
            r.contact_description as description,
            r.contact_gender as gender,
            r.contact_ethnicity as ethnicity,
            r.contact_expected_college_graduation as expected_college_graduation,

            e.name,
            e.pursuing_degree_type,
            e.type,
            e.start_date,
            e.actual_end_date,
            e.major,
            e.status,

            a.adjusted_6_year_minority_graduation_rate as ecc,
            a.name as institution,

            extract(month from e.actual_end_date) as actual_end_date_month,
            extract(year from e.actual_end_date) as actual_end_date_year,

            if(
                e.name is not null,
                row_number() over (
                    partition by r.contact_id order by e.actual_end_date desc
                ),
                1
            ) as rn_latest,
        from {{ ref("int_kippadb__roster") }} as r
        left join
            {{ ref("stg_kippadb__enrollment") }} as e
            on r.contact_id = e.student
            and e.type not in ('High School', 'Middle School')
        left join {{ ref("stg_kippadb__account") }} as a on e.school = a.id
        where
            r.contact_id is not null
            and r.ktc_cohort < {{ var("current_academic_year") }} + 1
    ),

    survey_data as (
        select
            safe_cast(ri.survey_id as string) as survey_id,
            safe_cast(ri.response_id as string) as response_id,
            ri.response_date_submitted,
            ri.respondent_salesforce_id,
            ri.respondent_user_principal_name,

            sr.survey_title,
            sr.question_short_name,
            sr.response_string_value,
        from {{ ref("int_surveys__response_identifiers") }} as ri
        inner join
            {{ ref("base_alchemer__survey_results") }} as sr
            on ri.survey_id = sr.survey_id
            and ri.response_id = sr.response_id
        where ri.survey_id = 6734664  -- 'KIPP Forward Career Launch Survey'

        union all

        select
            safe_cast(fr.form_id as string) as survey_id,
            safe_cast(fr.response_id as string) as response_id,
            safe_cast(fr.last_submitted_time as timestamp) as response_date_submitted,
            null as respondent_salesforce_id,
            fr.respondent_email as respondent_user_principal_name,

            fr.info_document_title as survey_title,
            fr.item_abbreviation as question_short_name,
            fr.text_value as response_string_value,
        from {{ ref("base_google_forms__form_responses") }} as fr
        where form_id = '1qfXBcMxp9712NEnqOZS2S-Zm_SAvXRi_UndXxYZUZho'
    -- 'KIPP Forward Career Launch Survey'
    ),

    survey_pivot as (
        select
            survey_id,
            survey_title,
            response_id,
            response_date_submitted,
            respondent_salesforce_id,
            respondent_user_principal_name,

            {# pivot cols #}
            first_name,
            last_name,
            after_grad,
            alumni_dob,
            alumni_email as survey_alumni_email,
            email as survey_email,
            alumni_phone,
            job_sat,
            ladder,
            covid,
            linkedin,
            linkedin_link,
            debt_binary,
            debt_amount,
            annual_income,
            finish_program,
            complete_program,
            reenrollment,
            search_focus,
            company,
            role,

            safe_cast(cur_1 as numeric) as cur_1,
            safe_cast(cur_2 as numeric) as cur_2,
            safe_cast(cur_3 as numeric) as cur_3,
            safe_cast(cur_4 as numeric) as cur_4,
            safe_cast(cur_5 as numeric) as cur_5,
            safe_cast(cur_6 as numeric) as cur_6,
            safe_cast(cur_7 as numeric) as cur_7,
            safe_cast(cur_8 as numeric) as cur_8,
            safe_cast(cur_9 as numeric) as cur_9,
            safe_cast(cur_10 as numeric) as cur_10,
        from
            survey_data pivot (
                max(response_string_value) for question_short_name in (
                    'first_name',
                    'last_name',
                    'alumni_dob',
                    'alumni_email',
                    'email',
                    'alumni_phone',
                    'after_grad',
                    'cur_1',
                    'cur_2',
                    'cur_3',
                    'cur_4',
                    'cur_5',
                    'cur_6',
                    'cur_7',
                    'cur_8',
                    'cur_9',
                    'cur_10',
                    'job_sat',
                    'ladder',
                    'covid',
                    'linkedin',
                    'linkedin_link',
                    'debt_binary',
                    'debt_amount',
                    'annual_income',
                    'finish_program',
                    'complete_program',
                    'reenrollment',
                    'search_focus',
                    'company',
                    'role'

                )
            )
    ),

    weight_questions as (
        select
            question_short_name,
            safe_cast(response_string_value as numeric) as response_float_value,
        from survey_data
        where
            question_short_name in (
                'imp_1',
                'imp_2',
                'imp_3',
                'imp_4',
                'imp_5',
                'imp_6',
                'imp_7',
                'imp_8',
                'imp_9',
                'imp_10'
            )
    ),

    weight_denominator as (
        select sum(response_float_value) as answer_total, from weight_questions
    ),

    weight_table as (
        select
            s.question_short_name,
            (sum(s.response_float_value) / a.answer_total) * 10 as item_weight,
        from weight_questions as s
        cross join weight_denominator as a
        group by s.question_short_name, a.answer_total
    ),

    weight_pivot as (
        select imp_1, imp_2, imp_3, imp_4, imp_5, imp_6, imp_7, imp_8, imp_9, imp_10,
        from
            weight_table pivot (
                max(item_weight) for question_short_name in (
                    'imp_1',
                    'imp_2',
                    'imp_3',
                    'imp_4',
                    'imp_5',
                    'imp_6',
                    'imp_7',
                    'imp_8',
                    'imp_9',
                    'imp_10'
                )
            )
    ),

    survey_weighted as (
        select
            s.*,

            /* weighted satisfaction scores based on relative importance of each*/
            s.cur_1 * p.imp_1 as level_pay_quality,
            s.cur_2 * p.imp_2 as stable_pay_quality,
            s.cur_3 * p.imp_3 as stable_hours_quality,
            s.cur_4 * p.imp_4 as control_hours_location_quality,
            s.cur_5 * p.imp_5 as job_security_quality,
            s.cur_6 * p.imp_6 as benefits_quality,
            s.cur_7 * p.imp_7 as advancement_quality,
            s.cur_8 * p.imp_8 as enjoyment_quality,
            s.cur_9 * p.imp_9 as purpose_quality,
            s.cur_10 * p.imp_10 as power_quality,
            (
                (s.cur_1 * p.imp_1)
                + (s.cur_2 * p.imp_2)
                + (s.cur_3 * p.imp_3)
                + (s.cur_4 * p.imp_4)
                + (s.cur_5 * p.imp_5)
                + (s.cur_6 * p.imp_6)
                + (s.cur_7 * p.imp_7)
                + (s.cur_8 * p.imp_8)
                + (s.cur_9 * p.imp_9)
                + (s.cur_10 * p.imp_10)
            )
            / 10.0 as overall_quality,
        from survey_pivot as s
        cross join weight_pivot as p
    )

select
    ad.*,

    sw.*,

    case
        when ad.actual_end_date_month between 1 and 6
        then concat('Spring ', ad.actual_end_date_year)
        when ad.actual_end_date_month between 7 and 12
        then concat('Fall ', ad.actual_end_date_year)
    end as season_label,

    row_number() over (
        partition by ad.student order by sw.response_date_submitted desc
    ) as rn_survey,
from alumni_data as ad
left join
    survey_reconciliation as sr
    on ad.student = sr.sf_contact_id
    and sr.rn_response_id = 1
left join
    survey_weighted as sw
    on (
        ad.sf_email = sw.respondent_user_principal_name
        or ad.sf_secondary_email = sw.respondent_user_principal_name
        or sr.response_id = sw.response_id
    )
where ad.rn_latest = 1
