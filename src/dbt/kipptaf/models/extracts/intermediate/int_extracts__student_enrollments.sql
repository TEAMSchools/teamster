{{ config(materialized="table") }}

with
    ms_grad_sub as (
        select
            _dbt_source_relation,
            student_number,
            school_abbreviation as ms_attended,

            row_number() over (
                partition by student_number order by exitdate desc
            ) as rn,

        from {{ ref("base_powerschool__student_enrollments") }}
        where school_level = 'MS'
    ),

    es_grad_sub as (
        select
            _dbt_source_relation,
            student_number,
            school_abbreviation as es_attended,

            row_number() over (
                partition by student_number order by exitdate desc
            ) as rn,

        from {{ ref("base_powerschool__student_enrollments") }}
        where school_level = 'ES'
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

    overgrad_fafsa as (
        select
            p._dbt_source_relation,

            s.external_student_id as salesforce_contact_id,

            if(p.fafsa_opt_out is null, 'No', 'Yes') as overgrad_fafsa_opt_out,

        from {{ ref("int_overgrad__custom_fields_pivot") }} as p
        inner join
            {{ ref("stg_overgrad__students") }} as s
            on p.id = s.id
            and {{ union_dataset_join_clause(left_alias="p", right_alias="s") }}
        where p._dbt_source_model = 'stg_overgrad__students'
    ),

    m_ps_code as (
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
            end as is_grad_iep_exempt_overall,

        from {{ ref("stg_powerschool__s_nj_stu_x") }}
        where graduation_pathway_math = 'M' or graduation_pathway_ela = 'M'
    )

select
    e._dbt_source_relation,
    e.studentid,
    e.students_dcid,
    e.student_number,
    e.lastfirst as student_name,
    e.last_name as student_last_name,
    e.first_name as student_first_name,
    e.middle_name as student_middle_name,
    e.enroll_status,
    e.cohort,
    e.yearid,
    e.academic_year,
    e.entrydate,
    e.exitdate,
    e.exitcode,
    e.exitcomment,
    e.region,
    e.school_level,
    e.schoolid,
    e.reporting_schoolid,
    e.school_name,
    e.school_abbreviation as school,
    e.grade_level,
    e.grade_level_prev,
    e.advisory_name,
    e.advisory_section_number as team,
    e.advisor_lastfirst,
    e.student_email_google as student_email,
    e.student_web_id,
    e.student_web_password,
    e.gender,
    e.ethnicity,
    e.fedethnicity,
    e.dob,
    e.lunch_status,
    e.spedlep,
    e.special_education_code,
    e.lep_status,
    e.gifted_and_talented,
    e.is_504,
    e.is_homeless,
    e.is_out_of_district,
    e.is_self_contained,
    e.is_enrolled_oct01,
    e.is_enrolled_recent,
    e.is_enrolled_y1,
    e.is_retained_year,
    e.is_retained_ever,
    e.is_fldoe_fte_all,
    e.year_in_school,
    e.year_in_network,
    e.boy_status,
    e.rn_year,
    e.rn_undergrad,
    e.rn_all,
    e.code_location,
    e.salesforce_contact_id as salesforce_id,
    e.salesforce_contact_df_has_fafsa as has_fafsa,
    e.salesforce_contact_college_match_display_gpa as college_match_gpa,
    e.salesforce_contact_college_match_gpa_band as college_match_gpa_bands,
    e.salesfoce_contact_owner_name as contact_owner_name,
    e.ktc_cohort,
    e.illuminate_student_id,
    e.contact_1_name,
    e.contact_1_phone_home,
    e.contact_1_phone_mobile,
    e.contact_1_email_current,
    e.contact_2_name,
    e.contact_2_phone_home,
    e.contact_2_phone_mobile,
    e.contact_2_email_current,
    e.is_fldoe_fte_2,

    lc.region as region_official_name,
    lc.deanslist_school_id,

    m.ms_attended,

    es.es_attended,

    mt.territory,

    hos.head_of_school_preferred_name_lastfirst as hos,

    ovg.overgrad_fafsa_opt_out,

    ada.ada_term_q1 as ada_unweighted_term_q1,
    ada.ada_semester_s1 as ada_unweighted_semester_s1,
    ada.ada_year as unweighted_ada,
    ada.ada_weighted_term_q1,
    ada.ada_weighted_semester_s1,
    ada.ada_weighted_year as weighted_ada,
    ada.sum_absences_year as absences_unexcused_year,

    adapy.ada_year as ada_unweighted_year_prev,
    adapy.ada_weighted_year as ada_weighted_year_prev,

    ny.next_year_school,
    ny.next_year_schoolid,

    if(
        e.enroll_status = 0 and mc.is_grad_iep_exempt_overall is not null,
        mc.is_grad_iep_exempt_overall,
        null
    ) as is_grad_iep_exempt_overall,

    'KTAF' as district,

    concat(e.region, e.school_level) as region_school_level,

    coalesce(e.contact_1_email_current, e.contact_2_email_current) as guardian_email,

    cast(e.academic_year as string)
    || '-'
    || right(cast(e.academic_year + 1 as string), 2) as academic_year_display,

    if(e.spedlep like 'SPED%', 'Has IEP', 'No IEP') as iep_status,

    if(e.region = 'Miami', e.fleid, e.state_studentnumber) as state_studentnumber,

    /* starting SY26, HS uses weighted ADA */
    if(
        e.school_level = 'HS' and e.academic_year >= 2025,
        ada.ada_weighted_year,
        ada.ada_year
    ) as `ada`,

    if(
        e.salesforce_contact_df_has_fafsa = 'Yes' or ovg.overgrad_fafsa_opt_out = 'Yes',
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
        when e.region in ('Camden', 'Newark')
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
            and ovg.overgrad_fafsa_opt_out = 'Yes'
        then 'Salesforce/Overgrad has FAFSA opt-out mismatch'
        else 'No issues'
    end as fafsa_status_mismatch_category,

from {{ ref("base_powerschool__student_enrollments") }} as e
left join {{ ref("stg_people__location_crosswalk") }} as lc on e.school_name = lc.name
left join
    ms_grad_sub as m
    on e.student_number = m.student_number
    and {{ union_dataset_join_clause(left_alias="e", right_alias="m") }}
    and m.rn = 1
left join
    es_grad_sub as es
    on e.student_number = es.student_number
    and {{ union_dataset_join_clause(left_alias="e", right_alias="es") }}
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
    {{ ref("int_people__leadership_crosswalk") }} as hos
    on e.schoolid = hos.home_work_location_powerschool_school_id
left join
    overgrad_fafsa as ovg
    on e.salesforce_contact_id = ovg.salesforce_contact_id
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
    next_year_school as ny
    on e.student_number = ny.student_number
    and e.academic_year = ny.academic_year
left join
    m_ps_code as mc
    on e.students_dcid = mc.studentsdcid
    and {{ union_dataset_join_clause(left_alias="e", right_alias="mc") }}
where e.grade_level != 99
