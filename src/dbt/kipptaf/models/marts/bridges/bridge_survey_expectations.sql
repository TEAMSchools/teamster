with
    -- TODO: deduplicating contact persons; no unique key in source
    contact_persons as (
        select distinct student_contact_person_key,
        from {{ ref("dim_student_contact_persons") }}
    ),

    survey_admin as (
        select
            sa.survey_administration_key,
            sa.survey_key,
            sa.term_key,
            sa.academic_year,
            sa.response_deadline_date,

            s.name,
        from {{ ref("dim_survey_administrations") }} as sa
        inner join {{ ref("dim_surveys") }} as s on sa.survey_key = s.survey_key
    ),

    /* Staff SCD expectations: active staff during SCD window */
    staff_scd as (
        select
            sa.survey_administration_key,
            sa.survey_key,
            sa.term_key,

            'staff' as respondent_type,

            swa.staff_key,

            cast(null as string) as student_enrollment_key,
            cast(null as string) as student_contact_person_key,

        from survey_admin as sa
        inner join
            {{ ref("dim_work_assignment_status") }} as wast
            on sa.response_deadline_date
            between wast.effective_start_date and wast.effective_end_date
            and wast.status_code = 'A'
        inner join
            {{ ref("dim_work_assignment_primary") }} as wap
            on wast.work_assignment_key = wap.work_assignment_key
            and sa.response_deadline_date
            between wap.effective_start_date and wap.effective_end_date
            and wap.is_primary_position
        inner join
            {{ ref("dim_staff_work_assignments") }} as swa
            on wast.work_assignment_key = swa.work_assignment_key
        where sa.name = 'School Community Diagnostic Staff Survey'
    ),

    /* Staff Manager Survey expectations: direct reports evaluate manager */
    staff_manager as (
        select
            sa.survey_administration_key,
            sa.survey_key,
            sa.term_key,

            'staff' as respondent_type,

            swa.staff_key,

            cast(null as string) as student_enrollment_key,
            cast(null as string) as student_contact_person_key,

        from survey_admin as sa
        inner join
            {{ ref("dim_work_assignment_status") }} as wast
            on sa.response_deadline_date
            between wast.effective_start_date and wast.effective_end_date
            and wast.status_code = 'A'
        inner join
            {{ ref("dim_work_assignment_primary") }} as wap
            on wast.work_assignment_key = wap.work_assignment_key
            and sa.response_deadline_date
            between wap.effective_start_date and wap.effective_end_date
            and wap.is_primary_position
        inner join
            {{ ref("dim_staff_work_assignments") }} as swa
            on wast.work_assignment_key = swa.work_assignment_key
        where sa.name = 'Manager Survey'
    ),

    /* Staff Support Survey expectations */
    staff_support as (
        select
            sa.survey_administration_key,
            sa.survey_key,
            sa.term_key,

            'staff' as respondent_type,

            swa.staff_key,

            cast(null as string) as student_enrollment_key,
            cast(null as string) as student_contact_person_key,

        from survey_admin as sa
        inner join
            {{ ref("dim_work_assignment_status") }} as wast
            on sa.response_deadline_date
            between wast.effective_start_date and wast.effective_end_date
            and wast.status_code = 'A'
        inner join
            {{ ref("dim_work_assignment_primary") }} as wap
            on wast.work_assignment_key = wap.work_assignment_key
            and sa.response_deadline_date
            between wap.effective_start_date and wap.effective_end_date
            and wap.is_primary_position
        inner join
            {{ ref("dim_staff_work_assignments") }} as swa
            on wast.work_assignment_key = swa.work_assignment_key
        where sa.name = 'Support Survey'
    ),

    /* Student SCD expectations: enrolled students */
    student_scd as (
        select
            sa.survey_administration_key,
            sa.survey_key,
            sa.term_key,

            'student' as respondent_type,

            cast(null as string) as staff_key,

            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "enr.student_number",
                        "enr._dbt_source_relation",
                        "enr.academic_year",
                        "enr.entrydate",
                    ]
                )
            }} as student_enrollment_key,

            cast(null as string) as student_contact_person_key,

            enr.student_number as respondent_identifier,
        from survey_admin as sa
        inner join
            {{ ref("int_extracts__student_enrollments") }} as enr
            on sa.academic_year = enr.academic_year
            and enr.enroll_status = 0
            and enr.grade_level between 3 and 12
        where sa.name = 'School Community Diagnostic Student Survey'
    ),

    /* Family SCD expectations: one per contact person */
    family_scd as (
        select
            sa.survey_administration_key,
            sa.survey_key,
            sa.term_key,

            'family' as respondent_type,

            cast(null as string) as staff_key,
            cast(null as string) as student_enrollment_key,

            cp.student_contact_person_key,
        from survey_admin as sa
        cross join contact_persons as cp
        where
            sa.name in (
                'KIPP NJ & KIPP Miami Family Survey',
                'KIPP Miami Re-Commitment Form'
                ' & Family School Community Diagnostic',
                'PowerSchool Family School Community Diagnostic'
            )
    ),

    all_expectations as (
        select
            survey_administration_key,
            survey_key,
            term_key,
            respondent_type,
            staff_key,
            student_enrollment_key,
            student_contact_person_key,
        from staff_scd
        union all
        select
            survey_administration_key,
            survey_key,
            term_key,
            respondent_type,
            staff_key,
            student_enrollment_key,
            student_contact_person_key,
        from staff_manager
        union all
        select
            survey_administration_key,
            survey_key,
            term_key,
            respondent_type,
            staff_key,
            student_enrollment_key,
            student_contact_person_key,
        from staff_support
        union all
        select
            survey_administration_key,
            survey_key,
            term_key,
            respondent_type,
            staff_key,
            student_enrollment_key,
            student_contact_person_key,
        from student_scd
        union all
        select
            survey_administration_key,
            survey_key,
            term_key,
            respondent_type,
            staff_key,
            student_enrollment_key,
            student_contact_person_key,
        from family_scd
    )

-- TODO: #3687 — roster history has multiple assignments per employee
select distinct
    {{
        dbt_utils.generate_surrogate_key(
            [
                "survey_administration_key",
                "respondent_type",
                "staff_key",
                "student_enrollment_key",
                "student_contact_person_key",
            ]
        )
    }} as survey_expectation_key,

    survey_administration_key,
    respondent_type,
    staff_key,
    student_enrollment_key,
    student_contact_person_key,
from all_expectations
