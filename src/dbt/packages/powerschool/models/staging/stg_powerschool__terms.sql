{{
    teamster_utils.generate_staging_model(
        unique_key="id.int_value, schoolid.int_value",
        transform_cols=[
            {"name": "dcid", "extract": "int_value"},
            {"name": "id", "extract": "int_value"},
            {"name": "yearid", "extract": "int_value"},
            {"name": "noofdays", "extract": "int_value"},
            {"name": "schoolid", "extract": "int_value"},
            {"name": "yearlycredithrs", "extract": "double_value"},
            {"name": "termsinyear", "extract": "int_value"},
            {"name": "portion", "extract": "int_value"},
            {"name": "autobuildbin", "extract": "int_value"},
            {"name": "isyearrec", "extract": "int_value"},
            {"name": "periods_per_day", "extract": "int_value"},
            {"name": "days_per_cycle", "extract": "int_value"},
            {"name": "attendance_calculation_code", "extract": "int_value"},
            {"name": "sterms", "extract": "int_value"},
            {"name": "suppresspublicview", "extract": "int_value"},
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

select *
from staging
