{{
    teamster_utils.generate_staging_model(
        unique_key="usersdcid.int_value",
        transform_cols=[
            {"name": "usersdcid", "extract": "int_value"},
            {"name": "smart_salary", "extract": "int_value"},
            {"name": "smart_yearsinlea", "extract": "int_value"},
            {"name": "smart_yearsinnj", "extract": "int_value"},
            {"name": "smart_yearsofexp", "extract": "int_value"},
            {"name": "excl_frm_smart_stf_submissn", "extract": "int_value"},
            {"name": "smart_stafcompenanualsup", "extract": "int_value"},
            {"name": "smart_stafcompnsatnbassal", "extract": "int_value"},
        ],
        except_cols=[
            "_dagster_partition_fiscal_year",
            "_dagster_partition_date",
            "_dagster_partition_hour",
            "_dagster_partition_minute",
        ],
    )
}}

select *
from staging
