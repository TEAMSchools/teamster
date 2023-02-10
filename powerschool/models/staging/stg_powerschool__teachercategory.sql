{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="teachercategoryid",
        transform_cols=[
            {"name": "teachercategoryid", "type": "int_value"},
            {"name": "districtteachercategoryid", "type": "int_value"},
            {"name": "usersdcid", "type": "int_value"},
            {"name": "isinfinalgrades", "type": "int_value"},
            {"name": "isactive", "type": "int_value"},
            {"name": "isusermodifiable", "type": "int_value"},
            {"name": "teachermodified", "type": "int_value"},
            {"name": "displayposition", "type": "int_value"},
            {"name": "defaultscoreentrypoints", "type": "bytes_decimal_value"},
            {"name": "defaultextracreditpoints", "type": "bytes_decimal_value"},
            {"name": "defaultweight", "type": "bytes_decimal_value"},
            {"name": "defaulttotalvalue", "type": "bytes_decimal_value"},
            {"name": "isdefaultpublishscores", "type": "int_value"},
            {"name": "defaultdaysbeforedue", "type": "int_value"},
            {"name": "whomodifiedid", "type": "int_value"},
        ],
    )
}}
