{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="personaddressid",
        transform_cols=[
            {
                "name": "personaddressid",
                "extract": "int_value",
            },
            {
                "name": "statescodesetid",
                "extract": "int_value",
            },
            {
                "name": "countrycodesetid",
                "extract": "int_value",
            },
            {
                "name": "geocodelatitude",
                "extract": "bytes_decimal_value",
            },
            {
                "name": "geocodelongitude",
                "extract": "bytes_decimal_value",
            },
        ],
    )
}}
