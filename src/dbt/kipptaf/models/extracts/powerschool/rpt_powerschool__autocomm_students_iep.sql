select  -- noqa: disable=ST06
    student_number,
    format_date('%m/%d/%Y', nj_se_referraldate) as s_nj_stu_x__referral_date,
    format_date(
        '%m/%d/%Y', nj_se_parentalconsentdate
    ) as s_nj_stu_x__parental_consent_eval_date,
    format_date(
        '%m/%d/%Y', nj_se_eligibilityddate
    ) as s_nj_stu_x__eligibility_determ_date,
    null as s_nj_stu_x__early_intervention_yn,
    format_date(
        '%m/%d/%Y', nj_se_initialiepmeetingdate
    ) as s_nj_stu_x__initial_iep_meeting_date,
    nj_se_parentalconsentobtained as s_nj_stu_x__parent_consent_obtain_code,
    format_date(
        '%m/%d/%Y', nj_se_consenttoimplementdate
    ) as s_nj_stu_x__parent_consent_intial_iep_date,
    format_date(
        '%m/%d/%Y', nj_se_lastiepmeetingdate
    ) as s_nj_stu_x__annual_iep_review_meeting_date,
    special_education_code as s_nj_stu_x__specialed_classification,
    format_date('%m/%d/%Y', nj_se_reevaluationdate) as s_nj_stu_x__reevaluation_date,
    nj_se_delayreason as s_nj_stu_x__initial_process_delay_reason,
    nj_se_placement as s_nj_stu_x__special_education_placement,
    nj_timeinregularprogram as s_nj_stu_x__time_in_regular_program,
    if(ti_serv_counseling = 'Y', 1, 0) as s_nj_stu_x__counseling_services_yn,
    if(ti_serv_occup = 'Y', 1, 0) as s_nj_stu_x__occupational_therapy_serv_yn,
    if(ti_serv_physical = 'Y', 1, 0) as s_nj_stu_x__physical_therapy_services_yn,
    if(ti_serv_speech = 'Y', 1, 0) as s_nj_stu_x__speech_lang_theapy_services_yn,
    if(ti_serv_other = 'Y', 1, 0) as s_nj_stu_x__other_related_services_yn,
    spedlep as studentcorefields__spedlep,
    if(special_education_code = '00', '1', '0') as s_nj_stu_x__determined_ineligible_yn,
    regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as code_location,
from {{ ref("stg_edplan__njsmart_powerschool") }}
where
    academic_year = {{ var("current_academic_year") }}
    and rn_student_year_desc = 1
    and student_number is not null
