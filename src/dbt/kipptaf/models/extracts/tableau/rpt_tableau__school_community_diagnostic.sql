select
    scd.survey_id,
    scd.survey_title,
    scd.survey_response_id,
    scd.question_title,
    scd.question_shortname,
    scd.answer,
    scd.answer_value,
    scd.date_submitted,
    scd.survey_audience,
    scd.academic_year,

    srh.job_title as staff_job_title,

    se.special_education_code as student_special_education_code,

    coalesce(srh.home_work_location_region, se.region) as region,
    coalesce(srh.home_work_location_name, se.school_name) as location,
    coalesce(srh.race_ethnicity, se.ethnicity) as race_ethnicity,
    coalesce(srh.gender_identity, se.gender) as gender,
    coalesce(srh.home_work_location_grade_band, se.school_level) as grade_band,
    coalesce(srh.primary_grade_level_taught, se.grade_level) as grade_level,
    coalesce(
        scd.staff_respondent_number,
        scd.student_respondent_number,
        scd.family_respondent_number
    ) as respondent_number,

from {{ ref("int_surveys__school_community_diagnostic") }} as scd
left join
    {{ ref("base_people__staff_roster_history") }} as srh
    on scd.staff_respondent_number = srh.employee_number
    and scd.date_submitted
    between srh.work_assignment_start_date and srh.work_assignment_end_date
left join
    {{ ref("base_powerschool__student_enrollments") }} as se
    on coalesce(scd.student_respondent_number, scd.family_respondent_number)
    = se.student_number
    and scd.academic_year = se.academic_year
where
    coalesce(
        scd.staff_respondent_number,
        scd.student_respondent_number,
        scd.family_respondent_number
    )
    is not null
    and answer is not null
