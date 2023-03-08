{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="dcid",
        transform_cols=[
            {"name": "dcid", "transformation": "extract", "type": "int_value"},
            {"name": "id", "transformation": "extract", "type": "int_value"},
            {
                "name": "district_number",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "school_number",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "low_grade", "transformation": "extract", "type": "int_value"},
            {"name": "high_grade", "transformation": "extract", "type": "int_value"},
            {"name": "sortorder", "transformation": "extract", "type": "int_value"},
            {"name": "schoolgroup", "transformation": "extract", "type": "int_value"},
            {
                "name": "hist_low_grade",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "hist_high_grade",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "dfltnextschool",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "view_in_portal",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "state_excludefromreporting",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "alternate_school_number",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "fee_exemption_status",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "issummerschool",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "schoolcategorycodesetid",
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
