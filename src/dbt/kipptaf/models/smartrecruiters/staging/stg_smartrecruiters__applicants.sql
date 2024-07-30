select
    * except (
        application_field_school_shared_with_miami,
        application_field_school_shared_with_new_jersey,
        screening_question_answer_miami_grad_gpa,
        screening_question_answer_miami_out_of_state_teaching_certification_details,
        screening_question_answer_miami_teacher_certification_question,
        screening_question_answer_miami_undergrad_gpa,
        screening_question_answer_new_jersey_grad_gpa,
        screening_question_answer_new_jersey_out_of_state_teacher_certification_details,
        screening_question_answer_new_jersey_teacher_certification_question,
        screening_question_answer_new_jersey_undergrad_gpa,
        screening_question_answer_new_jersey_miami_affiliated_orgs,
        screening_question_answer_new_jersey_miami_other_orgs,
        screening_question_answer_new_jersey_miami_current_or_former_kipp_employee,
        screening_question_answer_new_jersey_miami_expected_salary,
        screening_question_answer_national_race,
        screening_question_answer_national_gender,
        screening_question_answer_national_are_you_alumnus,
        screening_question_answer_national_in_which_regions_alumnus,
        screening_question_answer_new_jersey_out_of_state_sped_credits,
        -- trunk-ignore(sqlfluff/LT05)
        screening_question_answer_new_jersey_miami_current_or_former_kipp_nj_miami_employee
    ),

    screening_question_answer_national_are_you_alumnus as kf_are_you_alumnus,
    screening_question_answer_national_gender as kf_gender,
    screening_question_answer_national_in_which_regions_alumnus
    as kf_in_which_regions_alumnus,
    screening_question_answer_national_race as kf_race,
    screening_question_answer_new_jersey_miami_affiliated_orgs as taf_affiliated_orgs,
    screening_question_answer_new_jersey_miami_current_or_former_kipp_employee
    as taf_current_or_former_kipp_employee,
    screening_question_answer_new_jersey_miami_current_or_former_kipp_nj_miami_employee
    as taf_current_or_former_kipp_nj_miami_employee,
    screening_question_answer_new_jersey_miami_expected_salary as taf_expected_salary,
    screening_question_answer_new_jersey_miami_other_orgs as taf_other_orgs,
    screening_question_answer_new_jersey_out_of_state_sped_credits
    as nj_out_of_state_sped_credits,

    concat(candidate_last_name, ', ', candidate_first_name) as candidate_last_first,

    coalesce(
        application_field_school_shared_with_new_jersey,
        application_field_school_shared_with_miami
    ) as school_shared_with,
    coalesce(
        screening_question_answer_new_jersey_undergrad_gpa,
        screening_question_answer_miami_undergrad_gpa
    ) as undergrad_gpa,
    coalesce(
        screening_question_answer_new_jersey_grad_gpa,
        screening_question_answer_miami_grad_gpa
    ) as grad_gpa,
    coalesce(
        screening_question_answer_new_jersey_teacher_certification_question,
        screening_question_answer_miami_teacher_certification_question
    ) as certification_in_state,
    coalesce(
        screening_question_answer_new_jersey_out_of_state_teacher_certification_details,
        screening_question_answer_miami_out_of_state_teaching_certification_details
    ) as certification_out_of_state,
from {{ source("smartrecruiters", "src_smartrecruiters__applicants") }}
