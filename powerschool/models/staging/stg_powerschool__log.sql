{{
    teamster_utils.generate_staging_model(
        unique_key="dcid.int_value",
        transform_cols=[
            {"name": "dcid", "extract": "int_value"},
            {"name": "id", "extract": "int_value"},
            {"name": "studentid", "extract": "int_value"},
            {"name": "teacherid", "extract": "int_value"},
            {"name": "entry_time", "extract": "int_value"},
            {"name": "category", "extract": "int_value"},
            {"name": "schoolid", "extract": "int_value"},
            {"name": "logtypeid", "extract": "int_value"},
            {"name": "student_number", "extract": "double_value"},
            {"name": "discipline_felonyflag", "extract": "int_value"},
            {"name": "discipline_likelyinjuryflag", "extract": "int_value"},
            {"name": "discipline_schoolrulesvioflag", "extract": "int_value"},
            {"name": "discipline_policeinvolvedflag", "extract": "int_value"},
            {"name": "discipline_hearingofficerflag", "extract": "int_value"},
            {"name": "discipline_gangrelatedflag", "extract": "int_value"},
            {"name": "discipline_hatecrimeflag", "extract": "int_value"},
            {"name": "discipline_alcoholrelatedflag", "extract": "int_value"},
            {"name": "discipline_drugrelatedflag", "extract": "int_value"},
            {"name": "discipline_weaponrelatedflag", "extract": "int_value"},
            {"name": "discipline_moneylossvalue", "extract": "double_value"},
            {"name": "discipline_durationassigned", "extract": "double_value"},
            {"name": "discipline_durationactual", "extract": "double_value"},
            {"name": "discipline_sequence", "extract": "int_value"},
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
