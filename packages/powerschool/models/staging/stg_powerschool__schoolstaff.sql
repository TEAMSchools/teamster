{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="dcid",
        transform_cols=[
            {"name": "dcid", "transformation": "extract", "type": "int_value"},
            {"name": "id", "transformation": "extract", "type": "int_value"},
            {"name": "schoolid", "transformation": "extract", "type": "int_value"},
            {"name": "users_dcid", "transformation": "extract", "type": "int_value"},
            {"name": "balance1", "transformation": "extract", "type": "double_value"},
            {"name": "balance2", "transformation": "extract", "type": "double_value"},
            {"name": "balance3", "transformation": "extract", "type": "double_value"},
            {"name": "balance4", "transformation": "extract", "type": "double_value"},
            {
                "name": "noofcurclasses",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "staffstatus", "transformation": "extract", "type": "int_value"},
            {"name": "status", "transformation": "extract", "type": "int_value"},
            {
                "name": "sched_maximumcourses",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_maximumduty",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_maximumfree",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_totalcourses",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_maximumconsecutive",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_isteacherfree",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_teachermoreoneschool",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_substitute",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_scheduled",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_usebuilding",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_usehouse",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "sched_lunch", "transformation": "extract", "type": "int_value"},
            {
                "name": "sched_maxpers",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_maxpreps",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "whomodifiedid",
                "transformation": "extract",
                "type": "int_value",
            },
        ],
    )
}}
