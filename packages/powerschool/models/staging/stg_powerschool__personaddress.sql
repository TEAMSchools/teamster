{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="personaddressid",
        transform_cols=[
            {
                "name": "personaddressid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "statescodesetid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "countrycodesetid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "geocodelatitude",
                "transformation": "extract",
                "type": "bytes_decimal_value",
            },
            {
                "name": "geocodelongitude",
                "transformation": "extract",
                "type": "bytes_decimal_value",
            },
        ],
    )
}}
