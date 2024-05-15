/* Student Number from Family Surveys*/
with
    family_responses as (
        select
            survey_id,
            survey_response_id,
            academic_year,

            safe_cast(
                max(
                    case
                        when
                            question_shortname
                            in ('student_number', 'family_respondent_number')
                        then answer
                    end
                ) over (partition by answer order by date_submitted) as int
            ) as respondent_number,

        from {{ ref("int_surveys__survey_responses") }}
        where
            survey_title in (
                'KIPP NJ & KIPP Miami Family Survey',
                'KIPP Miami Re-Commitment Form & Family School Community Diagnostic'
            )
            and question_shortname in ('student_number', 'family_respondent_number')

    )
/* Google Forms and Alchemer Responses */
select
    sr.survey_id,
    sr.survey_title,
    sr.survey_response_id,
    sr.question_title,
    sr.question_shortname,
    sr.answer,
    sr.answer_value,
    sr.date_submitted,
    sr.academic_year,

    srh.job_title as staff_job_title,

    coalesce(se1.spedlep, se2.spedlep) as student_spedlep,
    coalesce(
        sr.employee_number, se1.student_number, fr.respondent_number
    ) as respondent_number,
    coalesce(srh.home_work_location_region, se1.region, se2.region) as region,
    coalesce(srh.home_work_location_name, se1.school_name, se2.school_name) as location,
    coalesce(srh.race_ethnicity, se1.ethnicity, se2.ethnicity) as race_ethnicity,
    coalesce(srh.gender_identity, se1.gender, se2.gender) as gender,
    coalesce(
        srh.home_work_location_grade_band, se1.school_level, se2.school_level
    ) as grade_band,
    coalesce(
        srh.primary_grade_level_taught, se1.grade_level, se2.grade_level
    ) as grade_level,

    case
        when sr.survey_title like '%Staff%'
        then 'Staff'
        when sr.survey_title like '%Engagement%'
        then 'Staff'
        when sr.survey_title like '%Student%'
        then 'Student'
        when sr.survey_title like '%Family%'
        then 'Family'
    end as survey_audience,

from {{ ref("int_surveys__survey_responses") }} as sr
left join
    {{ ref("base_people__staff_roster_history") }} as srh
    on sr.employee_number = srh.employee_number
    and sr.date_submitted
    between srh.work_assignment_start_date and srh.work_assignment_end_date
left join
    {{ ref("base_powerschool__student_enrollments") }} as se1
    on sr.respondent_email = se1.student_email_google
    and sr.academic_year = se1.academic_year
left join
    family_responses as fr
    on fr.survey_id = sr.survey_id
    and fr.survey_response_id = sr.survey_response_id
left join
    {{ ref("base_powerschool__student_enrollments") }} as se2
    on fr.respondent_number = se2.student_number
    and fr.academic_year = se2.academic_year
where
    sr.survey_title in (
        'Engagement & Support Surveys',
        'KIPP NJ & KIPP Miami Family Survey',
        'School Community Diagnostic Student Survey',
        'School Community Diagnostic Staff Survey',
        'KIPP Miami Re-Commitment Form & Family School Community Diagnostic'
    )
    and sr.question_shortname like '%scd%'

union all

/* Powerschool InfoSnap Responses */
select
    'PowerSchool_24' as survey_id,
    'PowerSchool Family School Community Diagnostic' as survey_title,
    sr.external_student_id as survey_response_id,
    sr.data_item_key as question_title,
    sr.data_item_key as question_shortname,
    sr.data_item_value as answer,
    safe_cast(sr.data_item_value as int) as answer_value,
    safe_cast(sr.submitted as timestamp) as date_submitted,
    2024 as academic_year,

    null as staff_job_title,

    se.spedlep as student_spedlep,
    se.student_number as respondent_number,
    se.region,
    se.school_name as location,
    se.ethnicity as race_ethnicity,
    se.gender as gender,
    se.school_level as grade_band,
    se.grade_level,
    'Family' as survey_audience,

from {{ ref("stg_powerschool_enrollment__submission_records") }} as sr
left join
    {{ ref("stg_reporting__terms") }} as rt
    on rt.name = 'PowerSchool Family School Community Diagnostic'
    and sr.submitted between rt.start_date and rt.end_date
left join
    {{ ref("base_powerschool__student_enrollments") }} as se
    on sr.external_student_id = safe_cast(se.student_number as string)
    and rt.academic_year = se.academic_year
where
    published_action_id = 39362
    and data_item_key in (
        'School_Survey_01',
        'School_Survey_02',
        'School_Survey_03',
        'School_Survey_04',
        'School_Survey_05',
        'School_Survey_06',
        'School_Survey_07',
        'School_Survey_08',
        'School_Survey_09',
        'School_Survey_10'
    )
