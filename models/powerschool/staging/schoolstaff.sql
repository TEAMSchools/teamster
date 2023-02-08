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
            {"name": "id", "type": "int_value"},
            {"name": "schoolid", "type": "int_value"},
            {"name": "users_dcid", "type": "int_value"},
            {"name": "balance1", "type": "double_value"},
            {"name": "balance2", "type": "double_value"},
            {"name": "balance3", "type": "double_value"},
            {"name": "balance4", "type": "double_value"},
            {"name": "noofcurclasses", "type": "int_value"},
            {"name": "staffstatus", "type": "int_value"},
            {"name": "status", "type": "int_value"},
            {"name": "sched_maximumcourses", "type": "int_value"},
            {"name": "sched_maximumduty", "type": "int_value"},
            {"name": "sched_maximumfree", "type": "int_value"},
            {"name": "sched_totalcourses", "type": "int_value"},
            {"name": "sched_maximumconsecutive", "type": "int_value"},
            {"name": "sched_isteacherfree", "type": "int_value"},
            {"name": "sched_teachermoreoneschool", "type": "int_value"},
            {"name": "sched_substitute", "type": "int_value"},
            {"name": "sched_scheduled", "type": "int_value"},
            {"name": "sched_usebuilding", "type": "int_value"},
            {"name": "sched_usehouse", "type": "int_value"},
            {"name": "sched_lunch", "type": "int_value"},
            {"name": "sched_maxpers", "type": "int_value"},
            {"name": "sched_maxpreps", "type": "int_value"},
            {"name": "whomodifiedid", "type": "int_value"},
        ],
    )
}}
