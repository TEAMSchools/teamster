{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="reenrollmentsdcid",
        transform_cols=[
            {"name": "reenrollmentsdcid", "extract": "int_value"},
            {"name": "lep_tf", "extract": "int_value"},
            {"name": "pid_504_tf", "extract": "int_value"},
            {"name": "cumulativedaysabsent", "extract": "int_value"},
            {"name": "cumulativedayspresent", "extract": "int_value"},
            {"name": "cumulativestateabs", "extract": "int_value"},
            {"name": "daysopen", "extract": "int_value"},
            {"name": "deviceowner", "extract": "int_value"},
            {"name": "devicetype", "extract": "int_value"},
            {"name": "homelessprimarynighttimeres", "extract": "int_value"},
            {"name": "internetconnectivity", "extract": "int_value"},
            {"name": "remotedaysabsent", "extract": "int_value"},
            {"name": "remotedayspresent", "extract": "int_value"},
            {"name": "learningenvironment", "extract": "int_value"},
            {"name": "retained_tf", "extract": "int_value"},
            {"name": "languageacquisition", "extract": "int_value"},
            {"name": "lep_completion_date_refused", "extract": "int_value"},
            {"name": "sid_excludeenrollment", "extract": "int_value"},
        ],
        except_cols=[
            "_dagster_partition_fiscal_year",
            "_dagster_partition_date",
            "_dagster_partition_hour",
            "_dagster_partition_minute",
        ],
    )
}}
