with
    eligible_roster as (
        select
            sr.employee_number,
            sr.assignment_status,
            sr.formatted_name as preferred_name_lastfirst,
            sr.home_business_unit_name as business_unit,
            sr.home_work_location_name as `location`,
            sr.home_department_name as department,
            sr.job_title,
            sr.worker_original_hire_date as hire_date,
            sr.mail,
            sr.google_email,
            sr.reports_to_employee_number as report_to_employee_number,
            sr.reports_to_formatted_name as report_to_preferred_name_lastfirst,
            sr.survey_last_submitted_timestamp,
            sr.race_ethnicity,
            sr.gender_identity,
            sr.community_grew_up,
            sr.community_professional_exp,
            sr.languages_spoken,
            sr.additional_languages,
            sr.level_of_education,
            sr.undergraduate_school,
            sr.years_exp_outside_kipp,
            sr.years_teaching_in_njfl,
            sr.years_teaching_outside_njfl,
            sr.alumni_status,
            sr.relay_status,
            sr.path_to_education,

            mgr.home_work_location_name as manager_work_location,

            replace(
                lower(regexp_extract(sr.user_principal_name, r'[^@]+')), '-', ''
            ) as username,
            replace(
                lower(regexp_extract(sr.sam_account_name, r'[^@]+')), '-', ''
            ) as samaccountname,

            if(
                sr.home_work_location_grade_band in ('ES', 'MS', 'HS'),
                'School-based',
                'Not+school-based'
            ) as loc_type,
        from {{ ref("int_people__staff_roster") }} as sr
        left join
            {{ ref("int_people__staff_roster") }} as mgr
            on sr.reports_to_employee_number = mgr.employee_number
        where sr.assignment_status in ('Active', 'Leave')
    )

/* Performance Management: Middle of Year */
select
    r.employee_number,
    r.assignment_status,
    r.preferred_name_lastfirst,
    r.business_unit,
    r.location,
    r.department,
    r.job_title,
    r.hire_date,
    r.mail,
    r.google_email,
    r.report_to_employee_number,
    r.report_to_preferred_name_lastfirst,
    r.samaccountname,
    r.username,

    rt.academic_year,
    rt.code as survey_round,
    rt.is_current,

    'Performance Management: Middle of Year' as survey,
    'Complete your MOY ratings' as `assignment`,

    replace(
        concat(
            'https://docs.google.com/forms/d/e/',
            '1FAIpQLSfispp2-GdaSwHJX5aRpBvVLnmYZBusLwg8MbAV2UR14j4hZw',
            '/viewform',
            '?usp=pp_url',
            /* Name + ID */
            '&entry.2128702719=',
            r.preferred_name_lastfirst,
            ' - ',
            coalesce(r.location, ''),
            ' (',
            ltrim(cast(r.employee_number as string format '999999')),
            ')',
            /* Change Management */
            '&entry.1558405518=',
            /* to-do: add BOY response */,
            /* Continuous Learning */
            '&entry.658094708=',
            /* to-do: add BOY response */,
            /* Critical Consciousness*/
            '&entry.1268543371=',
            /* to-do: add BOY response */,
            /* Developing+and+Managing+People */
            '&entry.925741586=',
            replace(
                coalesce(r.community_professional_exp, ''), ', ', '&entry.1197736651='
            ),
            /* languages spoken */
            '&entry.1551531542=',
            replace(coalesce(r.languages_spoken, ''), ',', '&entry.1551531542='),
            /* additional languages */
            '&entry.53823493=',
            coalesce(r.additional_languages, ''),
            /* level of education */
            '&entry.928329961=',
            coalesce(r.level_of_education, ''),
            /* undergraduate school */
            '&entry.844913390=',
            -- trunk-ignore(sqlfluff/CV10)
            coalesce(replace(r.undergraduate_school, "'", ""), ''),
            /* years outside of kipp */
            '&entry.2136123484=',
            coalesce(cast(r.years_exp_outside_kipp as string), ''),
            /* years teaching njfl */
            '&entry.2038589601=',
            coalesce(cast(r.years_teaching_in_njfl as string), ''),
            /* years outside njfl */
            '&entry.1922494504=',
            coalesce(cast(r.years_teaching_outside_njfl as string), ''),
            /* alumni status */
            '&entry.1216415935=',
            coalesce(r.alumni_status, ''),
            /* relay status */
            '&entry.553510009=',
            coalesce(r.relay_status, ''),
            /* path to education' */
            '&entry.1130804124=',
            replace(coalesce(r.path_to_education, ''), ',', '&entry.1130804124='),
            if(
                r.job_title in (
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
    ) as link,
from eligible_roster as r
inner join
    {{ ref("stg_reporting__terms") }} as rt
    on rt.name = 'Staff Info & Certification Update'

