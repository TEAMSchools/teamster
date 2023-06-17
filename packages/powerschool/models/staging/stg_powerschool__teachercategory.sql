{{
    teamster_utils.transform_cols_base_model(
        transform_cols=[
            {"name": "teachercategoryid", "extract": "int_value"},
            {"name": "districtteachercategoryid", "extract": "int_value"},
            {"name": "usersdcid", "extract": "int_value"},
            {"name": "isinfinalgrades", "extract": "int_value"},
            {"name": "isactive", "extract": "int_value"},
            {"name": "isusermodifiable", "extract": "int_value"},
            {"name": "teachermodified", "extract": "int_value"},
            {"name": "displayposition", "extract": "int_value"},
            {"name": "defaultscoreentrypoints", "extract": "bytes_decimal_value"},
            {"name": "defaultextracreditpoints", "extract": "bytes_decimal_value"},
            {"name": "defaultweight", "extract": "bytes_decimal_value"},
            {"name": "defaulttotalvalue", "extract": "bytes_decimal_value"},
            {"name": "isdefaultpublishscores", "extract": "int_value"},
            {"name": "defaultdaysbeforedue", "extract": "int_value"},
            {"name": "whomodifiedid", "extract": "int_value"},
        ],
        except_cols=[
            "_dagster_partition_fiscal_year",
            "_dagster_partition_date",
            "_dagster_partition_hour",
            "_dagster_partition_minute",
        ],
    )
}}

{# {{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="teachercategoryid",
        transform_cols=[
            {"name": "teachercategoryid", "extract": "int_value"},
            {"name": "districtteachercategoryid", "extract": "int_value"},
            {"name": "usersdcid", "extract": "int_value"},
            {"name": "isinfinalgrades", "extract": "int_value"},
            {"name": "isactive", "extract": "int_value"},
            {"name": "isusermodifiable", "extract": "int_value"},
            {"name": "teachermodified", "extract": "int_value"},
            {"name": "displayposition", "extract": "int_value"},
            {"name": "defaultscoreentrypoints", "extract": "bytes_decimal_value"},
            {"name": "defaultextracreditpoints", "extract": "bytes_decimal_value"},
            {"name": "defaultweight", "extract": "bytes_decimal_value"},
            {"name": "defaulttotalvalue", "extract": "bytes_decimal_value"},
            {"name": "isdefaultpublishscores", "extract": "int_value"},
            {"name": "defaultdaysbeforedue", "extract": "int_value"},
            {"name": "whomodifiedid", "extract": "int_value"},
        ],
        except_cols=[
            "_dagster_partition_fiscal_year",
            "_dagster_partition_date",
            "_dagster_partition_hour",
            "_dagster_partition_minute",
        ],
    )
}} #}

