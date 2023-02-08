{%- set code_location = "kippcamden" -%}

{%- set source_name = model.fqn[1] -%}
{%- set model_name = this.identifier -%}

{{
    incremental_merge_source_file(
        source_name=source_name,
        model_name=model_name,
        file_uri=get_gcs_uri(
            code_location, source_name, model_name, var("partition_path")
        ),
        unique_key="dcid",
        transform_cols=[
            {"name": "dcid", "type": "int_value"},
            {"name": "studentid", "type": "int_value"},
            {"name": "sectionid", "type": "int_value"},
            {"name": "termid", "type": "int_value"},
            {"name": "percent", "type": "double_value"},
            {"name": "absences", "type": "double_value"},
            {"name": "tardies", "type": "double_value"},
            {"name": "potentialcrhrs", "type": "double_value"},
            {"name": "earnedcrhrs", "type": "double_value"},
            {"name": "grade_level", "type": "int_value"},
            {"name": "schoolid", "type": "int_value"},
            {"name": "excludefromgpa", "type": "int_value"},
            {"name": "gpa_points", "type": "double_value"},
            {"name": "gpa_addedvalue", "type": "double_value"},
            {"name": "gpa_custom2", "type": "double_value"},
            {"name": "excludefromclassrank", "type": "int_value"},
            {"name": "excludefromhonorroll", "type": "int_value"},
            {"name": "isearnedcrhrsfromgb", "type": "int_value"},
            {"name": "ispotentialcrhrsfromgb", "type": "int_value"},
            {"name": "excludefromtranscripts", "type": "int_value"},
            {"name": "replaced_dcid", "type": "int_value"},
            {"name": "excludefromgraduation", "type": "int_value"},
            {"name": "excludefromgradesuppression", "type": "int_value"},
            {"name": "gradereplacementpolicy_id", "type": "int_value"},
            {"name": "whomodifiedid", "type": "int_value"},
        ],
    )
}}
