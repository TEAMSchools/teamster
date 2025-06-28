{{ config(materialized="table") }}

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
        ref("int_tableau__state_assessments_demographic_comps"),
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
