select  -- noqa: disable=ST06
    employee_number,
    status_value,
    business_unit_assigned_name as business_unit,

    coalesce(preferred_name_given_name, legal_name_given_name) as first_name,
    coalesce(preferred_name_family_name, legal_name_family_name) as last_name,

    home_work_location_name as work_location,
    job_title,
    worker_original_hire_date as hire_date,
    communication_business_email as business_email,

    concat(
        coalesce(preferred_name_given_name, legal_name_given_name),
        ' ',
        coalesce(preferred_name_family_name, legal_name_family_name),
        ' - ',
        home_work_location_name,
        ' (',
        employee_number,
        ')'
    ) as respondent_response_name,

    regexp_extract(communication_business_email, r'^(.*?)@') as worker_username,

    survey_last_submitted_timestamp as last_submitted_time,
    race_ethnicity as last_submitted_race_ethnicity,
    gender_identity as last_submitted_gender_identity,
    community_grew_up as last_submitted_community_grew_up,
    community_professional_exp as last_submitted_community_professional_experience,
    languages_spoken as last_submitted_languages_spoken,
    level_of_education as last_submitted_level_of_education,
    undergraduate_school as last_submitted_undergraduate_school,
    years_exp_outside_kipp as last_submitted_years_exp_outside_kipp,
    years_teaching_in_njfl as last_submitted_years_teaching_in_njfl,
    years_teaching_outside_njfl as last_submitted_years_teaching_outside_njfl,
    alumni_status as last_submitted_alumni_status,
    relay_status as last_submitted_relay_status,
    path_to_education as last_submitted_path_to_education,

    replace(
        concat(
            'https://docs.google.com/forms/d/e/',
            '1FAIpQLSdxkHheRKAQQL5WjhbWwwGiC34weMX1LKcIDAt94cR78csfXw',
            '/viewform',
            '?usp=pp_url',
            '&entry.1744062351=',
            coalesce(preferred_name_given_name, legal_name_given_name),
            ' ',
            coalesce(preferred_name_family_name, legal_name_family_name),
            ' - ',
            coalesce(home_work_location_name, ''),
            ' (',
            ltrim(cast(employee_number as string format '999999')),  -- Name + ID
            ')',
            -- Race/Ethnicity
            '&entry.1688914034=',
            replace(coalesce(race_ethnicity, ''), ', ', '&entry.1688914034='),
            -- gender identity
            '&entry.600247632=',
            coalesce(gender_identity, ''),
            -- Community Grew Up
            '&entry.2102492257=',
            replace(coalesce(community_grew_up, ''), ', ', '&entry.2102492257='),
            -- Community Work Exp
            '&entry.1197736651=',
            replace(
                coalesce(community_professional_exp, ''), ', ', '&entry.1197736651='
            ),
            -- languages spoken
            '&entry.1551531542=',
            replace(coalesce(languages_spoken, ''), ',', '&entry.1551531542='),
            -- additional languages
            '&entry.53823493=',
            coalesce(additional_languages, ''),
            -- level of education
            '&entry.928329961=',
            coalesce(level_of_education, ''),
            -- undergraduate school
            '&entry.844913390=',
            coalesce(undergraduate_school, ''),
            -- years outside of kipp
            '&entry.2136123484=',
            coalesce(cast(years_exp_outside_kipp as string), ''),
            -- years teaching njfl
            '&entry.2038589601=',
            coalesce(cast(years_teaching_in_njfl as string), ''),
            -- years outside njfl
            '&entry.1922494504=',
            coalesce(cast(years_teaching_outside_njfl as string), ''),
            -- alumni status
            '&entry.1216415935=',
            coalesce(alumni_status, ''),
            -- relay status
            '&entry.553510009=',
            coalesce(relay_status, ''),
            -- path to education'
            '&entry.1130804124=',
            replace(coalesce(path_to_education, ''), ',', '&entry.1130804124='),
            if(
                job_title in (
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
from {{ ref("base_people__staff_roster") }}
