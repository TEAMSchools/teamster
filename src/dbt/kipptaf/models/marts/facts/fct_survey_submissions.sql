with
    /* Staff survey submissions from int_surveys__survey_responses */
    staff_submissions as (
        -- TODO: upstream at response grain (#3629)
        select distinct
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

            'staff' as respondent_type,

            cast(null as int64) as subject_employee_number,
        from {{ ref("int_surveys__survey_responses") }} as sr
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on sr.survey_title = rt.`name`
            and sr.academic_year = rt.academic_year
            and sr.term_code = rt.code
            and rt.type = 'SURVEY'
        where
            sr.survey_title in (
                'School Community Diagnostic Staff Survey',
                'Engagement & Support Surveys'
            )
    ),

    /* Student SCD submissions */
    student_submissions as (
        -- TODO: upstream at response grain (#3629)
        select distinct
            sr.survey_id,
            sr.survey_response_id,
            sr.respondent_email,
            sr.date_submitted,
            sr.term_code,

            rt.type as term_type,
            rt.code as rt_code,
            rt.`name` as rt_name,
            rt.start_date as rt_start_date,
            rt.region as rt_region,
            rt.school_id as rt_school_id,

            'student' as respondent_type,

            enr.student_number,
            enr._dbt_source_relation,
            enr.academic_year,
            enr.entrydate,
        from {{ ref("int_surveys__survey_responses") }} as sr
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on sr.survey_title = rt.`name`
            and sr.academic_year = rt.academic_year
            and sr.term_code = rt.code
            and rt.type = 'SURVEY'
        inner join
            {{ ref("int_extracts__student_enrollments") }} as enr
            on sr.respondent_email = enr.student_email
            and enr.entrydate <= date(sr.date_submitted)
            and enr.exitdate > date(sr.date_submitted)
        where sr.survey_title = 'School Community Diagnostic Student Survey'
    ),

    /* Family SCD submissions from rpt_tableau__school_community_diagnostic */
    family_gforms as (
        -- TODO: upstream at response grain (#3629)
        select distinct
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

            'family' as respondent_type,
        from {{ ref("int_surveys__survey_responses") }} as sr
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on sr.survey_title = rt.`name`
            and sr.academic_year = rt.academic_year
            and sr.term_code = rt.code
            and rt.type = 'SURVEY'
        where
            sr.survey_title in (
                'KIPP NJ & KIPP Miami Family Survey',
                'KIPP Miami Re-Commitment Form'
                ' & Family School Community Diagnostic'
            )
    ),

    /* Manager Survey submissions */
    manager_submissions as (
        -- TODO: upstream at response grain (#3629)
        select distinct
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

            'staff' as respondent_type,

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
            respondent_type,
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
            respondent_type,
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
            respondent_type,
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
            respondent_type,
            date_submitted,
            academic_year,
        from family_gforms
    )

/* Staff submissions */
select
    {{ dbt_utils.generate_surrogate_key(["survey_id", "survey_response_id"]) }}
    as survey_submission_key,

    survey_administration_key,

    date(date_submitted) as date_submitted_key,

    respondent_type,

    if(
        respondent_employee_number is not null,
        {{ dbt_utils.generate_surrogate_key(["respondent_employee_number"]) }},
        cast(null as string)
    ) as staff_key,

    cast(null as string) as student_enrollment_key,
    cast(null as string) as student_contact_person_key,

    if(
        subject_employee_number is not null,
        {{ dbt_utils.generate_surrogate_key(["subject_employee_number"]) }},
        cast(null as string)
    ) as subject_staff_key,

    academic_year,

    date_submitted as `timestamp`,
from combined_staff

union all

/* Student submissions */
select
    {{ dbt_utils.generate_surrogate_key(["survey_id", "survey_response_id"]) }}
    as survey_submission_key,

    survey_administration_key,

    date(date_submitted) as date_submitted_key,

    respondent_type,

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

    academic_year,

    date_submitted as `timestamp`,
from combined_student

union all

/* Family submissions */
select
    {{ dbt_utils.generate_surrogate_key(["survey_id", "survey_response_id"]) }}
    as survey_submission_key,

    survey_administration_key,

    date(date_submitted) as date_submitted_key,

    respondent_type,

    cast(null as string) as staff_key,
    cast(null as string) as student_enrollment_key,
    cast(null as string) as student_contact_person_key,
    cast(null as string) as subject_staff_key,

    academic_year,

    date_submitted as `timestamp`,
from combined_family
