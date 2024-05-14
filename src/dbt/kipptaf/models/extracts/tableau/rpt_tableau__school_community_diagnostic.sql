/* Student Number from Family Google Forms Survey*/
with
    family_responses as (
        select
            survey_id,
            survey_response_id,

            max(
                case
                    when
                        question_shortname
                        in ('student_number', 'family_respondent_number')
                    then answer
                    else null
                end
            ) over (partition by answer order by date_submitted)
            as respondent_number,

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

    se.special_education_code as student_special_education_code,

    coalesce(srh.home_work_location_region, se.region) as region,
    coalesce(srh.home_work_location_name, se.school_name) as location,
    coalesce(srh.race_ethnicity, se.ethnicity) as race_ethnicity,
    coalesce(srh.gender_identity, se.gender) as gender,
    coalesce(srh.home_work_location_grade_band, se.school_level) as grade_band,
    coalesce(srh.primary_grade_level_taught, se.grade_level) as grade_level,
    coalesce(
        srh.employee_number, se.student_number, safe_cast(fr.respondent_number as int)
    ) as respondent_number,

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
    on sr.respondent_email = srh.google_email
    and sr.date_submitted
    between srh.work_assignment_start_date and srh.work_assignment_end_date
left join
    {{ ref("base_powerschool__student_enrollments") }} as se
    on sr.respondent_email = se.student_email_google
    and sr.academic_year = se.academic_year
left join family_responses as fr on safe_cast(fr.respondent_number as int) = se.student_number
where
    sr.survey_id in (
        '5300913',
        '6829997',
        '15Iq_dMeOmURb68Bg8Uc6j-Fco4N2wix7D8YFfSdCKPE',
        '1qFzdciQdg7g9aNujUulk6hivP7Qkz4Ab4Hr5WzW_k1Q',
        '16pr-UXHqY9g4kzB6azIWm0MRQANNspzWtAjvNEVcaUo'
    )
