{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="dlsaid",
        transform_cols=[
            {"name": "DLOrganizationID", "cast": "INT64"},
            {"name": "DLSchoolID", "cast": "INT64"},
            {"name": "DLStudentID", "cast": "INT64"},
            {"name": "StudentSchoolID", "cast": "INT64"},
            {"name": "SecondaryStudentID", "cast": "INT64", "nullif": "''"},
            {"name": "StudentMiddleName", "nullif": "''"},
            {"name": "DLSAID", "cast": "INT64"},
            {"name": "BehaviorDate", "cast": "DATE"},
            {"name": "PointValue", "cast": "INT64"},
            {"name": "DLUserID", "cast": "INT64"},
            {"name": "StaffTitle", "nullif": "''"},
            {"name": "StaffMiddleName", "nullif": "''"},
            {"name": "RosterID", "cast": "INT64"},
            {"name": "Notes", "nullif": "''"},
            {"name": "DL_LASTUPDATE", "cast": "DATETIME"},
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
