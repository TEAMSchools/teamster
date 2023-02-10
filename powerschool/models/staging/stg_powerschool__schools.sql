{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="dcid",
        transform_cols=[
            {"name": "dcid", "type": "int_value"},
            {"name": "id", "type": "int_value"},
            {"name": "district_number", "type": "int_value"},
            {"name": "school_number", "type": "int_value"},
            {"name": "low_grade", "type": "int_value"},
            {"name": "high_grade", "type": "int_value"},
            {"name": "sortorder", "type": "int_value"},
            {"name": "schoolgroup", "type": "int_value"},
            {"name": "hist_low_grade", "type": "int_value"},
            {"name": "hist_high_grade", "type": "int_value"},
            {"name": "dfltnextschool", "type": "int_value"},
            {"name": "view_in_portal", "type": "int_value"},
            {"name": "state_excludefromreporting", "type": "int_value"},
            {"name": "alternate_school_number", "type": "int_value"},
            {"name": "fee_exemption_status", "type": "int_value"},
            {"name": "issummerschool", "type": "int_value"},
            {"name": "schoolcategorycodesetid", "type": "int_value"},
            {"name": "whomodifiedid", "type": "int_value"},
        ],
    )
}}
