with
    /*
     * Submission-grain projection of int_surveys__survey_responses.
     * One row per (survey_id, survey_response_id). The order_by choice is
     * arbitrary because projected columns don't vary across questions of the
     * same submission — survey_question_id is used for determinism only.
     * TODO: #3918 — extract int_surveys__survey_submissions intermediate.
     */
    submissions_grain as (
        {{
            dbt_utils.deduplicate(
                relation=ref("int_surveys__survey_responses"),
                partition_by="survey_id, survey_response_id",
                order_by="survey_question_id",
            )
        }}
    ),

    /* Staff SCD submissions */
    staff_submissions as (
        select
            sg.survey_id,
            sg.survey_response_id,
            sg.respondent_employee_number,
            sg.date_submitted,
            sg.academic_year,
            sg.term_code,

            rt.type as term_type,
            rt.code as rt_code,
            rt.`name` as rt_name,
            rt.start_date as rt_start_date,
            rt.region as rt_region,
            rt.school_id as rt_school_id,

            'staff' as respondent_type,

            cast(null as int64) as subject_employee_number,
        from submissions_grain as sg
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

    /* Student SCD submissions */
    student_submissions as (
        select
            sg.survey_id,
            sg.survey_response_id,
            sg.respondent_email,
            sg.date_submitted,
            sg.term_code,

            rt.type as term_type,
            rt.code as rt_code,
            rt.`name` as rt_name,
            rt.start_date as rt_start_date,
            rt.region as rt_region,
            rt.school_id as rt_school_id,

            'student' as respondent_type,

            enr.student_number,
            regexp_extract(
                enr._dbt_source_relation, r'(kipp\w+)_'
            ) as _dbt_source_project,
            enr.academic_year,
            enr.entrydate,
        from submissions_grain as sg
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
            and enr.exitdate > date(sg.date_submitted)
        where sg.survey_title = 'School Community Diagnostic Student Survey'
    ),

    /* Family SCD submissions */
    family_submissions as (
        select
            sg.survey_id,
            sg.survey_response_id,
            sg.date_submitted,
            sg.academic_year,
            sg.term_code,

            rt.type as term_type,
            rt.code as rt_code,
            rt.`name` as rt_name,
            rt.start_date as rt_start_date,
            rt.region as rt_region,
            rt.school_id as rt_school_id,

            'family' as respondent_type,
        from submissions_grain as sg
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

    /*
     * Manager Survey submissions — hash inputs from submissions_grain (Google
     * Forms branch of int_surveys__survey_responses). Subject-of-evaluation
     * staff columns come from int_surveys__manager_survey_details as a thin
     * overlay; that model is retained for subject context and the historic
     * Alchemer archive only. TODO: #3918.
     */
    /*
     * subject_df_employee_number is constant per (survey_id, survey_response_id)
     * by source-model design — int_surveys__manager_survey_details carries one
     * subject per submission and repeats it across question-grain rows. The
     * order_by here is arbitrary among identical values; deduplicate's only
     * job is the question-grain → submission-grain projection.
     */
    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    manager_overlay_source as (
        select survey_id, survey_response_id, subject_df_employee_number,
        from {{ ref("int_surveys__manager_survey_details") }}
        where survey_response_id is not null
    ),

    manager_subject_overlay as (
        {{
            dbt_utils.deduplicate(
                relation="manager_overlay_source",
                partition_by="survey_id, survey_response_id",
                order_by="subject_df_employee_number",
            )
        }}
    ),

    manager_submissions as (
        select
            sg.survey_id,
            sg.survey_response_id,
            sg.respondent_employee_number,
            sg.date_submitted,
            sg.academic_year,
            sg.term_code,

            rt.type as term_type,
            rt.code as rt_code,
            rt.`name` as rt_name,
            rt.start_date as rt_start_date,
            rt.region as rt_region,
            rt.school_id as rt_school_id,

            'staff' as respondent_type,

            mso.subject_df_employee_number as subject_employee_number,
        from submissions_grain as sg
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on rt.`name` = 'Manager Survey'
            and sg.academic_year = rt.academic_year
            and sg.term_code = rt.code
            and rt.type = 'SURVEY'
        left join
            manager_subject_overlay as mso
            on sg.survey_id = mso.survey_id
            and sg.survey_response_id = mso.survey_response_id
        where sg.survey_title = 'Manager Survey'
    ),

    /*
     * Historic Alchemer Manager archive — these rows have survey_response_id
     * NULL and don't appear in int_surveys__survey_responses, so they need
     * the deterministic fallback hash. They produce no FK orphans against
     * fct_survey_responses because no response-grain rows exist for them.
     */
    historic_archive_submissions as (
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
        where
            ms.survey_id = 'historic_alchemer_Manager_survey'
            and ms.campaign_academic_year is not null
    ),

    /* Combine all staff-type submissions (live SCD + Manager + archive) */
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
        from historic_archive_submissions
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
            _dbt_source_project,
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
        from family_submissions
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
                "_dbt_source_project",
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
