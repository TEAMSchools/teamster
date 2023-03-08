{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="studentcontactdetailid",
        transform_cols=[
            {
                "name": "studentcontactdetailid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "studentcontactassocid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "relationshiptypecodesetid",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "isactive", "transformation": "extract", "type": "int_value"},
            {"name": "isemergency", "transformation": "extract", "type": "int_value"},
            {"name": "iscustodial", "transformation": "extract", "type": "int_value"},
            {
                "name": "liveswithflg",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "schoolpickupflg",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "receivesmailflg",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "excludefromstatereportingflg",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "generalcommflag",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "confidentialcommflag",
                "transformation": "extract",
                "type": "int_value",
            },
        ],
    )
}}
