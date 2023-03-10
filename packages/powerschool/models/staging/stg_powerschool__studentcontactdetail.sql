{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="studentcontactdetailid",
        transform_cols=[
            {
                "name": "studentcontactdetailid",
                "extract": "int_value",
            },
            {
                "name": "studentcontactassocid",
                "extract": "int_value",
            },
            {
                "name": "relationshiptypecodesetid",
                "extract": "int_value",
            },
            {"name": "isactive", "extract": "int_value"},
            {"name": "isemergency", "extract": "int_value"},
            {"name": "iscustodial", "extract": "int_value"},
            {
                "name": "liveswithflg",
                "extract": "int_value",
            },
            {
                "name": "schoolpickupflg",
                "extract": "int_value",
            },
            {
                "name": "receivesmailflg",
                "extract": "int_value",
            },
            {
                "name": "excludefromstatereportingflg",
                "extract": "int_value",
            },
            {
                "name": "generalcommflag",
                "extract": "int_value",
            },
            {
                "name": "confidentialcommflag",
                "extract": "int_value",
            },
        ],
    )
}}
