{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="dcid",
        transform_cols=[
            {"name": "dcid", "transformation": "extract", "type": "int_value"},
            {
                "name": "homeschoolid",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "photo", "transformation": "extract", "type": "int_value"},
            {"name": "numlogins", "transformation": "extract", "type": "int_value"},
            {
                "name": "allowloginstart",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "allowloginend",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "psaccess", "transformation": "extract", "type": "int_value"},
            {"name": "groupvalue", "transformation": "extract", "type": "int_value"},
            {"name": "lunch_id", "transformation": "extract", "type": "double_value"},
            {
                "name": "supportcontact",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "wm_tier", "transformation": "extract", "type": "int_value"},
            {
                "name": "wm_createtime",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "wm_exclude", "transformation": "extract", "type": "int_value"},
            {
                "name": "adminldapenabled",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "teacherldapenabled",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "maximum_load",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "gradebooktype",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "fedethnicity",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "fedracedecline",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "ptaccess", "transformation": "extract", "type": "int_value"},
            {
                "name": "whomodifiedid",
                "transformation": "extract",
                "type": "int_value",
            },
        ],
    )
}}
