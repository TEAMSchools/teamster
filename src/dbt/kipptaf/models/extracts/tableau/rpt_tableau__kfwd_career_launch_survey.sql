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

    alumni_data as (
        select
            e.student,
            e.name,
            e.pursuing_degree_type,
            e.type,
            e.start_date,
            e.actual_end_date,
            e.major,
            e.status,

            c.first_name as sf_first_name,
            c.last_name as sf_last_name,
            c.kipp_ms_graduate,
            c.kipp_hs_graduate,
            c.kipp_hs_class,
            c.college_match_display_gpa,
            c.kipp_region_name,
            c.description,
            c.gender,
            c.ethnicity,

            a.adjusted_6_year_minority_graduation_rate as ecc,
            a.name as institution,

            lower(c.email) as sf_email,
            lower(c.secondary_email) as sf_secondary_email,

            extract(month from e.actual_end_date) as actual_end_date_month,
            extract(year from e.actual_end_date) as actual_end_date_year,

            row_number() over (
                partition by e.student order by e.actual_end_date desc
            ) as rn_latest,
        from {{ ref("stg_kippadb__enrollment") }} as e
        inner join {{ ref("stg_kippadb__contact") }} as c on e.student = c.id
        left join {{ ref("stg_kippadb__account") }} as a on e.school = a.id
        where e.status = 'Graduated' and e.type not in ('High School', 'Middle School')
    ),

    survey_data as (
        select
            ri.response_date_submitted,
            ri.respondent_salesforce_id,

            sr.survey_title,
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

            fr.info_document_title as survey_title,
            fr.item_abbreviation as question_short_name,
            fr.text_value as response_string_value,

            cast(fr.form_id as string) as survey_id,
            cast(fr.response_id as string) as response_id,
            lower(fr.respondent_email) as respondent_user_principal_name,
        from {{ ref("base_google_forms__form_responses") }} as fr
        /* 'KIPP Forward Career Launch Survey' */
        where form_id = '1qfXBcMxp9712NEnqOZS2S-Zm_SAvXRi_UndXxYZUZho'
    ),

    survey_pivot as (
        select
            survey_id,
            survey_title,
            response_id,
            response_date_submitted,
            respondent_salesforce_id,
            respondent_user_principal_name,

            /* pivot cols */
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
            `role`,

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
    sw.*,

    ad.*,

    case
        when ad.actual_end_date_month between 1 and 6
        then concat('Spring ', ad.actual_end_date_year)
        when ad.actual_end_date_month between 7 and 12
        then concat('Fall ', ad.actual_end_date_year)
    end as season_label,
from survey_weighted as sw
left join
    survey_reconciliation as sr
    on sw.response_id = sr.survey_response_id
    and sr.rn_response_id = 1
full join
    alumni_data as ad
    on ad.rn_latest = 1
    and (
        sw.respondent_user_principal_name = ad.sf_email
        or sw.respondent_user_principal_name = ad.sf_secondary_email
        or sr.sf_contact_id = ad.student
    )
