with
    /* Student Number from Family Surveys */
    family_responses as (
        select
            survey_id,
            survey_response_id,
            academic_year,

            safe_cast(
                max(
                    if(
                        question_shortname
                        in ('student_number', 'family_respondent_number'),
                        answer,
                        null
                    )
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
    sr.question_shortname,
    sr.date_submitted,
    sr.academic_year,

    qc.question_text,

    ac.response_string as answer_text,
    ac.response_int as answer_value,

    srh.job_title as staff_job_title,

    coalesce(se1.spedlep, se2.spedlep) as student_spedlep,

    coalesce(
        sr.employee_number, se1.student_number, fr.respondent_number
    ) as respondent_number,

    coalesce(srh.home_work_location_region, se1.region, se2.region) as region,

    coalesce(
        srh.home_work_location_name, se1.school_name, se2.school_name
    ) as `location`,

    coalesce(srh.race_ethnicity, se1.ethnicity, se2.ethnicity) as race_ethnicity,

    coalesce(srh.gender_identity, se1.gender, se2.gender) as gender,

    coalesce(
        srh.home_work_location_grade_band, se1.school_level, se2.school_level
    ) as grade_band,

    coalesce(tgl.grade_level, se1.grade_level, se2.grade_level) as grade_level,

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
    between srh.work_assignment_start_timestamp and srh.work_assignment_end_timestamp
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
left join
    {{ ref("stg_surveys__scd_answer_crosswalk") }} as ac
    on sr.question_shortname = ac.question_code
    and sr.answer = ac.response
left join
    {{ ref("stg_surveys__scd_question_crosswalk") }} as qc
    on sr.question_shortname = qc.question_code
left join
    {{ ref("int_powerschool__teacher_grade_levels") }} as tgl
    on srh.powerschool_teacher_number = tgl.teachernumber
    and sr.academic_year = tgl.academic_year
    and tgl.grade_level_rank = 1
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
    'PowerSchool' as survey_id,
    'PowerSchool Family School Community Diagnostic' as survey_title,
    sr.external_student_id as survey_response_id,
    sr.data_item_key as question_shortname,
    safe_cast(sr.submitted as timestamp) as date_submitted,
    sr.academic_year,

    qc.question_text,
    ac.response_string as answer_text,
    ac.response_int as answer_value,

    null as staff_job_title,

    se.spedlep as student_spedlep,
    se.student_number as respondent_number,
    se.region,
    se.school_name as `location`,
    se.ethnicity as race_ethnicity,
    se.gender,
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
left join
    {{ ref("stg_surveys__scd_answer_crosswalk") }} as ac
    on sr.data_item_key = ac.question_code
    and sr.data_item_value = ac.response
left join
    {{ ref("stg_surveys__scd_question_crosswalk") }} as qc
    on sr.data_item_key = qc.question_code
where
    sr.published_action_id = 39362
    and sr.data_item_key in (
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
