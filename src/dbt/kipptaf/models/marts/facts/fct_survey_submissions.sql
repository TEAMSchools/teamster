with
    /* Staff SCD submissions */
    staff_submissions as (
        select
            sg.survey_submission_key,
            sg.survey_id,
            sg.respondent_employee_number,
            sg.date_submitted,
            sg.academic_year,

            rt.type as term_type,
            rt.code as rt_code,
            rt.`name` as rt_name,
            rt.start_date as rt_start_date,
            rt.region as rt_region,
            rt.school_id as rt_school_id,

            'staff' as respondent_type,

            cast(null as int64) as subject_employee_number,
        from {{ ref("int_surveys__survey_submissions") }} as sg
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on sg.survey_title = rt.`name`
            and sg.academic_year = rt.academic_year
            and sg.term_code = rt.code
            and rt.type = 'SURVEY'
        where
            sg.survey_title in (
                'School Community Diagnostic Staff Survey',
                'Engagement & Support Surveys'
            )
    ),

    /*
     * Manager Survey submissions, both arms. The live Google Forms arm and the
     * historic Alchemer archive reach int_surveys__survey_submissions with the
     * same shape, so they need one branch rather than two. The subject of
     * evaluation comes from the overlay for both.
     */
    manager_submissions as (
        select
            sg.survey_submission_key,
            sg.survey_id,
            sg.respondent_employee_number,
            sg.date_submitted,
            sg.academic_year,

            rt.type as term_type,
            rt.code as rt_code,
            rt.`name` as rt_name,
            rt.start_date as rt_start_date,
            rt.region as rt_region,
            rt.school_id as rt_school_id,

            mso.subject_employee_number,

            'staff' as respondent_type,
        from {{ ref("int_surveys__survey_submissions") }} as sg
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on rt.`name` = 'Manager Survey'
            and sg.academic_year = rt.academic_year
            and sg.term_code = rt.code
            and rt.type = 'SURVEY'
        left join
            {{ ref("int_surveys__manager_submission_subjects") }} as mso
            on sg.survey_id = mso.survey_id
            and sg.survey_response_id = mso.survey_response_id
        where sg.survey_title = 'Manager Survey'
    ),

    /* Student SCD submissions */
    student_submissions as (
        select
            sg.survey_submission_key,
            sg.survey_id,
            sg.date_submitted,

            rt.type as term_type,
            rt.code as rt_code,
            rt.`name` as rt_name,
            rt.start_date as rt_start_date,
            rt.region as rt_region,
            rt.school_id as rt_school_id,

            enr.student_number,
            enr.academic_year,
            enr.entrydate,

            'student' as respondent_type,

            regexp_extract(
                enr._dbt_source_relation, r'(kipp\w+)_'
            ) as _dbt_source_project,
        from {{ ref("int_surveys__survey_submissions") }} as sg
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on sg.survey_title = rt.`name`
            and sg.academic_year = rt.academic_year
            and sg.term_code = rt.code
            and rt.type = 'SURVEY'
        inner join
            {{ ref("int_extracts__student_enrollments") }} as enr
            on sg.respondent_email = enr.student_email
            and enr.entrydate <= date(sg.date_submitted)
            and enr.exitdate >= date(sg.date_submitted)
        where sg.survey_title = 'School Community Diagnostic Student Survey'
    ),

    /* Family SCD submissions */
    family_submissions as (
        select
            sg.survey_submission_key,
            sg.survey_id,
            sg.date_submitted,
            sg.academic_year,

            rt.type as term_type,
            rt.code as rt_code,
            rt.`name` as rt_name,
            rt.start_date as rt_start_date,
            rt.region as rt_region,
            rt.school_id as rt_school_id,

            'family' as respondent_type,
        from {{ ref("int_surveys__survey_submissions") }} as sg
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on sg.survey_title = rt.`name`
            and sg.academic_year = rt.academic_year
            and sg.term_code = rt.code
            and rt.type = 'SURVEY'
        where
            sg.survey_title in (
                'KIPP NJ & KIPP Miami Family Survey',
                'KIPP Miami Re-Commitment Form'
                ' & Family School Community Diagnostic'
            )
    ),

    combined_staff as (
        select
            survey_submission_key,
            respondent_type,
            respondent_employee_number,
            subject_employee_number,
            date_submitted,
            academic_year,

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
        from staff_submissions

        union all

        select
            survey_submission_key,
            respondent_type,
            respondent_employee_number,
            subject_employee_number,
            date_submitted,
            academic_year,

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
        from manager_submissions
    )

/* Staff submissions */
select
    survey_submission_key,
    survey_administration_key,
    respondent_type,
    academic_year,

    date(date_submitted) as date_submitted_key,

    cast(null as string) as student_enrollment_key,
    cast(null as string) as student_contact_person_key,

    if(
        respondent_employee_number is not null,
        {{ dbt_utils.generate_surrogate_key(["respondent_employee_number"]) }},
        cast(null as string)
    ) as staff_key,

    if(
        subject_employee_number is not null,
        {{ dbt_utils.generate_surrogate_key(["subject_employee_number"]) }},
        cast(null as string)
    ) as subject_staff_key,

    date_submitted as `timestamp`,
from combined_staff

union all

/* Student submissions */
select
    survey_submission_key,

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

    respondent_type,
    academic_year,

    date(date_submitted) as date_submitted_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "student_number",
                "_dbt_source_project",
                "academic_year",
                "entrydate",
            ]
        )
    }} as student_enrollment_key,

    cast(null as string) as student_contact_person_key,
    cast(null as string) as staff_key,
    cast(null as string) as subject_staff_key,

    date_submitted as `timestamp`,
from student_submissions

union all

/* Family submissions */
select
    survey_submission_key,

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

    respondent_type,
    academic_year,

    date(date_submitted) as date_submitted_key,

    cast(null as string) as student_enrollment_key,
    cast(null as string) as student_contact_person_key,
    cast(null as string) as staff_key,
    cast(null as string) as subject_staff_key,

    date_submitted as `timestamp`,
from family_submissions
