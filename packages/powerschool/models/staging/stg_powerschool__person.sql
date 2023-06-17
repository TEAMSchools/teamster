{{
    teamster_utils.transform_cols_base_model(
        transform_cols=[
            {"name": "dcid", "extract": "int_value"},
            {"name": "id", "extract": "int_value"},
            {"name": "prefixcodesetid", "extract": "int_value"},
            {"name": "suffixcodesetid", "extract": "int_value"},
            {"name": "gendercodesetid", "extract": "int_value"},
            {"name": "statecontactnumber", "extract": "int_value"},
            {"name": "isactive", "extract": "int_value"},
            {"name": "excludefromstatereporting", "extract": "int_value"},
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
        unique_key="dcid",
        transform_cols=[
            {"name": "dcid", "extract": "int_value"},
            {"name": "id", "extract": "int_value"},
            {"name": "prefixcodesetid", "extract": "int_value"},
            {"name": "suffixcodesetid", "extract": "int_value"},
            {"name": "gendercodesetid", "extract": "int_value"},
            {"name": "statecontactnumber", "extract": "int_value"},
            {"name": "isactive", "extract": "int_value"},
            {"name": "excludefromstatereporting", "extract": "int_value"},
        ],
        except_cols=[
            "_dagster_partition_fiscal_year",
            "_dagster_partition_date",
            "_dagster_partition_hour",
            "_dagster_partition_minute",
        ],
    )
}} #}

