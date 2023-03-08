{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="gradecalcformulaweightid",
        transform_cols=[
            {
                "name": "gradecalcformulaweightid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "gradecalculationtypeid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "teachercategoryid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "districtteachercategoryid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "assignmentid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "weight",
                "transformation": "extract",
                "type": "bytes_decimal_value",
            },
        ],
    )
}}
