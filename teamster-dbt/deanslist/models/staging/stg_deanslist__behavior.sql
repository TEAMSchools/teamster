{{
    teamster_utils.generate_staging_model(
        unique_key="dlsaid",
        transform_cols=[
            {"name": "DLOrganizationID", "cast": "int"},
            {"name": "DLSchoolID", "cast": "int"},
            {"name": "DLStudentID", "cast": "int"},
            {"name": "StudentSchoolID", "cast": "int"},
            {"name": "SecondaryStudentID", "cast": "int"},
            {"name": "StudentMiddleName", "nullif": "''"},
            {"name": "DLSAID", "cast": "int"},
            {"name": "BehaviorDate", "cast": "date"},
            {"name": "PointValue", "cast": "int"},
            {"name": "DLUserID", "cast": "int"},
            {"name": "StaffTitle", "nullif": "''"},
            {"name": "StaffMiddleName", "nullif": "''"},
            {"name": "RosterID", "cast": "int"},
            {"name": "Notes", "nullif": "''"},
            {"name": "DL_LASTUPDATE", "cast": "datetime"},
        ],
        except_cols=[
            "_dagster_partition_fiscal_year",
            "_dagster_partition_date",
            "_dagster_partition_hour",
            "_dagster_partition_minute",
            "_dagster_partition_school",
        ],
    )
}}

select *
from staging
