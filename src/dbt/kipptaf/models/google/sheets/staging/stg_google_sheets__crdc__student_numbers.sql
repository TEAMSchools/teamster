-- the sheet is hand-kept and repeats rows; a repeat fans out the CRDC roster
{{
    dbt_utils.deduplicate(
        relation=source("google_sheets", "src_google_sheets__crdc__student_numbers"),
        partition_by="student_number, crdc_question_section",
        order_by="student_number",
    )
}}
