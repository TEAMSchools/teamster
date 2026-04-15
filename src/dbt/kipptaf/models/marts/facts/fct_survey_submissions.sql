with
    /* Staff survey submissions from int_surveys__survey_responses */
    staff_submissions as (
        select
            sr.survey_id,
            sr.survey_response_id,
            sr.respondent_employee_number,
            sr.date_submitted,
            sr.academic_year,
            sr.term_code,

            rt.type as term_type,
            rt.code as rt_code,
            rt.`name` as rt_name,
            rt.start_date as rt_start_date,
            rt.region as rt_region,
            rt.school_id as rt_school_id,

            'staff' as respondent_population,

            cast(null as int64) as subject_employee_number,
        from {{ ref("int_surveys__survey_responses") }} as sr
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on sr.survey_title = rt.`name`
            and sr.academic_year = rt.academic_year
            and rt.type = 'SURVEY'
        where
            sr.respondent_employee_number is not null
            and sr.survey_title in (
                'School Community Diagnostic Staff Survey',
                'Engagement & Support Surveys'
            )
        group by 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14
    ),

    /* Student SCD submissions */
    student_submissions_ranked as (
        select
            sr.survey_id,
            sr.survey_response_id,
            sr.respondent_email,
            sr.date_submitted,
            sr.academic_year,
            sr.term_code,

            rt.type as term_type,
            rt.code as rt_code,
            rt.`name` as rt_name,
            rt.start_date as rt_start_date,
            rt.region as rt_region,
            rt.school_id as rt_school_id,

            'student' as respondent_population,

            enr.student_number,
            enr._dbt_source_relation,
            enr.entrydate,

            row_number() over (
                partition by sr.survey_response_id order by enr.entrydate desc
            ) as rn_enrollment,
        from {{ ref("int_surveys__survey_responses") }} as sr
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on sr.survey_title = rt.`name`
            and sr.academic_year = rt.academic_year
            and rt.type = 'SURVEY'
        inner join
            {{ ref("int_extracts__student_enrollments") }} as enr
            on sr.respondent_email = enr.student_email
            and sr.academic_year = enr.academic_year
            and enr.enroll_status = 0
        where sr.survey_title = 'School Community Diagnostic Student Survey'
    ),

    student_submissions as (
        select
            survey_id,
            survey_response_id,
            respondent_email,
            date_submitted,
            academic_year,
            term_code,
            term_type,
            rt_code,
            rt_name,
            rt_start_date,
            rt_region,
            rt_school_id,
            respondent_population,
            student_number,
            _dbt_source_relation,
            entrydate,
        from student_submissions_ranked
        where rn_enrollment = 1
    ),

    /* Family SCD submissions from rpt_tableau__school_community_diagnostic */
    family_gforms as (
        select
            sr.survey_id,
            sr.survey_response_id,
            sr.date_submitted,
            sr.academic_year,
            sr.term_code,

            rt.type as term_type,
            rt.code as rt_code,
            rt.`name` as rt_name,
            rt.start_date as rt_start_date,
            rt.region as rt_region,
            rt.school_id as rt_school_id,

            'family' as respondent_population,
        from {{ ref("int_surveys__survey_responses") }} as sr
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on sr.survey_title = rt.`name`
            and sr.academic_year = rt.academic_year
            and rt.type = 'SURVEY'
        where
            sr.survey_title in (
                'KIPP NJ & KIPP Miami Family Survey',
                'KIPP Miami Re-Commitment Form'
                ' & Family School Community Diagnostic'
            )
        group by 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12
    ),

    /* Manager Survey submissions */
    manager_submissions as (
        select
            ms.survey_id,
            ms.respondent_df_employee_number as respondent_employee_number,
            ms.subject_df_employee_number as subject_employee_number,
            ms.date_submitted,
            ms.campaign_academic_year as academic_year,
            ms.campaign_reporting_term as term_code,

            rt.type as term_type,
            rt.code as rt_code,
            rt.`name` as rt_name,
            rt.start_date as rt_start_date,
            rt.region as rt_region,
            rt.school_id as rt_school_id,

            'staff' as respondent_population,

            coalesce(
                ms.survey_response_id,
                concat(
                    ms.respondent_df_employee_number,
                    '_',
                    ms.subject_df_employee_number,
                    '_',
                    ms.campaign_reporting_term
                )
            ) as survey_response_id,
        from {{ ref("int_surveys__manager_survey_details") }} as ms
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on rt.`name` = 'Manager Survey'
            and ms.campaign_academic_year = rt.academic_year
            and ms.campaign_reporting_term = rt.code
            and rt.type = 'SURVEY'
        where ms.campaign_academic_year is not null
        group by 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14
    ),

    /* Combine all staff-type submissions */
    combined_staff as (
        select
            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "survey_id",
                        "term_type",
                        "rt_code",
                        "rt_name",
                        "rt_start_date",
                        "rt_region",
                        "rt_school_id",
                    ]
                )
            }} as survey_administration_key,

            survey_id,
            survey_response_id,
            respondent_population,
            respondent_employee_number,
            subject_employee_number,
            date_submitted,
            academic_year,
        from staff_submissions

        union all

        select
            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "survey_id",
                        "term_type",
                        "rt_code",
                        "rt_name",
                        "rt_start_date",
                        "rt_region",
                        "rt_school_id",
                    ]
                )
            }} as survey_administration_key,

            survey_id,
            survey_response_id,
            respondent_population,
            respondent_employee_number,
            subject_employee_number,
            date_submitted,
            academic_year,
        from manager_submissions
    ),

    combined_student as (
        select
            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "survey_id",
                        "term_type",
                        "rt_code",
                        "rt_name",
                        "rt_start_date",
                        "rt_region",
                        "rt_school_id",
                    ]
                )
            }} as survey_administration_key,

            survey_id,
            survey_response_id,
            respondent_population,
            student_number,
            _dbt_source_relation,
            academic_year,
            entrydate,
            date_submitted,
        from student_submissions
    ),

    combined_family as (
        select
            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "survey_id",
                        "term_type",
                        "rt_code",
                        "rt_name",
                        "rt_start_date",
                        "rt_region",
                        "rt_school_id",
                    ]
                )
            }} as survey_administration_key,

            survey_id,
            survey_response_id,
            respondent_population,
            date_submitted,
            academic_year,
        from family_gforms
    )

/* Staff submissions */
select
    {{
        dbt_utils.generate_surrogate_key(
            ["survey_id", "survey_response_id", "respondent_employee_number"]
        )
    }} as survey_submission_key,

    survey_administration_key,

    date(date_submitted) as date_submitted_key,

    respondent_population,

    {{ dbt_utils.generate_surrogate_key(["respondent_employee_number"]) }} as staff_key,

    cast(null as string) as student_enrollment_key,
    cast(null as string) as student_contact_person_key,

    if(
        subject_employee_number is not null,
        {{ dbt_utils.generate_surrogate_key(["subject_employee_number"]) }},
        cast(null as string)
    ) as subject_staff_key,

    survey_id,
    survey_response_id,
    date_submitted,
    academic_year,
from combined_staff

union all

/* Student submissions */
select
    {{
        dbt_utils.generate_surrogate_key(
            ["survey_id", "survey_response_id", "student_number"]
        )
    }} as survey_submission_key,

    survey_administration_key,

    date(date_submitted) as date_submitted_key,

    respondent_population,

    cast(null as string) as staff_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "student_number",
                "_dbt_source_relation",
                "academic_year",
                "entrydate",
            ]
        )
    }} as student_enrollment_key,

    cast(null as string) as student_contact_person_key,
    cast(null as string) as subject_staff_key,

    survey_id,
    survey_response_id,
    date_submitted,
    academic_year,
from combined_student

union all

/* Family submissions */
select
    {{ dbt_utils.generate_surrogate_key(["survey_id", "survey_response_id"]) }}
    as survey_submission_key,

    survey_administration_key,

    date(date_submitted) as date_submitted_key,

    respondent_population,

    cast(null as string) as staff_key,
    cast(null as string) as student_enrollment_key,
    cast(null as string) as student_contact_person_key,
    cast(null as string) as subject_staff_key,

    survey_id,
    survey_response_id,
    date_submitted,
    academic_year,
from combined_family
