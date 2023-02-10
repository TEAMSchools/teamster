{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="personaddressid",
        transform_cols=[
            {"name": "personaddressid", "type": "int_value"},
            {"name": "statescodesetid", "type": "int_value"},
            {"name": "countrycodesetid", "type": "int_value"},
            {"name": "geocodelatitude", "type": "bytes_decimal_value"},
            {"name": "geocodelongitude", "type": "bytes_decimal_value"},
        ],
    )
}}
