{{ config(enabled=False) }}
with
    alumni_data as (
        select
            e.student_c,
            e. [name],
            e.pursuing_degree_type_c,
            e.type_c,
            e.start_date_c,
            e.actual_end_date_c,
            e.major_c,
            e.status_c,
            row_number() over (
                partition by e.student_c order by e.actual_end_date_c desc
            ) as rn_latest,
            c.first_name,
            c.last_name,
            c. [email],
            c.secondary_email_c as [email2],
            c.kipp_ms_graduate_c,
            c.kipp_hs_graduate_c,
            c.kipp_hs_class_c,
            c.college_match_display_gpa_c,
            c.kipp_region_name_c,
            c. [description],
            c.gender_c,
            c.ethnicity_c
        from alumni.enrollment_c as e
        inner join alumni.contact as c on (e.student_c = c.id)
        where e.status_c = 'Graduated' and e.is_deleted = 0
    ),
    survey_pivot as (
        select
            respondent_salesforce_id,
            date_submitted,
            survey_response_id,
            survey_title,
            survey_id,
            [first_name],
            [last_name],
            [after_grad],
            [alumni_dob],
            [alumni_email],
            [alumni_phone],
            [cur_1],
            [cur_2],
            [cur_3],
            [cur_4],
            [cur_5],
            [cur_6],
            [cur_7],
            [cur_8],
            [cur_9],
            [cur_10],
            [job_sat],
            [ladder],
            [covid],
            [linkedin],
            [linkedin_link],
            [debt_binary],
            [debt_amount],
            [annual_income]
        from
            (
                select
                    respondent_salesforce_id,
                    question_shortname,
                    answer,
                    survey_title,
                    date_submitted,
                    survey_response_id,
                    survey_id
                from surveygizmo.survey_detail
                where survey_id = 6734664
            ) as sub pivot (
                max(answer) for question_shortname in (
                    [first_name],
                    [last_name],
                    [alumni_dob],
                    [alumni_email],
                    [alumni_phone],
                    [after_grad],
                    [cur_1],
                    [cur_2],
                    [cur_3],
                    [cur_4],
                    [cur_5],
                    [cur_6],
                    [cur_7],
                    [cur_8],
                    [cur_9],
                    [cur_10],
                    [job_sat],
                    [ladder],
                    [covid],
                    [linkedin],
                    [linkedin_link],
                    [debt_binary],
                    [debt_amount],
                    [annual_income]
                )
            ) as p
    ),
    weight_denominator as (
        select survey_id, sum(cast(answer_value as float)) as answer_total
        from surveygizmo.survey_detail
        where
            survey_id = 6734664
            and question_shortname in (
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
        group by survey_id
    ),
    weight_table as (
        select
            s.question_shortname,
            (sum(cast(s.answer_value as float)) / a.answer_total) * 10 as item_weight
        from weight_denominator as a
        left join
            surveygizmo.survey_detail as s
            on (
                a.survey_id = s.survey_id
                and s.survey_id = 6734664
                and s.question_shortname in (
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
        group by s.question_shortname, a.answer_total
    ),
    weight_pivot as (
        select
            '6734664' as survey_id,
            [imp_1],
            [imp_2],
            [imp_3],
            [imp_4],
            [imp_5],
            [imp_6],
            [imp_7],
            [imp_8],
            [imp_9],
            [imp_10]
        from
            weight_table pivot (
                max(item_weight) for question_shortname in (
                    [imp_1],
                    [imp_2],
                    [imp_3],
                    [imp_4],
                    [imp_5],
                    [imp_6],
                    [imp_7],
                    [imp_8],
                    [imp_9],
                    [imp_10]
                )
            ) as p
    )
select
    s.survey_title,
    s.survey_response_id,
    s.date_submitted,
    s.respondent_salesforce_id,
    s.first_name,
    s.last_name,
    s.alumni_phone,
    s.alumni_email,
    s.after_grad,
    s.alumni_dob,
    s.job_sat,
    s.ladder,
    s.covid,
    s.linkedin,
    s.linkedin_link,
    s.debt_binary,
    s.debt_amount,
    s.annual_income,
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
        -- trunk-ignore(sqlfluff/LT05)
        s.cur_1 * p.imp_1
        + s.cur_2 * p.imp_2
        + s.cur_3 * p.imp_3
        + s.cur_4 * p.imp_4
        + s.cur_5 * p.imp_5
        + s.cur_6 * p.imp_6
        + s.cur_7 * p.imp_7
        + s.cur_8 * p.imp_8
        + s.cur_9 * p.imp_9
        + s.cur_10 * p.imp_10
    )
    / 10.0 as overall_quality,
    a. [name],
    a.kipp_ms_graduate_c,
    a.kipp_hs_graduate_c,
    a.kipp_hs_class_c,
    a.college_match_display_gpa_c,
    a.kipp_region_name_c,
    a. [description],
    a.gender_c,
    a.ethnicity_c,
    a.pursuing_degree_type_c,
    a.type_c,
    a.start_date_c,
    a.actual_end_date_c,
    a.major_c,
    a.status_c
from survey_pivot as s
left join weight_pivot as p on (s.survey_id = p.survey_id)
left join
    alumni_data as a
    on ((s.alumni_email = a.email or s.alumni_email = a.email2) and a.rn_latest = 1)
left join
    surveygizmo.survey_response_disqualified as dq
    on (s.survey_id = dq.survey_id and s.survey_response_id = dq.id)
where dq.id is null
