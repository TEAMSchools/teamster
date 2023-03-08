{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="reenrollmentsdcid",
        transform_cols=[
            {
                "name": "reenrollmentsdcid",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "lep_tf", "transformation": "extract", "type": "int_value"},
            {"name": "pid_504_tf", "transformation": "extract", "type": "int_value"},
            {
                "name": "cumulativedaysabsent",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "cumulativedayspresent",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "cumulativestateabs",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "daysopen", "transformation": "extract", "type": "int_value"},
            {"name": "deviceowner", "transformation": "extract", "type": "int_value"},
            {"name": "devicetype", "transformation": "extract", "type": "int_value"},
            {
                "name": "homelessprimarynighttimeres",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "internetconnectivity",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "remotedaysabsent",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "remotedayspresent",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "learningenvironment",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "retained_tf", "transformation": "extract", "type": "int_value"},
            {
                "name": "languageacquisition",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "lep_completion_date_refused",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sid_excludeenrollment",
                "transformation": "extract",
                "type": "int_value",
            },
        ],
    )
}}
