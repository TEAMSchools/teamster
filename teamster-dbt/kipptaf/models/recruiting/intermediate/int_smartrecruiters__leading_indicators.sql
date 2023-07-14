with
    applications as (
        select
            application_id,
            job_city,
            recruiters,
            department_internal,
            job_title,
            application_state,
            source,
            source_type,
            source_subtype,
            application_state_new_date as application_date,
            application_state_in_review_date as review_date,
            application_state_interview_date as interview_date,
            application_status_interview_phone_screen_requested_date
            as phone_screen_requested,
            application_status_interview_phone_screen_complete_date
            as phone_screen_complete,
            application_status_interview_demo_date as final_interview_demo,
            application_state_offer_date as offer_date,
            application_state_hired_date as hired_date
        from {{ source("smartrecruiters", "src_smartrecruiters__applications") }}
    ),

    applications_unpivot as (
        select
            application_id,
            job_city,
            recruiters,
            department_internal,
            job_title,
            application_state,
            source,
            source_type,
            source_subtype,
            name_column,
            values_column,
        from
            applications unpivot (
                values_column for name_column in (
                    application_date,
                    review_date,
                    interview_date,
                    phone_screen_requested,
                    phone_screen_complete,
                    final_interview_demo,
                    offer_date,
                    hired_date
                )
            ) as u
    )

select
    a.application_id,
    a.job_city,
    a.recruiters,
    a.job_title,
    a.application_state,
    a.source,
    a.source_type,
    a.source_subtype,
    a.department_internal,
    a.name_column as status_type,
    a.values_column as date_val,

    b.candidate_id,
    b.candidate_last_name,
    b.candidate_first_name,
    b.candidate_email,
    b.current_employer,
    b.candidate_tags_values,
    b.taf_affiliated_orgs,
    b.taf_other_orgs,
    b.taf_current_or_former_kipp_employee,
    b.taf_expected_salary,
    b.kf_race,
    b.kf_gender,
    b.kf_are_you_alumnus,
    b.kf_in_which_regions_alumnus,
    b.nj_out_of_state_teacher_certification_sped_credits as nj_sped_credits,
    b.taf_current_or_former_kipp_nj_mia_employee as former_kippnjmia,
    concat(b.candidate_last_name, ', ', b.candidate_first_name) as candidate_last_first,
    coalesce(b.nj_undergrad_gpa, b.mia_undergrad_gpa) as undergrad_gpa,
    coalesce(b.nj_grad_gpa, b.mia_grad_gpa) as grad_gpa,
    coalesce(
        b.nj_teacher_certification_question, b.mia_teacher_certification_question
    ) as certification_instate,
    coalesce(
        b.nj_out_of_state_teacher_certification_details,
        b.mia_out_of_state_teaching_certification_details
    ) as certification_outstate,
from applications_unpivot as a
left join
    {{ source("smartrecruiters", "src_smartrecruiters__applicants") }} as b
    on a.application_id = b.application_id
