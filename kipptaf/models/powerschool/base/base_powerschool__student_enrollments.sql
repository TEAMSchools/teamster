with
    student_enrollments_union as (
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
    )

select
    seu._dbt_source_relation,
    seu.studentid,
    seu.students_dcid,
    seu.student_number,
    seu.state_studentnumber,
    seu.yearid,
    seu.academic_year,
    seu.schoolid,
    seu.school_name,
    seu.school_abbreviation,
    seu.reporting_schoolid,
    seu.reporting_school_name,
    seu.school_level,
    seu.is_self_contained,
    seu.is_out_of_district,
    seu.grade_level,
    seu.grade_level_prev,
    seu.lastfirst,
    seu.first_name,
    seu.middle_name,
    seu.last_name,
    seu.entrydate,
    seu.exitdate,
    seu.entrycode,
    seu.exitcode,
    seu.exit_code_kf,
    seu.exit_code_ts,
    seu.exitcomment,
    seu.enroll_status,
    seu.cohort,
    seu.dob,
    seu.gender,
    seu.ethnicity,
    seu.track,
    seu.fteid,
    seu.rn_year,
    seu.rn_school,
    seu.rn_all,
    seu.rn_undergrad,
    seu.is_retained_year,
    seu.is_retained_ever,
    seu.year_in_school,
    seu.year_in_network,
    seu.entry_schoolid,
    seu.entry_grade_level,
    seu.highest_grade_level_achieved,
    seu.street,
    seu.city,
    seu.state,
    seu.zip,
    seu.advisory_name,
    seu.advisor_teachernumber,
    seu.advisor_lastfirst,
    seu.home_phone,
    seu.contact_1_name,
    seu.contact_1_phone_home,
    seu.contact_1_phone_mobile,
    seu.contact_1_phone_daytime,
    seu.contact_1_email_current,
    seu.contact_2_name,
    seu.contact_2_phone_home,
    seu.contact_2_phone_mobile,
    seu.contact_2_phone_daytime,
    seu.contact_2_email_current,
    seu.is_enrolled_y1,
    seu.is_enrolled_oct01,
    seu.is_enrolled_oct15,
    seu.is_enrolled_recent,
    initcap(regexp_extract(seu._dbt_source_relation, r'kipp(\w+)_\w+')) as region,

    suf.newark_enrollment_number,
    ifnull(suf.is_504, false) as is_504,

    nj.districtcoderesident,
    nj.referral_date,
    nj.parental_consent_eval_date,
    nj.eligibility_determ_date,
    nj.initial_iep_meeting_date,
    nj.parent_consent_intial_iep_date,
    nj.annual_iep_review_meeting_date,
    nj.reevaluation_date,
    nj.parent_consent_obtain_code,
    nj.initial_process_delay_reason,
    nj.special_education_placement,
    nj.time_in_regular_program,
    nj.early_intervention_yn,
    nj.determined_ineligible_yn,
    nj.counseling_services_yn,
    nj.occupational_therapy_serv_yn,
    nj.physical_therapy_services_yn,
    nj.speech_lang_theapy_services_yn,
    nj.other_related_services_yn,
    case
        when nj.lepbegindate is null
        then false
        when nj.lependdate < seu.entrydate
        then false
        when nj.lepbegindate <= seu.exitdate
        then true
        else false
    end as lep_status,

    sped.special_education_code,
    ifnull(sped.spedlep, 'No IEP') as spedlep,

    tpd.total_balance as lunch_balance,

    upper(
        case
            when
                seu.academic_year = {{ var("current_academic_year") }}
                and seu.rn_year = 1
            then if(tpd.is_directly_certified, 'F', ifd.eligibility_name)
            else seu.lunch_status
        end
    ) as lunch_status,
    case
        when seu.academic_year = {{ var("current_academic_year") }} and seu.rn_year = 1
        then
            case
                when tpd.is_directly_certified
                then 'Direct Certification'
                when ifd.lunch_application_status is null
                then 'No Application'
                else ifd.lunch_application_status
            end
        else seu.lunch_status
    end as lunch_application_status,

    sr.mail as advisor_email,
    sr.communication_business_mobile as advisor_phone,

    null as student_web_id,
    null as student_web_password,
from student_enrollments_union seu
left join
    {{ ref("stg_powerschool__u_studentsuserfields") }} as suf
    on seu.students_dcid = suf.studentsdcid
    and {{ union_dataset_join_clause(left_alias="seu", right_alias="suf") }}
left join
    {{ ref("stg_powerschool__s_nj_stu_x") }} as nj
    on seu.students_dcid = nj.studentsdcid
    and {{ union_dataset_join_clause(left_alias="seu", right_alias="nj") }}
left join
    {{ ref("stg_edplan__njsmart_powerschool") }} as sped
    on seu.student_number = sped.student_number
    and seu.academic_year = sped.academic_year
    and {{ union_dataset_join_clause(left_alias="seu", right_alias="sped") }}
    and seu.academic_year = {{ var("current_academic_year") }}
left join
    {{ ref("stg_titan__person_data") }} as tpd
    on seu.student_number = tpd.person_identifier
    and seu.academic_year = tpd.academic_year
    and {{ union_dataset_join_clause(left_alias="seu", right_alias="tpd") }}
left join
    {{ ref("stg_titan__income_form_data") }} as ifd
    on seu.student_number = ifd.student_identifier
    and seu.academic_year = ifd.academic_year
    and {{ union_dataset_join_clause(left_alias="seu", right_alias="ifd") }}
left join
    {{ ref("base_people__staff_roster") }} as sr
    on seu.advisor_teachernumber = sr.powerschool_teacher_number
    {# left join
    {{ ref("stg_students__access_accounts") }} as saa
    on seu.student_number = saa.student_number #}
    
