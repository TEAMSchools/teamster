select
    w.employee_number,
    w.status_value,
    w.business_unit_assigned_name as business_unit,
    coalesce(w.preferred_name_given_name, w.legal_name_given_name) as first_name,
    coalesce(w.preferred_name_family_name, w.legal_name_family_name) as last_name,
    w.home_work_location_name as work_location,
    w.job_title,
    w.worker_original_hire_date as hire_date,
    w.communication_business_email as business_email,
    concat(
        coalesce(w.preferred_name_given_name, w.legal_name_given_name),
        ' ',
        coalesce(w.preferred_name_family_name, w.legal_name_family_name),
        ' - ',
        w.home_work_location_name,
        ' (',
        w.employee_number,
        ')'
    ) as respondent_response_name,
    regexp_extract(w.communication_business_email, r'^(.*?)@') as worker_username,

    s.last_submitted_time,
    s.race_ethnicity as last_submitted_race_ethnicity,
    s.gender_identity as last_submitted_gender_identity,
    s.community_grew_up as last_submitted_community_grew_up,
    s.community_professional_exp as last_submitted_community_professional_experience,
    s.languages_spoken as last_submitted_languages_spoken,
    s.level_of_education as last_submitted_level_of_education,
    s.undergraduate_school as last_submitted_undergraduate_school,
    s.years_exp_outside_kipp as last_submitted_years_exp_outside_kipp,
    s.years_teaching_in_njfl as last_submitted_years_teaching_in_njfl,
    s.years_teaching_outside_njfl as last_submitted_years_teaching_outside_njfl,
    s.alumni_status as last_submitted_alumni_status,
    s.relay_status as last_submitted_relay_status,
    s.path_to_education as last_submitted_path_to_education,
    replace(
        concat(
            'https://docs.google.com/forms/d/e/',
            '1FAIpQLSdxkHheRKAQQL5WjhbWwwGiC34weMX1LKcIDAt94cR78csfXw',
            '/viewform',
            '?usp=pp_url',
            '&entry.1744062351=',
            coalesce(w.preferred_name_given_name, w.legal_name_given_name),
            ' ',
            coalesce(w.preferred_name_family_name, w.legal_name_family_name),
            ' - ',
            coalesce(w.home_work_location_name, ''),
            ' (',
            ltrim(cast(w.employee_number as string format '999999')),  -- Name + ID
            ')',
            '&entry.1688914034=',
            replace(coalesce(w.race_ethnicity, ''), ', ', '&entry.1688914034='),  -- Race/Ethnicity
            '&entry.600247632=',
            coalesce(w.gender_identity, ''),  -- gender identity
            '&entry.2102492257=',
            replace(coalesce(w.community_grew_up, ''), ', ', '&entry.2102492257='),  -- Community Grew Up
            '&entry.1197736651=',
            replace(
                coalesce(w.community_professional_exp, ''), ', ', '&entry.1197736651='
            ),  -- Community Work Exp
            '&entry.1551531542=',
            replace(coalesce(w.languages_spoken, ''), ',', '&entry.1551531542='),  -- languages spoken
            '&entry.53823493=',
            coalesce(w.additional_languages, ''),  -- additional languages
            '&entry.928329961=',
            coalesce(w.level_of_education, ''),  -- level of education
            '&entry.844913390=',
            coalesce(w.undergraduate_school, ''),  -- undergraduate school
            '&entry.2136123484=',
            coalesce(cast(w.years_exp_outside_kipp as string), ''),  -- years outside of kipp
            '&entry.2038589601=',
            coalesce(cast(w.years_teaching_in_njfl as string), ''),  -- years teaching njfl
            '&entry.1922494504=',
            coalesce(cast(w.years_teaching_outside_njfl as string), ''),  -- years outside njfl
            '&entry.1216415935=',
            coalesce(w.alumni_status, ''),  -- alumni status
            '&entry.553510009=',
            coalesce(w.relay_status, ''),  -- relay status
            '&entry.1130804124=',
            replace(coalesce(w.path_to_education, ''), ',', '&entry.1130804124='),  -- path to education'
            if(
                w.job_title in (
                    'Teacher',
                    'Teacher ESL',
                    'Learning Specialist',
                    'Licensed Practical Nurse',
                    'Registered Nurse'
                ),
                '&entry.1444365185=Yes',
                ''
            )
        ),
        ' ',
        '+'
    ) as staff_info_update_personal_link,
from {{ ref("base_people__staff_roster") }} as w
left join
    {{ ref("int_surveys__staff_information_survey_pivot") }} as s
    on w.employee_number = s.employee_number
