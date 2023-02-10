{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="coursesdcid",
        transform_cols=[
            {"name": "coursesdcid", "type": "int_value"},
            {"name": "exclude_course_submission_tf", "type": "int_value"},
            {"name": "sla_include_tf", "type": "int_value"},
        ],
    )
}}
