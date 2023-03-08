{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="teachercategoryid",
        transform_cols=[
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
            {"name": "usersdcid", "transformation": "extract", "type": "int_value"},
            {
                "name": "isinfinalgrades",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "isactive", "transformation": "extract", "type": "int_value"},
            {
                "name": "isusermodifiable",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "teachermodified",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "displayposition",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "defaultscoreentrypoints",
                "transformation": "extract",
                "type": "bytes_decimal_value",
            },
            {
                "name": "defaultextracreditpoints",
                "transformation": "extract",
                "type": "bytes_decimal_value",
            },
            {
                "name": "defaultweight",
                "transformation": "extract",
                "type": "bytes_decimal_value",
            },
            {
                "name": "defaulttotalvalue",
                "transformation": "extract",
                "type": "bytes_decimal_value",
            },
            {
                "name": "isdefaultpublishscores",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "defaultdaysbeforedue",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "whomodifiedid",
                "transformation": "extract",
                "type": "int_value",
            },
        ],
    )
}}
