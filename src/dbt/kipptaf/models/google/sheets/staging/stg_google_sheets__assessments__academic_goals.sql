{{
    dbt_utils.deduplicate(
        relation=source(
            "google_sheets", "src_google_sheets__assessments__academic_goals"
        ),
        partition_by=(
            "Academic_Year, School_ID, Grade_Level, "
            "State_Assessment_Code, Illuminate_Subject_Area"
        ),
        order_by="School_Goal desc",
    )
}}
