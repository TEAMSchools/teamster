{{ config(enabled=(var("powerschool_external_source_type") == "sftp")) }}

select
    * except (
        studentsdcid,
        savings_529_optin,
        iep_registration_followup,
        lep_registration_followup,
        test_field,
        current_programid,
        aup_yn_1718,
        incorrect_region_grad_student
    ),

    /* column transformations */
    studentsdcid.int_value as studentsdcid,
    savings_529_optin.int_value as savings_529_optin,
    iep_registration_followup.int_value as iep_registration_followup,
    lep_registration_followup.int_value as lep_registration_followup,
    test_field.int_value as test_field,
    current_programid.int_value as current_programid,
    aup_yn_1718.int_value as aup_yn_1718,
    incorrect_region_grad_student.int_value as incorrect_region_grad_student,
from {{ source("powerschool_sftp", "src_powerschool__u_def_ext_students") }}
