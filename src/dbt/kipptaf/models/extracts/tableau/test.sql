{% set dims = [
    "academic_year",
    "district_state",
    "region",
    "assessment_name",
    "test_code",
    "gender",
    "race_ethnicity",
    "lunch_status",
    "lep_status",
    "iep_status",
] %}

{% set aggs = [
    "ROUND(AVG(is_proficient_int) * COUNT(student_number), 0) AS total_proficient_students",
    "COUNT(student_number) AS total_students",
    "AVG(is_proficient_int) AS percent_proficient",
] %}

{{
    generate_cube_query(
        dims,
        aggs,
        ref("rpt_tableau__state_assessments_dashboard_cmo_comps"),
        where_clause="test_code IS NOT NULL AND assessment_name IS NOT NULL and academic_year IS NOT NULL",
        focus_group=True,
        focus_dims=[
            "gender",
            "race_ethnicity",
            "lunch_status",
            "lep_status",
            "iep_status",
        ],
    )
}}
