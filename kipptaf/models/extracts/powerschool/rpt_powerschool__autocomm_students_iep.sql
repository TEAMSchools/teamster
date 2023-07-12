select
    student_number,
    format_date('%m/%d/%Y', nj_se_referraldate) as `S_NJ_STU_X__Referral_Date`,
    format_date(
        '%m/%d/%Y', nj_se_parentalconsentdate
    ) as `S_NJ_STU_X__Parental_Consent_Eval_Date`,
    format_date(
        '%m/%d/%Y', nj_se_eligibilityddate
    ) as `S_NJ_STU_X__Eligibility_Determ_Date`,
    null as `S_NJ_STU_X__Early_Intervention_YN`,
    format_date(
        '%m/%d/%Y', nj_se_initialiepmeetingdate
    ) as `S_NJ_STU_X__Initial_IEP_Meeting_Date`,
    nj_se_parentalconsentobtained as `S_NJ_STU_X__Parent_Consent_Obtain_Code`,
    format_date(
        '%m/%d/%Y', nj_se_consenttoimplementdate
    ) as `S_NJ_STU_X__Parent_Consent_Intial_IEP_Date`,
    format_date(
        '%m/%d/%Y', nj_se_lastiepmeetingdate
    ) as `S_NJ_STU_X__Annual_IEP_Review_Meeting_Date`,
    special_education_code as `S_NJ_STU_X__SpecialEd_Classification`,
    format_date('%m/%d/%Y', nj_se_reevaluationdate) as `S_NJ_STU_X__Reevaluation_Date`,
    nj_se_delayreason as `S_NJ_STU_X__Initial_Process_Delay_Reason`,
    nj_se_placement as `S_NJ_STU_X__Special_Education_Placement`,
    nj_timeinregularprogram as `S_NJ_STU_X__Time_In_Regular_Program`,
    if(ti_serv_counseling, 1, 0) as `S_NJ_STU_X__Counseling_Services_YN`,
    if(ti_serv_occup, 1, 0) as `S_NJ_STU_X__Occupational_Therapy_Serv_YN`,
    if(ti_serv_physical, 1, 0) as `S_NJ_STU_X__Physical_Therapy_Services_YN`,
    if(ti_serv_speech, 1, 0) as `S_NJ_STU_X__Speech_Lang_Theapy_Services_YN`,
    if(ti_serv_other, 1, 0) as `S_NJ_STU_X__Other_Related_Services_YN`,
    spedlep as `STUDENTCOREFIELDS__SPEDLEP`,
    if(
        special_education_code = '00', '1', '0'
    ) as `S_NJ_STU_X__Determined_Ineligible_YN`,
    regexp_extract(_dbt_source_relation, r'(kipp\w+)_\w+') as code_location,
from {{ ref("stg_edplan__njsmart_powerschool") }}
where
    academic_year = {{ var("current_academic_year") }}
    and rn_student_year_desc = 1
    and student_number is not null
