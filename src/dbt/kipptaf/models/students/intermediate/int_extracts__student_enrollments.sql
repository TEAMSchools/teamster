with
    esms_attend as (
        select
            _dbt_source_relation,
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
            _dbt_source_relation,
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
            _dbt_source_relation,
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

    lc.region as region_official_name,
    lc.deanslist_school_id,

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
    gc.core_cumulative_y1_gpa,
    gc.earned_credits_cum,
    gc.earned_credits_cum_projected,
    gc.potential_credits_cum,

    ny.next_year_school,
    ny.next_year_schoolid,

    'KTAF' as district,

    concat(e.region, e.school_level) as region_school_level,

    coalesce(e.contact_1_email_current, e.contact_2_email_current) as guardian_email,

    cast(e.academic_year as string)
    || '-'
    || right(cast(e.academic_year + 1 as string), 2) as academic_year_display,

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
    -- added this temporarily because we dont have alignment on ids
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
        -- hardcode year because PAT wasnt incorporated until SY2025-26
        e.region = 'Paterson' and e.academic_year <= 2024,
        e.prevstudentid,
        e.student_number
    ) as student_number_historic,

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
            e.academic_year = 2025
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
    {{ ref("stg_google_sheets__people__location_crosswalk") }} as lc
    on e.school_name = lc.name
left join
    esms_attend as m
    on e.student_number = m.student_number
    and {{ union_dataset_join_clause(left_alias="e", right_alias="m") }}
    and m.school_level = 'MS'
    and m.rn = 1
left join
    esms_attend as es
    on e.student_number = es.student_number
    and {{ union_dataset_join_clause(left_alias="e", right_alias="es") }}
    and es.school_level = 'ES'
    and es.rn = 1
left join
    mia_territory as mt
    on e.student_number = mt.student_school_id
    and {{ union_dataset_join_clause(left_alias="e", right_alias="mt") }}
    and mt.rn_territory = 1
left join
    {{ ref("int_powerschool__spenrollments") }} as cs
    on e.studentid = cs.studentid
    and e.academic_year = cs.academic_year
    and {{ union_dataset_join_clause(left_alias="e", right_alias="cs") }}
    and cs.specprog_name = 'Counseling Services'
    and cs.rn_student_program_year_desc = 1
left join
    {{ ref("int_powerschool__spenrollments") }} as ath
    on e.studentid = ath.studentid
    and e.academic_year = ath.academic_year
    and {{ union_dataset_join_clause(left_alias="e", right_alias="ath") }}
    and ath.specprog_name = 'Student Athlete'
    and ath.rn_student_program_year_desc = 1
left join
    {{ ref("int_powerschool__spenrollments") }} as tut
    on e.studentid = tut.studentid
    and e.academic_year = tut.academic_year
    and {{ union_dataset_join_clause(left_alias="e", right_alias="tut") }}
    and tut.specprog_name = 'Tutoring'
    and tut.rn_student_program_year_desc = 1
left join
    {{ ref("int_powerschool__spenrollments") }} as hi
    on e.studentid = hi.studentid
    and e.academic_year = hi.academic_year
    and {{ union_dataset_join_clause(left_alias="e", right_alias="hi") }}
    and hi.specprog_name = 'Home Instruction'
    and hi.rn_student_program_year_desc = 1
left join
    {{ ref("int_people__leadership_crosswalk") }} as hos
    on e.schoolid = hos.home_work_location_powerschool_school_id
left join
    {{ ref("int_overgrad__students") }} as ovg
    on e.salesforce_contact_id = ovg.external_student_id
    and {{ union_dataset_join_clause(left_alias="e", right_alias="ovg") }}
left join
    {{ ref("int_powerschool__ada_term_pivot") }} as ada
    on e.studentid = ada.studentid
    and e.academic_year = ada.academic_year
    and {{ union_dataset_join_clause(left_alias="e", right_alias="ada") }}
left join
    {{ ref("int_powerschool__ada_term_pivot") }} as adapy
    on e.studentid = adapy.studentid
    and e.academic_year = (adapy.academic_year + 1)
    and {{ union_dataset_join_clause(left_alias="e", right_alias="adapy") }}
left join
    {{ ref("int_powerschool__gpa_cumulative") }} as gc
    on e.studentid = gc.studentid
    and e.schoolid = gc.schoolid
    and {{ union_dataset_join_clause(left_alias="e", right_alias="gc") }}
left join
    next_year_school as ny
    on e.student_number = ny.student_number
    and e.academic_year = ny.academic_year
left join
    graduation_pathway_m as mc
    on e.students_dcid = mc.studentsdcid
    and {{ union_dataset_join_clause(left_alias="e", right_alias="mc") }}
left join
    {{ ref("base_powerschool__course_enrollments") }} as sip
    on e.student_number = sip.students_student_number
    and e.academic_year = sip.cc_academic_year
    and {{ union_dataset_join_clause(left_alias="e", right_alias="sip") }}
    and sip.courses_course_number = 'SEM01099G1'
    and sip.rn_course_number_year = 1
    and not sip.is_dropped_section
left join es_grad as eg on e.student_number = eg.student_number and eg.rn = 1
