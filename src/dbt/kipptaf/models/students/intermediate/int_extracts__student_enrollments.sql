{% set invalid_lunch_status = ["", "NoD", "1", "2"] %}

with
    mia_territory as (
        select
            _dbt_source_relation,
            roster_name as territory,
            student_school_id,

            row_number() over (
                partition by _dbt_source_relation, student_school_id
                order by roster_id asc
            ) as rn_territory,

        from {{ ref("int_deanslist__roster_assignments") }}
        where school_id = 472 and roster_type = 'House' and active = 'Y'
<<<<<<< HEAD
=======
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
    ),

    finalsite_enrollment_type_calc as (
        select
            _dbt_source_relation,
            academic_year,
            student_number,

            if(
                sum(date_diff(exitdate, entrydate, day)) >= 7, 'Returning', 'New'
            ) as next_year_enrollment_type,

        from {{ ref("base_powerschool__student_enrollments") }}
        where grade_level != 99
        group by _dbt_source_relation, academic_year, student_number
>>>>>>> main
    )

select
    e.* except (
        `state`,
        advisory_section_number,
        email,
        first_name,
        grad_iep_exempt_overall,
        last_name,
        lastfirst,
        lunchstatus,
        middle_name,
        school_abbreviation,
        spedlep,
        state_studentnumber
    ),

    e.lastfirst as student_name,
    e.last_name as student_last_name,
    e.first_name as student_first_name,
    e.middle_name as student_middle_name,
    e.school_abbreviation as school,
    e.advisory_section_number as team,

    lc.region as region_official_name,
    lc.deanslist_school_id,

    hos.head_of_school_preferred_name_lastfirst as hos,
    hos.school_leader_preferred_name_lastfirst as school_leader,
    hos.school_leader_sam_account_name as school_leader_tableau_username,

    sr.mail as advisor_email,
    sr.work_cell as advisor_phone,

    adb.contact_id as salesforce_contact_id,
    adb.contact_kipp_hs_class as salesforce_contact_kipp_hs_class,
    adb.contact_graduation_year as salesforce_contact_graduation_year,
    adb.contact_college_match_display_gpa as salesforce_contact_college_match_gpa,
    adb.contact_owner_id as salesforce_contact_owner_id,
    adb.contact_owner_name as salesforce_contact_owner_name,
    adb.contact_owner_email as salesforce_contact_owner_email,
    adb.contact_owner_phone as salesforce_contact_owner_phone,

    ovg.best_guess_pathway,

    mt.territory,

    tpd.total_balance as lunch_balance,

    'KTAF' as district,

    /* PowerSchool */
    coalesce(e.contact_1_email_current, e.contact_2_email_current) as guardian_email,

    concat(e.region, e.school_level) as region_school_level,

<<<<<<< HEAD
    concat(
        e.academic_year, '-', right(cast(e.academic_year + 1 as string), 2)
    ) as academic_year_display,
=======
    if(
        e.grade_level = 99, null, fs.next_year_enrollment_type
    ) as next_year_enrollment_type,

    if(ovg.fafsa_opt_out is not null, 'Yes', 'No') as overgrad_fafsa_opt_out,

    if(
        e.enroll_status = 0 and mc.grad_iep_exempt_overall is not null,
        mc.grad_iep_exempt_overall,
        'Not Grad IEP Exempt'
    ) as grad_iep_exempt_status_overall,
>>>>>>> main

    if(e.spedlep like 'SPED%', 'Has IEP', 'No IEP') as iep_status,
    if(e.lep_status, 'ML', 'Not ML') as ml_status,
    if(e.is_504, 'Has 504', 'No 504') as status_504,
    if(
        e.is_self_contained, 'Self-contained', 'Not self-contained'
    ) as self_contained_status,
    if(e.region = 'Miami', e.fleid, e.state_studentnumber) as state_studentnumber,
    if(
        e.region = 'Miami', e.state_studentnumber, null
    ) as secondary_state_studentnumber,
    if(
        e.enroll_status = 0 and e.grad_iep_exempt_overall is not null,
        e.grad_iep_exempt_overall,
        'Not Grad IEP Exempt'
    ) as grad_iep_exempt_status_overall,

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

    /* Student accounts */
    if(e.region = 'Paterson', null, sl.username) as student_web_id,
    if(e.region = 'Paterson', null, sl.default_password) as student_web_password,
    if(e.region = 'Paterson', e.email, sl.google_email) as student_email,

    /* EasyIEP */
    if(
        e.region = 'Miami', e.spedlep, sped.special_education_code
    ) as special_education_code,

    coalesce(if(e.region = 'Miami', e.spedlep, sped.spedlep), 'No IEP') as spedlep,

    /* FLDOE */
    if(e.region = 'Miami' and fte.survey_2 is not null, true, false) as is_fldoe_fte_2,
    if(e.region = 'Miami' and fte.survey_3 is not null, true, false) as is_fldoe_fte_3,
    if(
        e.region = 'Miami' and fte.survey_2 is not null and fte.survey_3 is not null,
        true,
        false
    ) as is_fldoe_fte_all,

    /* ADB/Overgrad */
    coalesce(
        adb.contact_college_match_gpa_band, 'No GPA'
    ) as salesforce_contact_college_match_gpa_band,
    coalesce(adb.contact_kipp_hs_class, e.cohort) as ktc_cohort,

    if(ovg.fafsa_opt_out is not null, 'Yes', 'No') as overgrad_fafsa_opt_out,

    if(
        adb.contact_latest_fafsa_date is not null, 'Yes', 'No'
    ) as salesforce_contact_has_fafsa,

    if(
        adb.contact_latest_fafsa_date is not null or ovg.fafsa_opt_out is not null,
        true,
        false
    ) as met_fafsa_requirement,

    case
        when
            e.academic_year >= 2024  -- 1st year tracking this
            and e.grade_level = 12
            and adb.contact_latest_fafsa_date is not null
            and ovg.fafsa_opt_out is not null
        then 'Salesforce/Overgrad has FAFSA opt-out mismatch'
        else 'No issues'
    end as fafsa_status_mismatch_category,

    /* Titan */
    case
        when e.lunchstatus in unnest({{ invalid_lunch_status }})
        then null
        when e.academic_year < {{ var("current_academic_year") }}
        then e.lunchstatus
        when e.region = 'Miami'
        then e.lunchstatus
        when e.rn_year = 1
        then coalesce(if(tpd.is_directly_certified, 'F', null), tpd.eligibility_name)
    end as lunch_status,

    case
        when e.academic_year < {{ var("current_academic_year") }}
        then e.lunchstatus
        when e.region = 'Miami'
        then e.lunchstatus
        when e.rn_year = 1
        then
            case
                when tpd.is_directly_certified
                then 'Direct Certification'
                when tpd.eligibility_determination_reason is null
                then 'No Application'
                else tpd.eligibility || ' - ' || tpd.eligibility_determination_reason
            end
    end as lunch_application_status,
from {{ ref("base_powerschool__student_enrollments") }} as e
left join
    {{ ref("stg_google_sheets__people__location_crosswalk") }} as lc
    on e.school_name = lc.name
left join
    {{ ref("stg_people__student_logins") }} as sl
    on e.student_number = sl.student_number
left join
    {{ ref("int_people__staff_roster") }} as sr
    on e.advisor_teachernumber = sr.powerschool_teacher_number
left join
    {{ ref("int_people__leadership_crosswalk") }} as hos
    on e.schoolid = hos.home_work_location_powerschool_school_id
left join
    {{ ref("int_kippadb__contact") }} as adb
    on e.student_number = adb.contact_school_specific_id
left join
    {{ ref("int_overgrad__students") }} as ovg
    on adb.contact_id = ovg.external_student_id
    and {{ union_dataset_join_clause(left_alias="e", right_alias="ovg") }}
left join
    {{ ref("stg_titan__person_data") }} as tpd
    on e.student_number = tpd.person_identifier
    and e.academic_year = tpd.academic_year
    and {{ union_dataset_join_clause(left_alias="e", right_alias="tpd") }}
left join
    {{ ref("int_edplan__njsmart_powerschool_union") }} as sped
    on e.student_number = sped.student_number
    and e.academic_year = sped.academic_year
    and {{ union_dataset_join_clause(left_alias="e", right_alias="sped") }}
    and sped.rn_student_year_desc = 1
left join
    {{ ref("int_fldoe__fte_pivot") }} as fte
    on e.state_studentnumber = fte.student_id
    and e.academic_year = fte.academic_year
    and {{ union_dataset_join_clause(left_alias="e", right_alias="fte") }}
left join
    mia_territory as mt
    on e.student_number = mt.student_school_id
    and {{ union_dataset_join_clause(left_alias="e", right_alias="mt") }}
    and mt.rn_territory = 1
<<<<<<< HEAD
=======
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
    finalsite_enrollment_type_calc as fs
    on e.academic_year = fs.academic_year
    and e.student_number = fs.student_number
    and {{ union_dataset_join_clause(left_alias="e", right_alias="fs") }}
left join
    {{ ref("base_powerschool__course_enrollments") }} as sip
    on e.student_number = sip.students_student_number
    and e.academic_year = sip.cc_academic_year
    and {{ union_dataset_join_clause(left_alias="e", right_alias="sip") }}
    and sip.courses_course_number = 'SEM01099G1'
    and sip.rn_course_number_year = 1
    and not sip.is_dropped_section
left join es_grad as eg on e.student_number = eg.student_number and eg.rn = 1
>>>>>>> main
