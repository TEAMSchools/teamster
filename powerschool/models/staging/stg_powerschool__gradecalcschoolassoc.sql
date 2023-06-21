{{
    teamster_utils.transform_cols_base_model(
        transform_cols=[
            {"name": "gradecalcschoolassocid", "extract": "int_value"},
            {"name": "gradecalculationtypeid", "extract": "int_value"},
            {"name": "schoolsdcid", "extract": "int_value"},
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
        unique_key="gradecalcschoolassocid",
        transform_cols=[
            {"name": "gradecalcschoolassocid", "extract": "int_value"},
            {"name": "gradecalculationtypeid", "extract": "int_value"},
            {"name": "schoolsdcid", "extract": "int_value"},
        ],
        except_cols=[
            "_dagster_partition_fiscal_year",
            "_dagster_partition_date",
            "_dagster_partition_hour",
            "_dagster_partition_minute",
        ],
    )
}} #}

