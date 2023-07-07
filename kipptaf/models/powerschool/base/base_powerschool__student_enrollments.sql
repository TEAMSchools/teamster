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
    ),

    all_regions as (
        select
            seu.*,
            initcap(
                regexp_extract(seu._dbt_source_relation, r'kipp(\w+)_\w+')
            ) as region,

            suf.fleid,
            suf.newark_enrollment_number,
            suf.infosnap_id,
            suf.infosnap_opt_in,
            suf.media_release,
            suf.rides_staff,
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
            nj.lepbegindate,
            nj.lependdate,

            sr.mail as advisor_email,
            sr.communication_business_mobile as advisor_phone,

            null as student_web_id,
            null as student_web_password,
        from student_enrollments_union as seu
        left join
            {{ ref("stg_powerschool__u_studentsuserfields") }} as suf
            on seu.students_dcid = suf.studentsdcid
            and {{ union_dataset_join_clause(left_alias="seu", right_alias="suf") }}
        left join
            {{ ref("stg_powerschool__s_nj_stu_x") }} as nj
            on seu.students_dcid = nj.studentsdcid
            and {{ union_dataset_join_clause(left_alias="seu", right_alias="nj") }}
        left join
            {{ ref("base_people__staff_roster") }} as sr
            on seu.advisor_teachernumber = sr.powerschool_teacher_number
    {# left join
    {{ ref("stg_students__access_accounts") }} as saa
    on seu.student_number = saa.student_number #}
    )

select
    ar._dbt_source_relation,
    ar.studentid,
    ar.students_dcid,
    ar.student_number,
    ar.state_studentnumber,
    ar.yearid,
    ar.academic_year,
    ar.schoolid,
    ar.school_name,
    ar.school_abbreviation,
    ar.reporting_schoolid,
    ar.reporting_school_name,
    ar.school_level,
    ar.region,
    ar.is_self_contained,
    ar.is_out_of_district,
    ar.grade_level,
    ar.grade_level_prev,
    ar.lastfirst,
    ar.first_name,
    ar.middle_name,
    ar.last_name,
    ar.entrydate,
    ar.exitdate,
    ar.entrycode,
    ar.exitcode,
    ar.exit_code_kf,
    ar.exit_code_ts,
    ar.exitcomment,
    ar.enroll_status,
    ar.cohort,
    ar.dob,
    ar.gender,
    ar.ethnicity,
    ar.track,
    ar.fteid,
    ar.is_homeless,
    ar.rn_year,
    ar.rn_school,
    ar.rn_all,
    ar.rn_undergrad,
    ar.is_retained_year,
    ar.is_retained_ever,
    ar.year_in_school,
    ar.year_in_network,
    ar.entry_schoolid,
    ar.entry_grade_level,
    ar.highest_grade_level_achieved,
    ar.street,
    ar.city,
    ar.state,
    ar.zip,
    ar.advisory_name,
    ar.advisor_teachernumber,
    ar.advisor_lastfirst,
    ar.home_phone,
    ar.contact_1_name,
    ar.contact_1_phone_home,
    ar.contact_1_phone_mobile,
    ar.contact_1_phone_daytime,
    ar.contact_1_email_current,
    ar.contact_2_name,
    ar.contact_2_phone_home,
    ar.contact_2_phone_mobile,
    ar.contact_2_phone_daytime,
    ar.contact_2_email_current,
    ar.pickup_1_name,
    ar.pickup_1_phone_mobile,
    ar.pickup_2_name,
    ar.pickup_2_phone_mobile,
    ar.pickup_3_name,
    ar.pickup_3_phone_mobile,
    ar.is_enrolled_y1,
    ar.is_enrolled_oct01,
    ar.is_enrolled_oct15,
    ar.is_enrolled_recent,

    case
        when ar.region = 'Miami'
        then ar.lep_status
        when ar.lepbegindate is null
        then false
        when ar.lependdate < ar.entrydate
        then false
        when ar.lepbegindate <= ar.exitdate
        then true
        else false
    end as lep_status,

    if(
        ar.region = 'Miami', ar.spedlep, sped.special_education_code
    ) as special_education_code,
    if(ar.region = 'Miami', ar.spedlep, ifnull(sped.spedlep, 'No IEP')) as spedlep,

    tpd.total_balance as lunch_balance,

    upper(
        case
            when ar.region = 'Miami'
            then ar.lunch_status
            when
                ar.academic_year = {{ var("current_academic_year") }} and ar.rn_year = 1
            then if(tpd.is_directly_certified, 'F', ifd.eligibility_name)
            else ar.lunch_status
        end
    ) as lunch_status,
    case
        when ar.region = 'Miami'
        then ar.lunch_status
        when ar.academic_year = {{ var("current_academic_year") }} and ar.rn_year = 1
        then
            case
                when tpd.is_directly_certified
                then 'Direct Certification'
                when ifd.lunch_application_status is null
                then 'No Application'
                else ifd.lunch_application_status
            end
        else ar.lunch_status
    end as lunch_application_status,
from all_regions as ar
left join
    {{ ref("stg_edplan__njsmart_powerschool") }} as sped
    on ar.student_number = sped.student_number
    and ar.academic_year = sped.academic_year
    and {{ union_dataset_join_clause(left_alias="ar", right_alias="sped") }}
    and ar.academic_year = {{ var("current_academic_year") }}
left join
    {{ ref("stg_titan__person_data") }} as tpd
    on ar.student_number = tpd.person_identifier
    and ar.academic_year = tpd.academic_year
    and {{ union_dataset_join_clause(left_alias="ar", right_alias="tpd") }}
left join
    {{ ref("stg_titan__income_form_data") }} as ifd
    on ar.student_number = ifd.student_identifier
    and ar.academic_year = ifd.academic_year
    and {{ union_dataset_join_clause(left_alias="ar", right_alias="ifd") }}
