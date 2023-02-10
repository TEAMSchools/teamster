{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="gradecalcschoolassocid",
        transform_cols=[
            {"name": "gradecalcschoolassocid", "type": "int_value"},
            {"name": "gradecalculationtypeid", "type": "int_value"},
            {"name": "schoolsdcid", "type": "int_value"},
        ],
    )
}}
