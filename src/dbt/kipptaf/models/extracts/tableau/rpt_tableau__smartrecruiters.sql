with
    applications_unpivot as (
        select
            application_id,
            candidate_id,
            job_city,
            recruiters,
            department_internal,
            job_title,
            application_status,
            reason_for_rejection,
            phone_interview_score,
            status_type,
            date_val,
            coalesce(resume_score, star_score) as resume_score,
            if(
                subject_preference is null, 'No Preference', subject_preference
            ) as subject_preference,
        from
            {{ ref("stg_smartrecruiters__applications") }} unpivot (
                date_val for status_type in (
                    demo_date,
                    hired_date,
                    new_date,
                    offer_date,
                    phone_screen_complete_date,
                    phone_screen_requested_date
                )
            )
    ),

    applications_unnested as (
        select
            au.application_id,
            au.candidate_id,
            au.job_city,
            au.recruiters,
            au.department_internal,
            au.job_title,
            au.application_status,
            au.reason_for_rejection,
            au.phone_interview_score,
            au.status_type,
            au.date_val,
            au.resume_score,
            trim(au.subject_preference) as subject_preference,
        from applications_unpivot as au
        cross join unnest(split(au.subject_preference, ',')) as subject_preference
    )

select
    a.application_id,
    a.job_city,
    a.recruiters,
    a.department_internal,
    a.job_title,
    a.application_status,
    a.reason_for_rejection,
    a.phone_interview_score,
    a.resume_score,
    a.subject_preference,
    a.status_type,
    a.date_val,

    s.candidate_email,
    s.candidate_first_and_last_name,
    s.candidate_first_name,
    s.candidate_id,
    s.candidate_last_name,
    s.candidate_source_subtype,
    s.candidate_source_type,
    s.candidate_source,
    s.candidate_tags_values,
    s.current_employer,
    s.teacher_certification_endorsement_question,
    s.city_of_interest,
    s.how_did_you_hear_about_kipp_nj_miami,
    s.out_of_state_teacher_certification_sped_credits,
    s.kf_are_you_alumnus,
    s.kf_gender,
    s.kf_in_which_regions_alumnus,
    s.kf_race,
    s.taf_affiliated_orgs,
    s.taf_current_or_former_kipp_employee,
    s.taf_current_or_former_kipp_nj_miami_employee,
    s.taf_expected_salary,
    s.taf_other_orgs,
    s.nj_out_of_state_sped_credits,
    s.candidate_last_first,
    s.school_shared_with,
    s.undergrad_gpa,
    s.grad_gpa,
    s.certification_in_state,
    s.certification_out_of_state,
from applications_unnested as a
left join
    {{ ref("stg_smartrecruiters__applicants") }} as s on a.candidate_id = s.candidate_id
