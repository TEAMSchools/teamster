/* Student Number from Family Google Forms Survey*/
with
    family_responses as (
        select
            survey_id,
            survey_response_id,

            safe_cast(
                max(
                    case
                        when
                            question_shortname
                            in ('student_number', 'family_respondent_number')
                        then answer
                        else null
                    end
                ) over (partition by answer order by date_submitted) as int
            ) as respondent_number,

        from {{ ref("int_surveys__survey_responses") }}
        where
            survey_id in (
                '6829997',  -- KIPP NJ & KIPP Miami Family Survey
                '16pr-UXHqY9g4kzB6azIWm0MRQANNspzWtAjvNEVcaUo'
            )  -- KIPP Miami Re-Commitment Form & Family School Community Diagnostic 24.25
            and question_shortname in ('student_number', 'family_respondent_number')

    )

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

    coalesce(
        se1.special_education_code, se2.special_education_code
    ) as student_special_education_code,
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
    and fr.survey_response_id = fr.survey_response_id
left join
    {{ ref("base_powerschool__student_enrollments") }} as se2
    on fr.respondent_number = se2.student_number
where
    sr.survey_id in (
        '5300913',
        '6829997',
        '15Iq_dMeOmURb68Bg8Uc6j-Fco4N2wix7D8YFfSdCKPE',
        '1qFzdciQdg7g9aNujUulk6hivP7Qkz4Ab4Hr5WzW_k1Q',
        '16pr-UXHqY9g4kzB6azIWm0MRQANNspzWtAjvNEVcaUo'
    )
