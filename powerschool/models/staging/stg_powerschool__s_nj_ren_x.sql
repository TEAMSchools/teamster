{{
    teamster_utils.incremental_merge_source_file(
        from_source=source("powerschool", this.identifier | replace("stg", "src")),
        file_uri=teamster_utils.get_gcs_uri(
            code_location=var("code_location"),
            system_name="powerschool",
            model_name=this.identifier | replace("stg_powerschool__", ""),
            partition_path=var("partition_path"),
        ),
        unique_key="reenrollmentsdcid",
        transform_cols=[
            {"name": "reenrollmentsdcid", "type": "int_value"},
            {"name": "lep_tf", "type": "int_value"},
            {"name": "pid_504_tf", "type": "int_value"},
            {"name": "cumulativedaysabsent", "type": "int_value"},
            {"name": "cumulativedayspresent", "type": "int_value"},
            {"name": "cumulativestateabs", "type": "int_value"},
            {"name": "daysopen", "type": "int_value"},
            {"name": "deviceowner", "type": "int_value"},
            {"name": "devicetype", "type": "int_value"},
            {"name": "homelessprimarynighttimeres", "type": "int_value"},
            {"name": "internetconnectivity", "type": "int_value"},
            {"name": "remotedaysabsent", "type": "int_value"},
            {"name": "remotedayspresent", "type": "int_value"},
            {"name": "learningenvironment", "type": "int_value"},
            {"name": "retained_tf", "type": "int_value"},
            {"name": "languageacquisition", "type": "int_value"},
            {"name": "lep_completion_date_refused", "type": "int_value"},
            {"name": "sid_excludeenrollment", "type": "int_value"},
        ],
    )
}}
