with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_powerschool",
                        "base_powerschool__student_enrollments",
                    ),
                    source(
                        "kippcamden_powerschool",
                        "base_powerschool__student_enrollments",
                    ),
                    source(
                        "kippmiami_powerschool",
                        "base_powerschool__student_enrollments",
                    ),
                    source(
                        "kipppaterson_powerschool",
                        "base_powerschool__student_enrollments",
                    ),
                ]
            )
        }}
    ),

    esms_grad as (
        select
            _dbt_source_relation,
            student_number,
            school_level,
            school_abbreviation,

            row_number() over (
                partition by _dbt_source_relation, student_number, school_level
                order by exitdate desc
            ) as rn,
        from union_relations
    ),

    next_year_school as (
        select
            _dbt_source_relation,
            student_number,
            academic_year,

            lead(school_abbreviation, 1) over (
                partition by _dbt_source_relation, student_number
                order by academic_year asc
            ) as next_year_school,

            lead(schoolid, 1) over (
                partition by _dbt_source_relation, student_number
                order by academic_year asc
            ) as next_year_schoolid,
        from union_relations
        where rn_year = 1
    )

select
    ar.* except (lep_status),

    /* regional differences */
    suf.fleid,
    suf.newark_enrollment_number,
    suf.infosnap_id,
    suf.infosnap_opt_in,
    suf.media_release,
    suf.rides_staff,

    njs.districtcoderesident,
    njs.referral_date,
    njs.parental_consent_eval_date,
    njs.eligibility_determ_date,
    njs.initial_iep_meeting_date,
    njs.parent_consent_intial_iep_date,
    njs.annual_iep_review_meeting_date,
    njs.reevaluation_date,
    njs.parent_consent_obtain_code,
    njs.initial_process_delay_reason,
    njs.special_education_placement,
    njs.time_in_regular_program,
    njs.early_intervention_yn,
    njs.determined_ineligible_yn,
    njs.counseling_services_yn,
    njs.occupational_therapy_serv_yn,
    njs.physical_therapy_services_yn,
    njs.speech_lang_theapy_services_yn,
    njs.other_related_services_yn,
    njs.lepbegindate,
    njs.lependdate,
    njs.lep_tf,
    njs.liep_parent_refusal_date,
    njs.programtypecode,
    njs.home_language,

    se.email,

    m.school_abbreviation as ms_attended,

    es.school_abbreviation as es_attended,

    ny.next_year_school,
    ny.next_year_schoolid,

    hi.enter_date as home_instruction_enter_date,
    hi.exit_date as home_instruction_exit_date,
    hi.sp_comment as home_instruction_sp_comment,

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

    coalesce(
        njs.gifted_and_talented, suf.gifted_and_talented, 'N'
    ) as gifted_and_talented,

    coalesce(njr.pid_504_tf, suf.is_504, false) as is_504,

    regexp_extract(ar._dbt_source_relation, r'(kipp\w+)_') as code_location,

    initcap(regexp_extract(ar._dbt_source_relation, r'kipp(\w+)_')) as region,

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

    /* starting SY26, HS uses weighted ADA */
    if(
        ar.school_level = 'HS' and ar.academic_year >= 2025,
        ada.ada_weighted_year,
        ada.ada_year
    ) as `ada`,

    case
        when ar._dbt_source_relation like '%kippmiami%'
        then ar.lep_status
        when njs.lepbegindate is null
        then false
        when njs.lependdate < ar.entrydate
        then false
        when njs.lepbegindate <= ar.exitdate
        then true
        else false
    end as lep_status,

    case
        when njs.graduation_pathway_math = 'M' and njs.graduation_pathway_ela = 'M'
        then 'Yes'
        when njs.graduation_pathway_math = 'M' and njs.graduation_pathway_ela != 'M'
        then 'Math only. No ELA match.'
        when njs.graduation_pathway_math != 'M' and njs.graduation_pathway_ela = 'M'
        then 'ELA only. No Math match.'
    end as grad_iep_exempt_overall,

    case
        /* starting SY26, HS uses weighted ADA */
        when
            ar.school_level = 'HS'
            and ar.academic_year >= 2025
            and ada.ada_weighted_year >= 0.80
        then true
        when
            ar.school_level = 'HS' and ar.academic_year <= 2024 and ada.ada_year >= 0.80
        then true
        when ada.ada_year >= 0.80
        then true
    end as ada_above_or_at_80,
from union_relations as ar
left join
    {{ ref("stg_powerschool__u_studentsuserfields") }} as suf
    on ar.students_dcid = suf.studentsdcid
    and {{ union_dataset_join_clause(left_alias="ar", right_alias="suf") }}
left join
    {{ ref("stg_powerschool__s_nj_stu_x") }} as njs
    on ar.students_dcid = njs.studentsdcid
    and {{ union_dataset_join_clause(left_alias="ar", right_alias="njs") }}
left join
    {{ ref("stg_powerschool__s_nj_ren_x") }} as njr
    on ar.reenrollments_dcid = njr.reenrollmentsdcid
    and {{ union_dataset_join_clause(left_alias="ar", right_alias="njr") }}
left join
    {{ ref("stg_powerschool__student_email") }} as se
    on ar.student_number = se.student_number
left join
    {{ ref("int_powerschool__spenrollments") }} as cs
    on ar.studentid = cs.studentid
    and ar.academic_year = cs.academic_year
    and {{ union_dataset_join_clause(left_alias="ar", right_alias="cs") }}
    and cs.specprog_name = 'Counseling Services'
    and cs.rn_student_program_year_desc = 1
left join
    {{ ref("int_powerschool__spenrollments") }} as ath
    on ar.studentid = ath.studentid
    and ar.academic_year = ath.academic_year
    and {{ union_dataset_join_clause(left_alias="ar", right_alias="ath") }}
    and ath.specprog_name = 'Student Athlete'
    and ath.rn_student_program_year_desc = 1
left join
    {{ ref("int_powerschool__spenrollments") }} as tut
    on ar.studentid = tut.studentid
    and ar.academic_year = tut.academic_year
    and {{ union_dataset_join_clause(left_alias="ar", right_alias="tut") }}
    and tut.specprog_name = 'Tutoring'
    and tut.rn_student_program_year_desc = 1
left join
    {{ ref("int_powerschool__spenrollments") }} as hi
    on ar.studentid = hi.studentid
    and ar.academic_year = hi.academic_year
    and {{ union_dataset_join_clause(left_alias="ar", right_alias="hi") }}
    and hi.specprog_name = 'Home Instruction'
    and hi.rn_student_program_year_desc = 1
left join
    {{ ref("int_powerschool__ada_term_pivot") }} as ada
    on ar.studentid = ada.studentid
    and ar.academic_year = ada.academic_year
    and {{ union_dataset_join_clause(left_alias="ar", right_alias="ada") }}
left join
    {{ ref("int_powerschool__ada_term_pivot") }} as adapy
    on ar.studentid = adapy.studentid
    and ar.academic_year = (adapy.academic_year + 1)
    and {{ union_dataset_join_clause(left_alias="ar", right_alias="adapy") }}
left join
    {{ ref("int_powerschool__gpa_cumulative") }} as gc
    on ar.studentid = gc.studentid
    and ar.schoolid = gc.schoolid
    and {{ union_dataset_join_clause(left_alias="ar", right_alias="gc") }}
left join
    {{ ref("base_powerschool__course_enrollments") }} as sip
    on ar.student_number = sip.students_student_number
    and ar.academic_year = sip.cc_academic_year
    and {{ union_dataset_join_clause(left_alias="ar", right_alias="sip") }}
    and sip.courses_course_number = 'SEM01099G1'
    and sip.rn_course_number_year = 1
    and not sip.is_dropped_section
left join
    esms_grad as m
    on ar.student_number = m.student_number
    and {{ union_dataset_join_clause(left_alias="ar", right_alias="m") }}
    and m.school_level = 'MS'
    and m.rn = 1
left join
    esms_grad as es
    on ar.student_number = es.student_number
    and {{ union_dataset_join_clause(left_alias="ar", right_alias="es") }}
    and es.school_level = 'ES'
    and es.rn = 1
left join
    next_year_school as ny
    on ar.student_number = ny.student_number
    and ar.academic_year = ny.academic_year
    and {{ union_dataset_join_clause(left_alias="ar", right_alias="ny") }}
