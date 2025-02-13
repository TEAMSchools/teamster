-- trunk-ignore-begin(sqlfluff/LT05)
with
    eligible_roster as (
        select
            sr.employee_number,
            sr.assignment_status,
            sr.preferred_name_lastfirst,
            sr.business_unit_home_name as business_unit,
            sr.home_work_location_name as location,
            sr.department_home_name as department,
            sr.job_title,
            sr.worker_original_hire_date as hire_date,
            sr.mail,
            sr.google_email,
            sr.report_to_employee_number,
            sr.report_to_preferred_name_lastfirst,
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
        from {{ ref("base_people__staff_roster") }} as sr
        left join
            {{ ref("base_people__staff_roster") }} as mgr
            on sr.report_to_employee_number = mgr.employee_number
        where sr.assignment_status in ('Active', 'Leave')
    )

-- Staff Info and Cert
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

    'Staff Info & Certification Update' as survey,
    'Update Your Info' as `assignment`,

    replace(
        concat(
            'https://docs.google.com/forms/d/e/',
            '1FAIpQLSdxkHheRKAQQL5WjhbWwwGiC34weMX1LKcIDAt94cR78csfXw',
            '/viewform',
            '?usp=pp_url',
            /* Name + ID */
            '&entry.1744062351=',
            r.preferred_name_lastfirst,
            ' - ',
            coalesce(r.location, ''),
            ' (',
            ltrim(cast(r.employee_number as string format '999999')),
            ')',
            /* Race/Ethnicity */
            '&entry.1688914034=',
            replace(coalesce(r.race_ethnicity, ''), ', ', '&entry.1688914034='),
            /* gender identity */
            '&entry.600247632=',
            coalesce(r.gender_identity, ''),
            /* Community Grew Up */
            '&entry.2102492257=',
            replace(coalesce(r.community_grew_up, ''), ', ', '&entry.2102492257='),
            /* Community Work Exp */
            '&entry.1197736651=',
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

union all
-- Intent to Return
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

    'Intent to Return Survey' as survey,
    'Complete Intent to Return Survey' as `assignment`,

    'https://docs.google.com/forms/d/e/1FAIpQLSerLfKQhyeRGIWNBRTyYHfefnuCmveUCKQ-nt3qaeJrq96w3A/viewform?usp=pp_url&entry.927104043='
    as link,

from eligible_roster as r
inner join
    {{ ref("stg_reporting__terms") }} as rt on rt.name = 'Intent to Return Survey'
where r.business_unit <> 'KIPP TEAM and Family Schools Inc.'

union all
-- KTAF Support Survey
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

    'KTAF Support Survey' as survey,
    'Complete KTAF Support Survey' as `assignment`,

    'https://docs.google.com/forms/d/e/1FAIpQLSfMM4t9aoSZomoYWZfghSDNnmHTtFIV5cUf_yvTZaUlz5Kz2A/viewform?usp=sf_link'
    as link,

from eligible_roster as r
inner join {{ ref("stg_reporting__terms") }} as rt on rt.name = 'KTAF Support Survey'
where
    r.job_title in ('Executive Director', 'Managing Director of Operations')
    or (
        r.business_unit <> 'KIPP TEAM and Family Schools Inc.'
        and (
            r.job_title like ('%Leader%')
            or r.job_title like ('%Head%')
            or r.job_title = 'School Operations Manager'
        )
    )
    or (
        r.business_unit <> 'KIPP TEAM and Family Schools Inc.'
        and (
            r.job_title like ('%Director%')
            and r.department
            in ('Operations', 'KIPP Forward', 'Special Education', 'School Support')
        )
    )

union all
-- Manager Survey
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

    'Manager Survey' as survey,
    concat(
        r.report_to_preferred_name_lastfirst,
        ' - ',
        r.manager_work_location,
        ' ( ',
        safe_cast(r.report_to_employee_number as string),
        ')'
    ) as `assignment`,

    coalesce(
        concat(
            'https://docs.google.com/forms/d/e/1FAIpQLSe9thH3gWfdPLWVtI7gTimKqFO4xjcSr8-Htq-pPhzccxf6dw/viewform?usp=pp_url&entry.1442315056=',
            r.preferred_name_lastfirst,
            '+-+',
            r.location,
            '+(',
            safe_cast(r.employee_number as string),
            ')',
            '&entry.828009527=',
            r.report_to_preferred_name_lastfirst,
            ' - ',
            r.manager_work_location,
            ' (',
            safe_cast(r.report_to_employee_number as string),
            ')'
        ),
        'https://docs.google.com/forms/d/e/1FAIpQLSe9thH3gWfdPLWVtI7gTimKqFO4xjcSr8-Htq-pPhzccxf6dw/viewform?usp=pp_url'
    ) as link,
from eligible_roster as r
inner join {{ ref("stg_reporting__terms") }} as rt on rt.name = 'Manager Survey'

union all
-- Support Survey
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

    'Support Survey' as survey,
    'Complete Your Support Survey' as `assignment`,

    concat(
        'https://docs.google.com/forms/d/e/1FAIpQLSf-KQi1iI4gEhilQABKe8gTHtb7wPHuJHG0i_ZX6Bln1JiwwA/viewform?usp=pp_url&entry.1442315056=',
        r.preferred_name_lastfirst,
        '+-+',
        r.location,
        '+(',
        safe_cast(r.employee_number as string),
        ')',
        '&entry.828009527=',
        r.loc_type
    ) as link,
from eligible_roster as r
inner join {{ ref("stg_reporting__terms") }} as rt on rt.name = 'Support Survey'

union all
-- School Community Diagnostic Staff Survey
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

    'School Community Diagnostic' as survey,
    'Complete The School Community Diagnostic' as `assignment`,
    'https://docs.google.com/forms/d/e/1FAIpQLSfozw5B8DP9jKhf_mA5JhtwfLdziZwVsjDFCJtfs2nJnQlWXA/viewform?usp=sf_link'
    as link,
from eligible_roster as r
inner join
    {{ ref("stg_reporting__terms") }} as rt
    on rt.name = 'School Community Diagnostic Staff Survey'

union all
-- TNTP Insight
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

    'TNTP Insight Survey' as survey,
    'Complete TNTP Insight Survey (Note: link is only accessible via your email)'
    as `assignment`,

    'https://teamschools.zendesk.com/hc/en-us/articles/22601310814999-How-to-Access-the-TNTP-Insight-and-Gallup-Surveys'
    as link,
from eligible_roster as r
inner join {{ ref("stg_reporting__terms") }} as rt on rt.name = 'TNTP Insight'

union all
-- Gallup Q12 Survey
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

    'Gallup Q12 Survey' as survey,
    'Complete Gallup Q12 Survey (Note: link is only accessible via your email)'
    as `assignment`,
    'https://teamschools.zendesk.com/hc/en-us/articles/22601310814999-How-to-Access-the-TNTP-Insight-and-Gallup-Surveys'
    as link,
-- trunk-ignore-end(sqlfluff/LT05)
from eligible_roster as r
inner join {{ ref("stg_reporting__terms") }} as rt on rt.name = 'Gallup Q12 Survey'
