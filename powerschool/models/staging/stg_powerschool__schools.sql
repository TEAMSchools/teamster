{{
    teamster_utils.generate_staging_model(
        unique_key="dcid.int_value",
        transform_cols=[
            {"name": "dcid", "extract": "int_value"},
            {"name": "id", "extract": "int_value"},
            {"name": "district_number", "extract": "int_value"},
            {"name": "school_number", "extract": "int_value"},
            {"name": "low_grade", "extract": "int_value"},
            {"name": "high_grade", "extract": "int_value"},
            {"name": "sortorder", "extract": "int_value"},
            {"name": "schoolgroup", "extract": "int_value"},
            {"name": "hist_low_grade", "extract": "int_value"},
            {"name": "hist_high_grade", "extract": "int_value"},
            {"name": "dfltnextschool", "extract": "int_value"},
            {"name": "view_in_portal", "extract": "int_value"},
            {"name": "state_excludefromreporting", "extract": "int_value"},
            {"name": "alternate_school_number", "extract": "int_value"},
            {"name": "fee_exemption_status", "extract": "int_value"},
            {"name": "issummerschool", "extract": "int_value"},
            {"name": "schoolcategorycodesetid", "extract": "int_value"},
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
