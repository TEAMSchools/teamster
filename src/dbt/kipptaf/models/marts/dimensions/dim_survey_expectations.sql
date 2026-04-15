with
    -- TODO: deduplicating contact persons; no unique key in source
    contact_persons as (
        select distinct student_contact_person_key,
        from {{ ref("dim_student_contact_persons") }}
    ),

    survey_admin as (
        select
            survey_administration_key,
            survey_key,
            term_key,
            survey_id,
            survey_name,
            term_code,
            academic_year,
            response_deadline,
        from {{ ref("dim_survey_administrations") }}
    ),

    /* Staff SCD expectations: active staff during SCD window */
    staff_scd as (
        select
            sa.survey_administration_key,
            sa.survey_key,
            sa.term_key,

            'staff' as respondent_population,

            {{ dbt_utils.generate_surrogate_key(["srh.employee_number"]) }}
            as staff_key,

            cast(null as string) as student_enrollment_key,
            cast(null as string) as student_contact_person_key,

            srh.employee_number,
        from survey_admin as sa
        inner join
            {{ ref("int_people__staff_roster_history") }} as srh
            on sa.response_deadline
            between srh.work_assignment_actual_start_date and srh.effective_date_end
            and srh.primary_indicator
            and srh.assignment_status = 'Active'
        where sa.survey_name = 'School Community Diagnostic Staff Survey'
    ),

    /* Staff Manager Survey expectations: direct reports evaluate manager */
    staff_manager as (
        select
            sa.survey_administration_key,
            sa.survey_key,
            sa.term_key,

            'staff' as respondent_population,

            {{ dbt_utils.generate_surrogate_key(["srh.employee_number"]) }}
            as staff_key,

            cast(null as string) as student_enrollment_key,
            cast(null as string) as student_contact_person_key,

            srh.employee_number,
        from survey_admin as sa
        inner join
            {{ ref("int_people__staff_roster_history") }} as srh
            on sa.response_deadline
            between srh.work_assignment_actual_start_date and srh.effective_date_end
            and srh.primary_indicator
            and srh.assignment_status = 'Active'
        where sa.survey_name = 'Manager Survey'
    ),

    /* Staff Support Survey expectations */
    staff_support as (
        select
            sa.survey_administration_key,
            sa.survey_key,
            sa.term_key,

            'staff' as respondent_population,

            {{ dbt_utils.generate_surrogate_key(["srh.employee_number"]) }}
            as staff_key,

            cast(null as string) as student_enrollment_key,
            cast(null as string) as student_contact_person_key,

            srh.employee_number,
        from survey_admin as sa
        inner join
            {{ ref("int_people__staff_roster_history") }} as srh
            on sa.response_deadline
            between srh.work_assignment_actual_start_date and srh.effective_date_end
            and srh.primary_indicator
            and srh.assignment_status = 'Active'
        where sa.survey_name = 'Support Survey'
    ),

    /* Student SCD expectations: enrolled students */
    student_scd as (
        select
            sa.survey_administration_key,
            sa.survey_key,
            sa.term_key,

            'student' as respondent_population,

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
        where sa.survey_name = 'School Community Diagnostic Student Survey'
    ),

    /* Family SCD expectations: one per contact person */
    family_scd as (
        select
            sa.survey_administration_key,
            sa.survey_key,
            sa.term_key,

            'family' as respondent_population,

            cast(null as string) as staff_key,
            cast(null as string) as student_enrollment_key,

            cp.student_contact_person_key,
        from survey_admin as sa
        cross join contact_persons as cp
        where
            sa.survey_name in (
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
            respondent_population,
            staff_key,
            student_enrollment_key,
            student_contact_person_key,
        from staff_scd
        union all
        select
            survey_administration_key,
            survey_key,
            term_key,
            respondent_population,
            staff_key,
            student_enrollment_key,
            student_contact_person_key,
        from staff_manager
        union all
        select
            survey_administration_key,
            survey_key,
            term_key,
            respondent_population,
            staff_key,
            student_enrollment_key,
            student_contact_person_key,
        from staff_support
        union all
        select
            survey_administration_key,
            survey_key,
            term_key,
            respondent_population,
            staff_key,
            student_enrollment_key,
            student_contact_person_key,
        from student_scd
        union all
        select
            survey_administration_key,
            survey_key,
            term_key,
            respondent_population,
            staff_key,
            student_enrollment_key,
            student_contact_person_key,
        from family_scd
    )

-- TODO: roster history has multiple assignments per employee
select distinct
    {{
        dbt_utils.generate_surrogate_key(
            [
                "survey_administration_key",
                "respondent_population",
                "staff_key",
                "student_enrollment_key",
                "student_contact_person_key",
            ]
        )
    }} as survey_expectation_key,

    survey_administration_key,
    respondent_population,
    staff_key,
    student_enrollment_key,
    student_contact_person_key,
from all_expectations
