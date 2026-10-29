{{
    dbt_utils.deduplicate(
        relation=source(
            "google_sheets", "src_google_sheets__assessments__academic_goals"
        ),
        partition_by=(
            "Academic_Year, School_ID, Grade_Level, "
            "State_Assessment_Code, Illuminate_Subject_Area"
        ),
        order_by=(
            "School_Goal desc, Grade_Goal desc, Region_Goal desc, "
            "Organization_Goal desc, Grade_Band_Goal desc, "
            "Assessment_Band_Goal desc, Region_Grade_Goal desc"
        ),
    )
}}
