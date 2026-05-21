select
    contact_id,
    notes,
    resume_score as is_resume_score,
    linkedin as is_linkedin,
    mock_interview_or_prep as is_mock_interview_or_prep,
    professional_references_list as is_professional_references_list,
    job_search_template as is_job_search_template,
    cover_letter_template as is_cover_letter_template,
    work_samples as is_work_samples,
from
    {{
        source(
            "google_appsheet",
            "src_google_appsheet__kfwd_career_conversations__output",
        )
    }}
