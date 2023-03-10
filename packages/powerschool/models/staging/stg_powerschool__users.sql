{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="dcid",
        transform_cols=[
            {"name": "dcid", "extract": "int_value"},
            {
                "name": "homeschoolid",
                "extract": "int_value",
            },
            {"name": "photo", "extract": "int_value"},
            {"name": "numlogins", "extract": "int_value"},
            {
                "name": "allowloginstart",
                "extract": "int_value",
            },
            {
                "name": "allowloginend",
                "extract": "int_value",
            },
            {"name": "psaccess", "extract": "int_value"},
            {"name": "groupvalue", "extract": "int_value"},
            {"name": "lunch_id", "extract": "double_value"},
            {
                "name": "supportcontact",
                "extract": "int_value",
            },
            {"name": "wm_tier", "extract": "int_value"},
            {
                "name": "wm_createtime",
                "extract": "int_value",
            },
            {"name": "wm_exclude", "extract": "int_value"},
            {
                "name": "adminldapenabled",
                "extract": "int_value",
            },
            {
                "name": "teacherldapenabled",
                "extract": "int_value",
            },
            {
                "name": "maximum_load",
                "extract": "int_value",
            },
            {
                "name": "gradebooktype",
                "extract": "int_value",
            },
            {
                "name": "fedethnicity",
                "extract": "int_value",
            },
            {
                "name": "fedracedecline",
                "extract": "int_value",
            },
            {"name": "ptaccess", "extract": "int_value"},
            {
                "name": "whomodifiedid",
                "extract": "int_value",
            },
        ],
    )
}}
