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
                ]
            )
        }}
    ),

    with_region as (
        -- trunk-ignore(sqlfluff/AM04)
        select
            *,

            regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as code_location,
            initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_')) as region,
        from union_relations
    )

select
    ar.* except (lep_status, lunch_status, spedlep),

    sr.mail as advisor_email,
    sr.work_cell as advisor_phone,

    sl.username as student_web_id,
    sl.default_password as student_web_password,
    sl.google_email as student_email_google,

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
    njs.gifted_and_talented,

    tpd.total_balance as lunch_balance,

    coalesce(njr.pid_504_tf, suf.is_504, false) as is_504,

    if(ar.region = 'Miami' and fte.survey_2 is not null, true, false) as is_fldoe_fte_2,
    if(ar.region = 'Miami' and fte.survey_3 is not null, true, false) as is_fldoe_fte_3,
    if(
        ar.region = 'Miami' and fte.survey_2 is not null and fte.survey_3 is not null,
        true,
        false
    ) as is_fldoe_fte_all,

    if(
        ar.region = 'Miami', ar.spedlep, sped.special_education_code
    ) as special_education_code,

    coalesce(if(ar.region = 'Miami', ar.spedlep, sped.spedlep), 'No IEP') as spedlep,

    case
        when ar.region = 'Miami'
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
        when ar.academic_year < {{ var("current_academic_year") }}
        then ar.lunch_status
        when ar.region = 'Miami'
        then ar.lunch_status
        when ar.rn_year = 1
        then coalesce(if(tpd.is_directly_certified, 'F', null), tpd.eligibility_name)
    end as lunch_status,

    case
        when ar.academic_year < {{ var("current_academic_year") }}
        then ar.lunch_status
        when ar.region = 'Miami'
        then ar.lunch_status
        when ar.rn_year = 1
        then
            case
                when tpd.is_directly_certified
                then 'Direct Certification'
                when tpd.eligibility_determination_reason is null
                then 'No Application'
                else tpd.eligibility || ' - ' || tpd.eligibility_determination_reason
            end
    end as lunch_application_status,
from with_region as ar
left join
    {{ ref("int_people__staff_roster") }} as sr
    on ar.advisor_teachernumber = sr.powerschool_teacher_number
left join
    {{ ref("stg_people__student_logins") }} as sl
    on ar.student_number = sl.student_number
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
    {{ ref("int_edplan__njsmart_powerschool_union") }} as sped
    on ar.student_number = sped.student_number
    and ar.academic_year = sped.academic_year
    and {{ union_dataset_join_clause(left_alias="ar", right_alias="sped") }}
    and sped.rn_student_year_desc = 1
left join
    {{ ref("stg_titan__person_data") }} as tpd
    on ar.student_number = tpd.person_identifier
    and ar.academic_year = tpd.academic_year
    and {{ union_dataset_join_clause(left_alias="ar", right_alias="tpd") }}
left join
    {{ ref("int_fldoe__fte_pivot") }} as fte
    on ar.state_studentnumber = fte.student_id
    and ar.academic_year = fte.academic_year
    and {{ union_dataset_join_clause(left_alias="ar", right_alias="fte") }}
