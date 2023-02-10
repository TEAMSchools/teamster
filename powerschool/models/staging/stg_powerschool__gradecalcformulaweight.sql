{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="gradecalcformulaweightid",
        transform_cols=[
            {"name": "gradecalcformulaweightid", "type": "int_value"},
            {"name": "gradecalculationtypeid", "type": "int_value"},
            {"name": "teachercategoryid", "type": "int_value"},
            {"name": "districtteachercategoryid", "type": "int_value"},
            {"name": "assignmentid", "type": "int_value"},
            {"name": "weight", "type": "bytes_decimal_value"},
        ],
    )
}}
