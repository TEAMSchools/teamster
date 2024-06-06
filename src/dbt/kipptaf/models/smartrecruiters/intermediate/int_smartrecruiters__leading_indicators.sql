with
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
            reason_for_rejection,

            status_type,
            date_val,
        from
            {{ ref("stg_smartrecruiters__applications") }} unpivot (
                date_val for status_type in (
                    demo_date,
                    hired_date,
                    in_review_date,
                    interview_date,
                    new_date,
                    offer_date,
                    performance_task_date,
                    phone_screen_complete_date,
                    phone_screen_requested_date
                )
            )
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
    a.reason_for_rejection as rejection_reason,
    a.status_type,
    a.date_val,

    b.candidate_id,
    b.candidate_last_name,
    b.candidate_first_name,
    b.candidate_last_first,
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
    b.nj_out_of_state_sped_credits as nj_sped_credits,
    b.taf_current_or_former_kipp_nj_miami_employee as former_kippnjmia,
    b.school_shared_with,
    b.undergrad_gpa,
    b.grad_gpa,
    b.certification_in_state as certification_instate,
    b.certification_out_of_state as certification_outstate,
from applications_unpivot as a
left join
    {{ ref("stg_smartrecruiters__applicants") }} as b
    on a.application_id = b.application_id
