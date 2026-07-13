with
    school_year_start as (
        select distinct
            _dbt_source_project, academic_year, schoolid, first_day_school_year,
        from {{ ref("int_powerschool__calendar_week") }}
    ),

    esms_attend as (
        select
            _dbt_source_project,
            student_number,
            school_level,
            school_abbreviation,

            row_number() over (
                partition by student_number, school_level order by exitdate desc
            ) as rn,
        from {{ ref("base_powerschool__student_enrollments") }}
    ),

    es_grad as (
        select
            student_number,
            school_abbreviation,

            row_number() over (
                partition by student_number order by exitdate desc
            ) as rn,

        from {{ ref("base_powerschool__student_enrollments") }}
        where
            grade_level = 4
            and extract(month from exitdate) = 6
            and exitdate < current_date('{{ var("local_timezone") }}')
    ),

    next_year_school as (
        select
            student_number,
            academic_year,

            lead(school_abbreviation, 1) over (
                partition by student_number order by academic_year asc
            ) as next_year_school,

            lead(schoolid, 1) over (
                partition by student_number order by academic_year asc
            ) as next_year_schoolid,

        from {{ ref("base_powerschool__student_enrollments") }}
        where rn_year = 1
    ),

    mia_territory as (
        select
            _dbt_source_project,
            roster_name as territory,
            student_school_id,

            row_number() over (
                partition by student_school_id order by roster_id asc
            ) as rn_territory,

        from {{ ref("int_deanslist__roster_assignments") }}
        where school_id = 472 and roster_type = 'House' and active = 'Y'
    ),

    graduation_pathway_m as (
        select
            _dbt_source_project,
            studentsdcid,

            case
                when graduation_pathway_math = 'M' and graduation_pathway_ela = 'M'
                then 'Yes'
                when graduation_pathway_math = 'M' and graduation_pathway_ela != 'M'
                then 'Math only. No ELA match.'
                when graduation_pathway_math != 'M' and graduation_pathway_ela = 'M'
                then 'ELA only. No Math match.'
            end as grad_iep_exempt_overall,

        from {{ ref("stg_powerschool__s_nj_stu_x") }}
        where graduation_pathway_math = 'M' or graduation_pathway_ela = 'M'
    ),

    finalsite_enrollment_type_calc as (
        select
            _dbt_source_project,
            academic_year,
            student_number,

            if(
                sum(date_diff(exitdate, entrydate, day)) >= 7,
                'Previously Enrolled',
                'NTK'
            ) as next_year_enrollment_history,

        from {{ ref("base_powerschool__student_enrollments") }}
        where grade_level != 99
        group by _dbt_source_project, academic_year, student_number
    )

select
    e.* except (
        lastfirst,
        last_name,
        first_name,
        middle_name,
        school_abbreviation,
        advisory_section_number,
        student_email_google,
        salesforce_contact_id,
        salesforce_contact_df_has_fafsa,
        salesforce_contact_college_match_display_gpa,
        salesforce_contact_college_match_gpa_band,
        salesforce_contact_owner_name,
        state_studentnumber,
        `state`
    ),

    sc.contact_1_name,
    sc.contact_1_relationship,
    sc.contact_1_email_current,
    sc.contact_1_phone_mobile,
    sc.contact_1_phone_home,
    sc.contact_1_phone_daytime,
    sc.contact_1_phone_work,
    sc.contact_1_phone_primary,
    sc.contact_1_address_home,
    sc.contact_2_name,
    sc.contact_2_relationship,
    sc.contact_2_email_current,
    sc.contact_2_phone_mobile,
    sc.contact_2_phone_home,
    sc.contact_2_phone_daytime,
    sc.contact_2_phone_work,
    sc.contact_2_phone_primary,
    sc.contact_2_address_home,
    sc.emergency_1_name,
    sc.emergency_1_relationship,
    sc.emergency_1_email_current,
    sc.emergency_1_phone_mobile,
    sc.emergency_1_phone_home,
    sc.emergency_1_phone_daytime,
    sc.emergency_1_phone_work,
    sc.emergency_1_phone_primary,
    sc.emergency_1_address_home,
    sc.emergency_2_name,
    sc.emergency_2_relationship,
    sc.emergency_2_email_current,
    sc.emergency_2_phone_mobile,
    sc.emergency_2_phone_home,
    sc.emergency_2_phone_daytime,
    sc.emergency_2_phone_work,
    sc.emergency_2_phone_primary,
    sc.emergency_2_address_home,
    sc.emergency_3_name,
    sc.emergency_3_relationship,
    sc.emergency_3_email_current,
    sc.emergency_3_phone_mobile,
    sc.emergency_3_phone_home,
    sc.emergency_3_phone_daytime,
    sc.emergency_3_phone_work,
    sc.emergency_3_phone_primary,
    sc.emergency_3_address_home,
    sc.emergency_4_name,
    sc.emergency_4_relationship,
    sc.emergency_4_email_current,
    sc.emergency_4_phone_mobile,
    sc.emergency_4_phone_home,
    sc.emergency_4_phone_daytime,
    sc.emergency_4_phone_work,
    sc.emergency_4_phone_primary,
    sc.emergency_4_address_home,
    sc.pickup_1_name,
    sc.pickup_1_relationship,
    sc.pickup_1_email_current,
    sc.pickup_1_phone_mobile,
    sc.pickup_1_phone_home,
    sc.pickup_1_phone_daytime,
    sc.pickup_1_phone_work,
    sc.pickup_1_phone_primary,
    sc.pickup_1_address_home,
    sc.pickup_2_name,
    sc.pickup_2_relationship,
    sc.pickup_2_email_current,
    sc.pickup_2_phone_mobile,
    sc.pickup_2_phone_home,
    sc.pickup_2_phone_daytime,
    sc.pickup_2_phone_work,
    sc.pickup_2_phone_primary,
    sc.pickup_2_address_home,
    sc.pickup_3_name,
    sc.pickup_3_relationship,
    sc.pickup_3_email_current,
    sc.pickup_3_phone_mobile,
    sc.pickup_3_phone_home,
    sc.pickup_3_phone_daytime,
    sc.pickup_3_phone_work,
    sc.pickup_3_phone_primary,
    sc.pickup_3_address_home,

    e.lastfirst as student_name,
    e.last_name as student_last_name,
    e.first_name as student_first_name,
    e.middle_name as student_middle_name,
    e.school_abbreviation as school,
    e.advisory_section_number as team,
    e.student_email_google as student_email,
    e.salesforce_contact_id as salesforce_id,
    e.salesforce_contact_df_has_fafsa as has_fafsa,
    e.salesforce_contact_college_match_display_gpa as college_match_gpa,
    e.salesforce_contact_college_match_gpa_band as college_match_gpa_bands,
    e.salesforce_contact_owner_name as contact_owner_name,

    lc.location_region as region_official_name,
    lc.location_deanslist_school_id as deanslist_school_id,

    m.school_abbreviation as ms_attended,

    es.school_abbreviation as es_attended,

    eg.school_abbreviation as es_graduated,

    mt.territory,

    hi.enter_date as home_instruction_enter_date,
    hi.exit_date as home_instruction_exit_date,
    hi.sp_comment as home_instruction_sp_comment,

    hos.head_of_school_preferred_name_lastfirst as hos,
    hos.school_leader_preferred_name_lastfirst as school_leader,
    hos.school_leader_sam_account_name as school_leader_tableau_username,

    ovg.best_guess_pathway,

    ada.ada_term_q1 as ada_unweighted_term_q1,
    ada.ada_semester_s1 as ada_unweighted_semester_s1,
    ada.ada_year as unweighted_ada,
    ada.ada_weighted_term_q1,
    ada.ada_weighted_semester_s1,
    ada.ada_weighted_year as weighted_ada,
    ada.sum_absences_year as absences_unexcused_year,

    adapy.ada_year as ada_unweighted_year_prev,
    adapy.ada_weighted_year as ada_weighted_year_prev,

    gc.cumulative_y1_gpa,
    gc.cumulative_y1_gpa_unweighted,
    gc.cumulative_y1_gpa_projected,
    gc.cumulative_y1_gpa_projected_s1,
    gc.cumulative_y1_gpa_projected_s1_unweighted,
    gc.cumulative_y1_gpa_projected_unweighted,
    gc.core_cumulative_y1_gpa,
    gc.earned_credits_cum,
    gc.earned_credits_cum_projected,
    gc.potential_credits_cum,

    ny.next_year_school,
    ny.next_year_schoolid,

    'KTAF' as district,

    concat(e.region, e.school_level) as region_school_level,

    coalesce(sc.contact_1_email_current, sc.contact_2_email_current) as guardian_email,

    cast(e.academic_year as string)
    || '-'
    || right(cast(e.academic_year + 1 as string), 2) as academic_year_display,

    if(
        e.grade_level = 99, null, fs.next_year_enrollment_history
    ) as next_year_enrollment_history,

    if(ovg.fafsa_opt_out is not null, 'Yes', 'No') as overgrad_fafsa_opt_out,

    if(
        e.enroll_status = 0 and mc.grad_iep_exempt_overall is not null,
        mc.grad_iep_exempt_overall,
        'Not Grad IEP Exempt'
    ) as grad_iep_exempt_status_overall,

    if(e.spedlep like 'SPED%', 'Has IEP', 'No IEP') as iep_status,
    if(e.lep_status, 'ML', 'Not ML') as ml_status,
    if(e.is_504, 'Has 504', 'No 504') as status_504,
    if(
        e.is_self_contained, 'Self-contained', 'Not self-contained'
    ) as self_contained_status,

    if(e.region = 'Miami', e.fleid, e.state_studentnumber) as state_studentnumber,
    /* temporary: Miami uses a different ID field until we have alignment on ids */
    if(
        e.region = 'Miami', e.state_studentnumber, null
    ) as secondary_state_studentnumber,

    /* starting SY26, HS uses weighted ADA */
    if(
        e.school_level = 'HS' and e.academic_year >= 2025,
        ada.ada_weighted_year,
        ada.ada_year
    ) as `ada`,

    if(
        e.salesforce_contact_df_has_fafsa = 'Yes' or ovg.fafsa_opt_out is not null,
        true,
        false
    ) as met_fafsa_requirement,

    if(
        current_date('{{ var("local_timezone") }}')
        between cs.enter_date and cs.exit_date,
        1,
        null
    ) as is_counseling_services,

    if(
        current_date('{{ var("local_timezone") }}')
        between ath.enter_date and ath.exit_date,
        1,
        null
    ) as is_student_athlete,

    if(
        current_date('{{ var("local_timezone") }}')
        between tut.enter_date and tut.exit_date,
        true,
        false
    ) as is_tutoring,

    if(sip.students_student_number is not null, true, false) as is_sipps,

    if(
        gc.cumulative_y1_gpa_projected_unweighted_band
        < gc.cumulative_y1_gpa_unweighted_band,
        true,
        false
    ) as student_slideback,

    if(
        (
            (
                e.school_level = 'HS'
                and e.academic_year >= 2025
                and ada.ada_weighted_year >= 0.80
            )
            or ada.ada_year >= 0.80
        )
        and gc.cumulative_y1_gpa < 2.0,
        true,
        false
    ) as is_ada_above_or_at_80_cum_gpa_less_2,

    if(e.exitdate < cal.first_day_school_year, true, false) as is_pre_year_withdrawal,

    case
        e.gender when 'F' then 'Female' when 'M' then 'Male' when 'X' then 'Non-Binary'
    end as aligned_gender,

    case
        e.enroll_status
        when -2
        then 'Inactive'
        when -1
        then 'Pre-registered'
        when 0
        then 'Currently Enrolled'
        when 1
        then 'Inactive'
        when 2
        then 'Transferred Out'
        when 3
        then 'Graduated'
        when 4
        then 'Imported as Historical'
    end as enroll_status_string,

    case
        e.ethnicity when 'T' then 'T' when 'H' then 'H' else e.ethnicity
    end as race_ethnicity,

    case
        when
            e.academic_year >= 2025
            and e.school_abbreviation = 'Sumner'
            and e.grade_level = 5
        then 'MS'
        else e.school_level
    end as school_level_alt,

    case
        when e.school_level in ('ES', 'MS')
        then e.advisory_name
        when e.school_level = 'HS'
        then e.advisor_lastfirst
    end as advisory,

    case
        when e.region in ('Camden', 'Newark', 'Paterson')
        then 'NJ'
        when e.region = 'Miami'
        then 'FL'
    end as `state`,

    case
        /* starting SY26, HS uses weighted ADA */
        when
            e.school_level = 'HS'
            and e.academic_year >= 2025
            and ada.ada_weighted_year >= 0.80
        then true
        when e.school_level = 'HS' and e.academic_year <= 2024 and ada.ada_year >= 0.80
        then true
        when ada.ada_year >= 0.80
        then true
    end as ada_above_or_at_80,

    case
        when
            e.academic_year >= 2024  /* 1st year tracking this */
            and e.grade_level = 12
            and e.salesforce_contact_df_has_fafsa = 'Yes'
            and ovg.fafsa_opt_out is not null
        then 'Salesforce/Overgrad has FAFSA opt-out mismatch'
        else 'No issues'
    end as fafsa_status_mismatch_category,

from {{ ref("base_powerschool__student_enrollments") }} as e
left join
    school_year_start as cal
    on e.schoolid = cal.schoolid
    and e.academic_year = cal.academic_year
    and e._dbt_source_project = cal._dbt_source_project
left join
    {{ ref("int_people__location_crosswalk") }} as lc
    on e.school_name = lc.location_name
left join
    esms_attend as m
    on e.student_number = m.student_number
    and e._dbt_source_project = m._dbt_source_project
    and m.school_level = 'MS'
    and m.rn = 1
left join
    esms_attend as es
    on e.student_number = es.student_number
    and e._dbt_source_project = es._dbt_source_project
    and es.school_level = 'ES'
    and es.rn = 1
left join
    mia_territory as mt
    on e.student_number = mt.student_school_id
    and e._dbt_source_project = mt._dbt_source_project
    and mt.rn_territory = 1
left join
    {{ ref("int_powerschool__spenrollments") }} as cs
    on e.studentid = cs.studentid
    and e.academic_year = cs.academic_year
    and e._dbt_source_project = cs._dbt_source_project
    and cs.specprog_name = 'Counseling Services'
    and cs.rn_student_program_year_desc = 1
left join
    {{ ref("int_powerschool__spenrollments") }} as ath
    on e.studentid = ath.studentid
    and e.academic_year = ath.academic_year
    and e._dbt_source_project = ath._dbt_source_project
    and ath.specprog_name = 'Student Athlete'
    and ath.rn_student_program_year_desc = 1
left join
    {{ ref("int_powerschool__spenrollments") }} as tut
    on e.studentid = tut.studentid
    and e.academic_year = tut.academic_year
    and e._dbt_source_project = tut._dbt_source_project
    and tut.specprog_name = 'Tutoring'
    and tut.rn_student_program_year_desc = 1
left join
    {{ ref("int_powerschool__spenrollments") }} as hi
    on e.studentid = hi.studentid
    and e.academic_year = hi.academic_year
    and e._dbt_source_project = hi._dbt_source_project
    and hi.specprog_name = 'Home Instruction'
    and hi.rn_student_program_year_desc = 1
left join
    {{ ref("int_people__leadership_crosswalk") }} as hos
    on e.schoolid = hos.home_work_location_powerschool_school_id
left join
    {{ ref("int_overgrad__students") }} as ovg
    on e.salesforce_contact_id = ovg.external_student_id
    and e._dbt_source_project = ovg._dbt_source_project
left join
    {{ ref("int_powerschool__ada_term_pivot") }} as ada
    on e.studentid = ada.studentid
    and e.academic_year = ada.academic_year
    and e._dbt_source_project = ada._dbt_source_project
left join
    {{ ref("int_powerschool__ada_term_pivot") }} as adapy
    on e.studentid = adapy.studentid
    and e.academic_year = (adapy.academic_year + 1)
    and e._dbt_source_project = adapy._dbt_source_project
left join
    {{ ref("int_powerschool__gpa_cumulative") }} as gc
    on e.studentid = gc.studentid
    and e.schoolid = gc.schoolid
    and e._dbt_source_project = gc._dbt_source_project
left join
    next_year_school as ny
    on e.student_number = ny.student_number
    and e.academic_year = ny.academic_year
left join
    graduation_pathway_m as mc
    on e.students_dcid = mc.studentsdcid
    and e._dbt_source_project = mc._dbt_source_project
left join
    finalsite_enrollment_type_calc as fs
    on e.academic_year = fs.academic_year
    and e.student_number = fs.student_number
    and e._dbt_source_project = fs._dbt_source_project
left join
    {{ ref("base_powerschool__course_enrollments") }} as sip
    on e.student_number = sip.students_student_number
    and e.academic_year = sip.cc_academic_year
    and e._dbt_source_project = sip._dbt_source_project
    and sip.courses_course_number = 'SEM01099G1'
    and sip.rn_course_number_year = 1
    and not sip.is_dropped_section
left join es_grad as eg on e.student_number = eg.student_number and eg.rn = 1
left join
    {{ ref("int_students__contacts_pivot") }} as sc
    on e.student_number = sc.student_number
    and e._dbt_source_project = sc._dbt_source_project
